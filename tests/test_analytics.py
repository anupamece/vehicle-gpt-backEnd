from fastapi.testclient import TestClient


def test_vehicle_summary_endpoint(client: TestClient):
    """Verify that GET /api/vehicle/summary returns typed telemetry, battery temperature,

    battery percentage, total distance, energy consumption, and recent event counts.
    """
    response = client.get("/api/vehicle/summary?vehicle_id=v-001")
    assert response.status_code == 200
    data = response.json()

    # Verify vehicle identifiers
    assert data["vehicleId"] == "v-001" or data.get("vehicle_id") == "v-001"
    assert "vin" in data
    assert "make" in data
    assert "model" in data

    # Verify explicit metrics and units
    assert "batteryPercentage" in data or "battery_percentage" in data
    battery_pct = data.get("batteryPercentage") or data.get("battery_percentage")
    assert isinstance(battery_pct, (int, float))
    assert 0.0 <= battery_pct <= 100.0

    assert "batteryTemperature" in data or "battery_temperature" in data
    battery_temp = data.get("batteryTemperature") or data.get("battery_temperature")
    assert isinstance(battery_temp, (int, float))

    assert "totalDistanceKm" in data or "total_distance_km" in data
    assert "energyConsumptionKwh" in data or "energy_consumption_kwh" in data

    # Verify recent event counts structure
    counts = data.get("recentEventCounts") or data.get("recent_event_counts")
    assert counts is not None
    assert "info" in counts
    assert "warning" in counts
    assert "critical" in counts
    assert "total" in counts


def test_vehicle_summary_nonexistent_returns_404(client: TestClient):
    """Verify requesting explicit summary for unknown vehicle ID returns 404."""
    response = client.get("/api/vehicle/summary?vehicle_id=unknown-id-404")
    assert response.status_code == 404


def test_energy_analytics_group_by_driving_mode(client: TestClient):
    """Verify that GET /api/analytics/energy?group_by=driving_mode returns comparable

    city/highway metrics with standardized kWh/100 km units.
    """
    response = client.get("/api/analytics/energy?group_by=driving_mode")
    assert response.status_code == 200
    data = response.json()

    assert data["groupBy"] == "driving_mode" or data.get("group_by") == "driving_mode"
    assert "metricDefinition" in data or "metric_definition" in data
    assert "breakdown" in data
    assert len(data["breakdown"]) >= 2

    modes = [b["drivingMode"] if "drivingMode" in b else b["driving_mode"] for b in data["breakdown"]]
    assert "city" in modes
    assert "highway" in modes

    for item in data["breakdown"]:
        unit = item.get("energyMetricUnit", item.get("energy_metric_unit"))
        assert unit == "kWh/100 km"
        assert "consumptionPer100km" in item or "consumption_per_100km" in item
        assert "totalEnergyConsumedKwh" in item or "total_energy_consumed_kwh" in item
        assert "efficiencyScorePercent" in item or "efficiency_score_percent" in item


def test_post_query_endpoint_contract(client: TestClient):
    """Verify POST /api/query request body {'question': '...'} and response schema

    containing question, answer, intent, data, sources, and warnings.
    """
    payload = {"question": "What is the battery health and charge status?"}
    response = client.post("/api/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["question"] == payload["question"]
    assert "answer" in data and len(data["answer"]) > 0
    assert "intent" in data
    assert isinstance(data.get("data"), dict)
    assert isinstance(data.get("sources"), list)
    assert isinstance(data.get("warnings"), list)
    assert len(data["sources"]) > 0
    assert len(data["warnings"]) > 0


def test_legacy_dashboard_endpoints(client: TestClient):
    """Verify backward compatibility of dashboard stats and vehicle list."""
    stats = client.get("/api/dashboard/stats").json()
    assert "totalVehicles" in stats

    vehicles = client.get("/api/vehicles").json()
    assert isinstance(vehicles, list)
    assert len(vehicles) > 0
