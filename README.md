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

### 4. Configure Local Ollama Inference (Zero Cloud Egress)

VehicleGPT uses local Ollama with `llama3.2:3b` for natural language telemetry synthesis grounded strictly in verified database records and analytics.

#### Step 1: Install Ollama & Pull Model
1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull the recommended local model:
   ```bash
   ollama pull llama3.2:3b
   ```
3. Ensure the local Ollama daemon is active (default port 11434):
   ```bash
   ollama serve
   ```

#### Step 2: Configure Environment Variables
Set the following variables in `.env` (already configured in `.env.example`):
```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT_SECONDS=60.0
```

> **Fallback Mode**: If Ollama is offline, unreachable, or the model is not downloaded, VehicleGPT automatically falls back to deterministic telemetry calculation algorithms with clear diagnostic notices.

### 5. Run the Pytest Test Suite
```bash
# Run mocked unit tests (requires no running Ollama or downloaded model)
pytest tests/test_ollama_service.py -v

# Run live local Ollama model integration tests
pytest tests/test_ollama_integration.py -v

# Run the complete test suite
pytest -v
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
| `GET` | `/api/analytics/energy` | Driving mode comparative consumption (kWh/100 km) & regen |
| `GET` | `/api/analytics/efficiency` | Fleet energy regeneration ratio & net metrics |
| `POST` | `/api/query` | Natural language telemetry query router (Local Ollama grounded) |
| `POST` | `/api/assistant/chat` | VehicleGPT conversational assistant endpoint |

