# VehicleGPT Frontend-Backend Integration & Verification Procedure

This document provides both the automated test commands and the manual verification procedure to validate that the VehicleGPT React frontend (`vehichle-gpt-frontEnd`) integrates seamlessly with the FastAPI backend (`vehicle-gpt-backEnd`) and the generated SQLite database (`vehicle.db`).

---

## 1. Quick Verification Command Summary

### Run Automated Backend & Integration Tests
```powershell
cd "vehicle-gpt-backEnd"
& ".\.venv\Scripts\python.exe" -m pytest -v
```
*Expected Result:* 33 passed tests covering health, simulator, events search, energy analytics, timeline ordering, and end-to-end frontend API contract validation.

### Build and Typecheck Frontend
```powershell
cd "vehichle-gpt-frontEnd"
pnpm build
```
*Expected Result:* `tsc -b && vite build` completes with 0 errors.

---

## 2. Launching Services Locally

### Step 1: Start FastAPI Backend
Open a terminal and run:
```powershell
cd "vehicle-gpt-backEnd"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health` -> `{"status": "ok"}`

### Step 2: Start Vite React Frontend
Open a second terminal and run:
```powershell
cd "vehichle-gpt-frontEnd"
pnpm dev
```
- Frontend application URL: `http://localhost:5173`

---

## 3. Manual Feature Verification Checklist

### Feature 1: Dashboard (`/`)
1. **Live Data Loading:** Open `http://localhost:5173`. Confirm the telemetry summary for `Tesla Model 3 Long Range (2024)` loads without loading spinners or placeholder stubs.
2. **Metrics & Units:**
   - Battery State of Charge: Displays exact percentage (e.g. `66.6%`).
   - Pack Temperature: Displays degrees Celsius (e.g. `27.4°C`).
   - Total Distance: Displays formatted kilometers (e.g. `14,320 km`).
   - Cumulative Energy: Displays formatted kilowatt-hours (e.g. `2,680 kWh`).
3. **Data Origin Badge:** Verify the banner displays `"Historical Simulation"` with the recorded measurement timestamp.
4. **Energy Consumption Chart:** Confirm the Recharts area chart renders 2-hour resampled gross consumption vs regenerative recovery.
5. **Recent Events Feed:** Verify real events from the database populate the right-hand panel.
6. **Vehicle Switching:** Use the vehicle switcher dropdown to select `Rivian R1T (v-002)` or `BMW iX (v-003)` and verify the dashboard updates.

---

### Feature 2: Events & Context Timeline (`/events`)
1. **Event List & Pagination:** Navigate to **Events** in the sidebar. Verify events from the 30-day simulation populate the table.
2. **Filter by Event Type:**
   - Select `adas_disengagement` in the type filter.
   - Confirm only ADAS takeover events are displayed (e.g. "driver steering wheel override torque applied (> 2.5 Nm)", "camera sun glare temporary occlusion").
3. **Filter by Severity:** Select `warning` or `critical` and confirm the badges and rows filter immediately.
4. **Keyword Search:** Type `radar` or `overheat` or `P0A7F` into the search input. Verify filtered results match the query.
5. **Date Window Filter:** Enter a start and end date and confirm results fall strictly within the window.
6. **Timeline Modal (`/api/events/{event_id}/timeline`):**
   - Click the **"Timeline"** button on the `Battery pack temperature exceeded safe threshold (58.6°C)` event (`ev-synth-overheat-001`).
   - Confirm the modal opens with the $\pm 30\text{ min}$ window.
   - Verify the **Engineering Notice** appears: *"Temporal sequence and proximity within the observation window indicate correlation only; they do not establish causation..."*
   - Verify Pre-Warning measurements show climbing temperatures up to $58.6\text{°C}$, while Post-Warning measurements show chiller cooling down to nominal ranges.

---

### Feature 3: Energy Analytics (`/analytics`)
1. **Normalized Metric Standard:** Navigate to **Analytics**. Confirm the banner defines normalized energy consumption in `kWh/100 km`.
2. **City vs. Highway Comparison Cards:**
   - City Consumption: `~15.20 kWh/100 km`
   - Highway Consumption: `~20.78 kWh/100 km`
   - Excess Highway Consumption: `+36.7%` (+5.58 kWh/100 km)
   - City Regeneration Recovery: `~28.0%`
   - Efficiency Leader: `CITY`
3. **Recharts Visualizations:**
   - Normalized Consumption Rate bar chart renders City (green) vs Highway (orange).
   - Energy Consumed vs Regenerated balance chart renders kilowatt-hours side-by-side.
4. **Outlier Validation:** Verify the data validation box confirms valid trip counts.

---

### Feature 4: VehicleGPT Assistant (`/assistant`)
1. Navigate to **Assistant** in the sidebar.
2. Ask: *"What is the battery health and charge status?"*
3. Confirm the backend processes the query via `POST /api/query` and returns a structured response with intent, data snapshot, sources, and diagnostic warnings.

---

## 4. Error Handling & Resilience
1. Stop the backend server (`Ctrl+C` in the backend terminal).
2. Refresh `http://localhost:5173`.
3. Confirm the frontend displays `<ErrorState />` with a **"Retry"** button rather than silently showing fabricated mock data.
4. Restart the backend server and click **"Retry"**; confirm live telemetry immediately resumes.
