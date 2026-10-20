import datetime
from fastapi.testclient import TestClient


def test_paginated_events_list(client: TestClient):
    """Verify that GET /api/events returns a paginated result with items and total."""
    response = client.get("/api/events")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= len(data["items"])
    assert len(data["items"]) > 0

    first = data["items"][0]
    assert "id" in first
    assert "vehicleId" in first
    assert "type" in first
    assert "severity" in first
    assert "message" in first
    assert "timestamp" in first


def test_events_filtering_by_event_type(client: TestClient):
    """Verify filtering by event_type parameter."""
    response = client.get("/api/events?event_type=diagnostic")
    assert response.status_code == 200
    data = response.json()
    assert all(e["type"] == "diagnostic" for e in data["items"])


def test_events_filtering_by_severity(client: TestClient):
    """Verify filtering by severity parameter."""
    response = client.get("/api/events?severity=critical")
    assert response.status_code == 200
    data = response.json()
    assert all(e["severity"] == "critical" for e in data["items"])


def test_events_filtering_by_time_range(client: TestClient):
    """Verify filtering by start_time and end_time parameters."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start = (now - datetime.timedelta(hours=2)).isoformat()
    end = (now + datetime.timedelta(hours=1)).isoformat()

    response = client.get(f"/api/events?start_time={start}&end_time={end}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_event_timeline_window(client: TestClient):
    """Verify that GET /api/events/{event_id}/timeline returns event, timestamp,

    time_window, related_events, and related_telemetry.
    """
    events_res = client.get("/api/events?limit=1")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert len(events_data["items"]) > 0
    event_id = events_data["items"][0]["id"]

    response = client.get(f"/api/events/{event_id}/timeline?before_minutes=60&after_minutes=60")
    assert response.status_code == 200
    data = response.json()

    assert "event" in data
    assert data["event"]["id"] == event_id
    assert "timestamp" in data

    assert "timeWindow" in data or "time_window" in data
    window = data.get("timeWindow") or data.get("time_window")
    assert window["beforeMinutes"] == 60 or window["before_minutes"] == 60
    assert window["afterMinutes"] == 60 or window["after_minutes"] == 60
    assert "windowStart" in window or "window_start" in window
    assert "windowEnd" in window or "window_end" in window

    assert "relatedEvents" in data or "related_events" in data
    assert "relatedTelemetry" in data or "related_telemetry" in data
    assert isinstance(data.get("relatedEvents", data.get("related_events")), list)
    assert isinstance(data.get("relatedTelemetry", data.get("related_telemetry")), list)


def test_event_timeline_not_found(client: TestClient):
    """Verify requesting timeline for nonexistent event returns 404."""
    response = client.get("/api/events/nonexistent-999/timeline")
    assert response.status_code == 404
