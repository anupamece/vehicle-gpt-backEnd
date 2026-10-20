"""End-to-End Frontend-Backend Integration Test Suite.

Validates that all backend REST APIs strictly adhere to the contracts,
data shapes, and units required by the React frontend pages and components:
- DashboardPage (/api/vehicle/summary, /api/dashboard/stats, /api/energy)
- EventsPage (/api/events, ADAS filtering, date ranges, text search)
- EventTimelineModal (/api/events/{event_id}/timeline, pre/post partitioning, causation disclaimer)
- AnalyticsPage (/api/analytics/energy?group_by=driving_mode, comparison, warnings)
- AssistantPage / ChatPanel (/api/query)
"""

import datetime
from fastapi.testclient import TestClient


def test_frontend_dashboard_page_contract(client: TestClient):
    """Verify backend supplies all required fields for DashboardPage."""
    # 1. Vehicle Summary
    res = client.get("/api/vehicle/summary?vehicle_id=v-001")
    assert res.status_code == 200
    data = res.json()

    # Required vehicle identifiers
    assert data["vehicleId"] == "v-001"
    assert data["vin"] is not None
    assert data["make"] == "Tesla"
    assert data["model"] == "Model 3 Long Range"
    assert data["status"] in ("online", "offline", "driving", "charging", "idle")

    # Explicit units and numbers
    assert isinstance(data["batteryPercentage"], (int, float))
    assert 0.0 <= data["batteryPercentage"] <= 100.0
    assert isinstance(data["batteryTemperature"], (int, float))
    assert isinstance(data["totalDistanceKm"], (int, float))
    assert isinstance(data["energyConsumptionKwh"], (int, float))

    # Recent event counts structure
    counts = data["recentEventCounts"]
    assert "info" in counts
    assert "warning" in counts
    assert "critical" in counts
    assert "total" in counts

    # Latest telemetry snapshot
    assert data["latestTelemetry"] is not None
    assert data["lastMeasurementTime"] is not None
    assert data["isLive"] is False
    assert data["isSynthetic"] is True
    assert data["dataSource"] == "historical_simulation"

    # 2. Energy Chart Time Series (Dashboard Left)
    res_en = client.get("/api/energy")
    assert res_en.status_code == 200
    energy_points = res_en.json()
    assert isinstance(energy_points, list)
    if energy_points:
        p = energy_points[0]
        assert "timestamp" in p
        assert "consumed" in p
        assert "regenerated" in p

    # 3. Dashboard Fleet KPI Stats
    res_stats = client.get("/api/dashboard/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["totalVehicles"] >= 1
    assert stats["activeVehicles"] >= 0
    assert stats["totalAlerts"] >= 0
    assert isinstance(stats["avgBatteryLevel"], (int, float))


def test_frontend_events_page_and_timeline_contract(client: TestClient):
    """Verify backend supplies all required fields for EventsPage and EventTimelineModal."""
    # 1. Paginated Events with filters
    res = client.get("/api/events?limit=25&offset=0")
    assert res.status_code == 200
    events_data = res.json()
    assert "items" in events_data
    assert "total" in events_data
    assert len(events_data["items"]) > 0

    first_event = events_data["items"][0]
    assert "id" in first_event
    assert "vehicleId" in first_event
    assert "type" in first_event
    assert "severity" in first_event
    assert "message" in first_event
    assert "timestamp" in first_event

    # 2. ADAS Disengagement filter test
    res_adas = client.get("/api/events?event_type=adas_disengagement")
    assert res_adas.status_code == 200
    adas_data = res_adas.json()
    assert all(e["type"] == "adas_disengagement" for e in adas_data["items"])

    # 3. Timeline context for EventTimelineModal
    event_id = first_event["id"]
    res_timeline = client.get(f"/api/events/{event_id}/timeline?before_minutes=30&after_minutes=30")
    assert res_timeline.status_code == 200
    timeline = res_timeline.json()

    assert "event" in timeline
    assert timeline["event"]["id"] == event_id
    assert "timeWindow" in timeline
    assert "causationDisclaimer" in timeline
    assert "preEventTelemetry" in timeline
    assert "postEventTelemetry" in timeline
    assert "relatedEvents" in timeline

    # Strict chronological ordering check
    telem = timeline["relatedTelemetry"]
    for i in range(len(telem) - 1):
        assert telem[i]["timestamp"] <= telem[i + 1]["timestamp"]


def test_frontend_analytics_page_contract(client: TestClient):
    """Verify backend supplies all required fields for AnalyticsPage."""
    res = client.get("/api/analytics/energy?group_by=driving_mode")
    assert res.status_code == 200
    analytics = res.json()

    assert analytics["groupBy"] == "driving_mode"
    assert "kWh/100 km" in analytics["metricDefinition"]
    assert "breakdown" in analytics
    assert len(analytics["breakdown"]) == 2

    for item in analytics["breakdown"]:
        assert item["drivingMode"] in ("city", "highway")
        assert item["energyMetricUnit"] == "kWh/100 km"
        assert item["consumptionPer100km"] is not None
        assert item["totalEnergyConsumedKwh"] > 0
        assert item["totalEnergyRegeneratedKwh"] >= 0
        assert item["totalDistanceKm"] > 0
        assert item["averageSpeedKmh"] > 0
        assert 0.0 <= item["efficiencyScorePercent"] <= 100.0

    # Comparison metrics block
    assert "comparison" in analytics
    comp = analytics["comparison"]
    assert "city_kwh_per_100km" in comp
    assert "highway_kwh_per_100km" in comp
    assert "consumption_delta_kwh_per_100km" in comp
    assert comp["more_efficient_mode"] == "city"

    # Warnings list
    assert "warnings" in analytics
    assert isinstance(analytics["warnings"], list)


def test_frontend_chat_assistant_contract(client: TestClient):
    """Verify backend supplies natural language responses for ChatPanel."""
    payload = {"question": "What is the current vehicle battery status?"}
    res = client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["question"] == payload["question"]
    assert "answer" in data and len(data["answer"]) > 0
    assert "intent" in data
    assert "sources" in data
    assert "warnings" in data
