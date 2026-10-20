from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Verify that GET /api/health returns HTTP 200 with exactly {'status': 'ok'}."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_endpoint(client: TestClient):
    """Verify that Swagger documentation is accessible at /docs."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "")


def test_openapi_schema(client: TestClient):
    """Verify that OpenAPI specification is available at /openapi.json with expected paths."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/api/health" in paths
    assert "/api/vehicle/summary" in paths
    assert "/api/events" in paths
    assert "/api/events/{event_id}/timeline" in paths
    assert "/api/analytics/energy" in paths
    assert "/api/query" in paths
