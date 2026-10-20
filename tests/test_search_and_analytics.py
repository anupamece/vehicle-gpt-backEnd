"""Unit and integration tests for VehicleGPT deterministic search and analytics services.

Covers:
- Date and time filtering for ADAS disengagement and diagnostic events
- Empty result handling across filters and non-existent IDs
- Energy analytics city vs highway comparison with kWh/100 km normalization
- Invalid measurement detection, trip exclusion, and data-quality warnings
- Chronological fault timeline ordering and non-causation engineering disclaimers
- Vehicle summary latest telemetry, measurement timestamps, and simulation indicators
"""

import datetime
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import EventModel, TelemetryModel, TripModel, VehicleModel
from app.services.energy_analysis import analyze_energy_by_driving_mode
from app.services.event_search import build_event_timeline, search_events_paginated


def test_adas_disengagement_date_time_filtering(client: TestClient):
    """Verify filtering ADAS disengagement events by event_type and time window."""
    # 1. Fetch all ADAS events
    response = client.get("/api/events?event_type=adas_disengagement")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0

    for item in data["items"]:
        assert item["type"] == "adas_disengagement"
        assert "ADAS disengagement:" in item["message"]

    # Pick the timestamp of the first ADAS event
    target_event = data["items"][0]
    ts = datetime.datetime.fromisoformat(target_event["timestamp"].replace("Z", "+00:00"))

    start = (ts - datetime.timedelta(minutes=1)).isoformat()
    end = (ts + datetime.timedelta(minutes=1)).isoformat()

    filtered_res = client.get(
        f"/api/events?event_type=adas_disengagement&start_time={start}&end_time={end}"
    )
    assert filtered_res.status_code == 200
    filtered_data = filtered_res.json()
    assert filtered_data["total"] >= 1
    found_ids = [e["id"] for e in filtered_data["items"]]
    assert target_event["id"] in found_ids


def test_event_filtering_empty_results(client: TestClient):
    """Verify empty result responses for non-matching criteria."""
    # Non-matching future date range
    start_future = "2099-01-01T00:00:00Z"
    end_future = "2099-01-02T00:00:00Z"
    res = client.get(f"/api/events?start_time={start_future}&end_time={end_future}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []

    # Non-existent event type
    res_type = client.get("/api/events?event_type=non_existent_type_xyz")
    assert res_type.status_code == 200
    assert res_type.json()["total"] == 0
    assert res_type.json()["items"] == []

    # Non-existent vehicle ID
    res_veh = client.get("/api/events?vehicle_id=non-existent-veh-999")
    assert res_veh.status_code == 200
    assert res_veh.json()["total"] == 0
    assert res_veh.json()["items"] == []


def test_event_sorting_and_pagination(client: TestClient):
    """Verify predictable ascending/descending sorting and pagination."""
    # Descending order (default)
    res_desc = client.get("/api/events?sort_order=desc&limit=10")
    assert res_desc.status_code == 200
    items_desc = res_desc.json()["items"]
    assert len(items_desc) >= 2
    for i in range(len(items_desc) - 1):
        t1 = items_desc[i]["timestamp"]
        t2 = items_desc[i + 1]["timestamp"]
        assert t1 >= t2

    # Ascending order
    res_asc = client.get("/api/events?sort_order=asc&limit=10")
    assert res_asc.status_code == 200
    items_asc = res_asc.json()["items"]
    assert len(items_asc) >= 2
    for i in range(len(items_asc) - 1):
        t1 = items_asc[i]["timestamp"]
        t2 = items_asc[i + 1]["timestamp"]
        assert t1 <= t2

    # Pagination offsets do not overlap
    res_page1 = client.get("/api/events?limit=3&offset=0").json()
    res_page2 = client.get("/api/events?limit=3&offset=3").json()
    ids_p1 = {e["id"] for e in res_page1["items"]}
    ids_p2 = {e["id"] for e in res_page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)


def test_event_keyword_search(client: TestClient):
    """Verify keyword filtering across descriptions, DTCs, and identifiers."""
    res = client.get("/api/events?query=battery")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0
    for item in items:
        assert (
            "battery" in item["message"].lower()
            or "battery" in item["type"].lower()
            or "battery" in (item.get("dtcCode") or "").lower()
        )


def test_energy_analytics_city_vs_highway_comparison(client: TestClient):
    """Verify energy analytics returns comparable city and highway metrics with comparison block."""
    res = client.get("/api/analytics/energy?group_by=driving_mode")
    assert res.status_code == 200
    data = res.json()

    assert data["groupBy"] == "driving_mode"
    assert "kWh/100 km" in data["metricDefinition"]
    assert len(data["breakdown"]) == 2

    breakdown_map = {b["drivingMode"]: b for b in data["breakdown"]}
    assert "city" in breakdown_map
    assert "highway" in breakdown_map

    city = breakdown_map["city"]
    highway = breakdown_map["highway"]

    # Verify kWh/100km calculations
    assert city["consumptionPer100km"] is not None
    assert highway["consumptionPer100km"] is not None
    assert city["totalDistanceKm"] > 0
    assert highway["totalDistanceKm"] > 0

    # Physical reality check: city regeneration efficiency should exceed highway cruising
    assert city["efficiencyScorePercent"] > highway["efficiencyScorePercent"]

    # Underlying comparison block
    comparison = data.get("comparison")
    assert comparison is not None
    assert "city_kwh_per_100km" in comparison
    assert "highway_kwh_per_100km" in comparison
    assert "consumption_delta_kwh_per_100km" in comparison
    assert comparison["more_efficient_mode"] == "city"

    # Data quality warnings list
    assert "warnings" in data
    assert isinstance(data["warnings"], list)


def test_energy_analytics_invalid_measurements_handling():
    """Verify that invalid trips (zero distance, non-positive energy) are excluded and flagged with warnings."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    # Seed 1 valid city trip
    now = datetime.datetime.now(datetime.timezone.utc)
    t_valid = TripModel(
        id="trip-valid-1",
        vehicle_id="v-test",
        start_time=now - datetime.timedelta(hours=2),
        end_time=now - datetime.timedelta(hours=1),
        driving_mode="city",
        distance_km=25.0,
        energy_consumed_kwh=4.0,
        energy_regenerated_kwh=1.0,
        avg_speed_kmh=30.0,
        is_synthetic=True,
    )
    # Seed 1 invalid zero-distance trip
    t_zero_dist = TripModel(
        id="trip-invalid-dist",
        vehicle_id="v-test",
        start_time=now - datetime.timedelta(hours=4),
        end_time=now - datetime.timedelta(hours=3),
        driving_mode="city",
        distance_km=0.0,
        energy_consumed_kwh=1.5,
        energy_regenerated_kwh=0.0,
        avg_speed_kmh=0.0,
        is_synthetic=True,
    )
    # Seed 1 invalid negative energy trip
    t_neg_energy = TripModel(
        id="trip-invalid-energy",
        vehicle_id="v-test",
        start_time=now - datetime.timedelta(hours=6),
        end_time=now - datetime.timedelta(hours=5),
        driving_mode="highway",
        distance_km=40.0,
        energy_consumed_kwh=-2.0,
        energy_regenerated_kwh=0.0,
        avg_speed_kmh=80.0,
        is_synthetic=True,
    )
    db.add_all([t_valid, t_zero_dist, t_neg_energy])
    db.commit()

    # Run analysis
    result = analyze_energy_by_driving_mode(db=db)

    # Both invalid trips must be flagged in warnings
    assert any("trip-invalid-dist" in w for w in result.warnings)
    assert any("trip-invalid-energy" in w for w in result.warnings)

    # Only valid trip distance should contribute
    assert result.summary["valid_trips"] == 1
    assert result.summary["excluded_trips"] == 2
    assert result.summary["total_distance_km"] == 25.0

    db.close()


def test_timeline_chronological_ordering_and_causation_disclaimer(client: TestClient):
    """Verify timeline strictly orders telemetry, distinguishes pre/post warning, and contains causation disclaimer."""
    # Look up the overheating event
    events_res = client.get("/api/events?event_type=battery&severity=warning")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert len(events_data["items"]) > 0
    overheat_event_id = events_data["items"][0]["id"]

    res = client.get(f"/api/events/{overheat_event_id}/timeline?before_minutes=30&after_minutes=30")
    assert res.status_code == 200
    data = res.json()

    # Verify causation disclaimer
    disclaimer = data.get("causationDisclaimer") or data.get("causation_disclaimer")
    assert disclaimer is not None
    assert "correlation only" in disclaimer.lower()
    assert "does not establish causation" in disclaimer.lower() or "do not establish causation" in disclaimer.lower()

    # Verify chronological ordering of all related telemetry
    telemetry = data.get("relatedTelemetry") or data.get("related_telemetry")
    assert len(telemetry) > 0
    for i in range(len(telemetry) - 1):
        t1 = telemetry[i]["timestamp"]
        t2 = telemetry[i + 1]["timestamp"]
        assert t1 <= t2

    # Verify pre-event and post-event partitioning
    pre_telemetry = data.get("preEventTelemetry") or data.get("pre_event_telemetry")
    post_telemetry = data.get("postEventTelemetry") or data.get("post_event_telemetry")
    assert pre_telemetry is not None
    assert post_telemetry is not None

    event_ts = data["event"]["timestamp"]
    for t in pre_telemetry:
        assert t["timestamp"] <= event_ts
        assert t.get("phase") in ("pre_warning", "at_event")

    for t in post_telemetry:
        assert t["timestamp"] > event_ts
        assert t.get("phase") == "post_warning"


def test_vehicle_summary_latest_telemetry_and_historical_distinction(client: TestClient):
    """Verify vehicle summary returns latest telemetry, last measurement time, and historical simulation distinction."""
    res = client.get("/api/vehicle/summary?vehicle_id=v-001")
    assert res.status_code == 200
    data = res.json()

    assert data["vehicleId"] == "v-001"
    assert data["batteryPercentage"] is not None
    assert data["batteryTemperature"] is not None
    assert data["latestTelemetry"] is not None

    # Indicate when most recent measurement was recorded
    assert data.get("lastMeasurementTime") is not None
    assert data["lastMeasurementTime"] == data["latestTelemetry"]["timestamp"]

    # Explicitly distinguish historical simulated values from live data
    assert data.get("isLive") is False
    assert data.get("isSynthetic") is True
    assert data.get("dataSource") == "historical_simulation"
    assert data.get("dataQualityNotes") is not None

    # Verify recent event counts structure
    counts = data.get("recentEventCounts")
    assert counts is not None
    assert "info" in counts
    assert "warning" in counts
    assert "critical" in counts
    assert "total" in counts
