# VehicleGPT Backend

FastAPI & SQLAlchemy backend service providing automotive telemetry ingestion, fleet diagnostics, energy efficiency analytics, and natural language query routing for the VehicleGPT dashboard.

---

## Tech Stack
- **Framework**: FastAPI (Swagger docs at `/docs`)
- **Database**: SQLite (SQLAlchemy ORM models in `app/db/models.py`)
- **Data Analysis**: pandas & numpy
- **Validation**: Pydantic v2 schemas
- **Testing**: pytest & FastAPI TestClient

---

## Directory Structure
```
backend/
  app/
    __init__.py
    main.py
    api/
      __init__.py
      health.py
      vehicle.py
      events.py
      analytics.py
      query.py
    core/
      config.py
    db/
      __init__.py
      database.py
      models.py
      schema.sql
    schemas/
      __init__.py
      vehicle.py
      events.py
      query.py
    services/
      event_search.py
      energy_analysis.py
      fault_timeline.py
      query_router.py
    simulator/
      __init__.py
      generate_data.py
  data/
    vehicle_gpt.db      (Generated automatically)
  tests/
    test_health.py
    test_events.py
    test_analytics.py
  requirements.txt
  .env.example
```

---

## Quickstart Instructions

### 1. Set Up Virtual Environment & Dependencies
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default SQLite database file is created automatically under `backend/data/vehicle_gpt.db`.

### 3. Run the Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### 4. Run the Pytest Test Suite
```bash
pytest -v
```
To run with coverage:
```bash
pytest -v --tb=short
```

---

## API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status and database connectivity check |
| `GET` | `/docs` | OpenAPI / Swagger interactive documentation |
| `GET` | `/api/vehicles` | List all fleet vehicles with real-time status |
| `GET` | `/api/vehicles/{id}` | Telemetry snapshot for specific vehicle |
| `GET` | `/api/dashboard/stats` | Aggregated fleet KPIs for the dashboard |
| `GET` | `/api/events` | Filtered telemetry events (by severity, type, vehicle) |
| `GET` | `/api/events/timeline/faults` | Fault timeline grouping critical and warning alerts |
| `GET` | `/api/analytics/energy` | 24h consumption & regeneration data points |
| `GET` | `/api/analytics/efficiency` | Fleet energy regeneration ratio & net metrics |
| `POST` | `/api/query` | Natural language telemetry query router |
| `POST` | `/api/assistant/chat` | VehicleGPT conversational assistant endpoint |
