# VehicleGPT Synthetic Telemetry Data Dictionary

> **Disclaimer:** All records contained within `backend/data/vehicle.db` are **strictly synthetic** test data generated via mathematical simulation models for demonstration, benchmarking, and hackathon development. They do not represent real proprietary telemetry or actual customer vehicles.

---

## 1. Physical Units Standard

| Dimension | Engineering Unit | Symbol | Range / Constraints |
|---|---|---|---|
| **Battery State of Charge** | Percentage | `%` | `0.0` to `100.0%` |
| **Battery Pack Temperature** | Degrees Celsius | `°C` | `-20.0` to `70.0°C` (Normal: `20-35°C`, Overheat: `> 55.0°C`) |
| **Vehicle Speed** | Kilometers per hour | `km/h` | `0.0` to `140.0 km/h` (`null` during sensor dropouts) |
| **Segment & Trip Distance** | Kilometers | `km` | `>= 0.0 km` |
| **Energy Consumption** | Kilowatt-hours | `kWh` | `>= 0.0 kWh` |
| **Normalized Energy Rate** | kWh per 100 kilometers | `kWh/100 km` | City: `~14-17`, Highway: `~19-23` |
| **Timestamps** | ISO-8601 UTC | — | Formatted as UTC ISO-8601 with timezone awareness |
| **Geographic Coordinates** | Decimal Degrees | `°` | WGS 84 (`null` during GPS canyon/tunnel dropouts) |

---

## 2. Table Specifications

### 2.1 `vehicles`
Represents connected electric fleet vehicles.

| Column | Type | Nullable | Units | Default | Description |
|---|---|---|---|---|---|
| `id` | `VARCHAR(64)` | No | — | Primary Key | Unique vehicle identifier (e.g. `v-001`) |
| `vin` | `VARCHAR(32)` | No | — | Unique | 17-character Vehicle Identification Number |
| `make` | `VARCHAR(64)` | No | — | — | Manufacturer (e.g. `Tesla`, `Rivian`, `BMW`) |
| `model` | `VARCHAR(64)` | No | — | — | Vehicle commercial model name |
| `year` | `INTEGER` | No | — | — | Model manufacturing year |
| `status` | `VARCHAR(32)` | No | — | `'idle'` | Operating status: `online`, `offline`, `charging`, `driving`, `idle` |
| `battery_level` | `REAL` | Yes | `%` | `100.0` | Latest recorded battery state of charge percentage |
| `battery_temperature` | `REAL` | Yes | `°C` | `25.0` | Latest battery pack temperature |
| `odometer` | `REAL` | Yes | `km` | `0.0` | Lifetime cumulative odometer distance |
| `total_energy_kwh` | `REAL` | Yes | `kWh` | `0.0` | Lifetime cumulative energy consumed |
| `is_synthetic` | `BOOLEAN` | No | — | `1` (`TRUE`) | Synthetic data indicator flag |
| `last_seen` | `DATETIME` | No | UTC | `CURRENT_TIMESTAMP` | Last network ping timestamp |

---

### 2.2 `trips`
Represents individual segmented journeys (city commutes, highway transits).

| Column | Type | Nullable | Units | Default | Description |
|---|---|---|---|---|---|
| `id` | `VARCHAR(64)` | No | — | Primary Key | Journey identifier (e.g. `trip-v-001-20261001-0730`) |
| `vehicle_id` | `VARCHAR(64)` | No | — | FK -> `vehicles.id` | Associated vehicle |
| `start_time` | `DATETIME` | No | UTC | — | Journey start timestamp |
| `end_time` | `DATETIME` | No | UTC | — | Journey completion timestamp |
| `driving_mode` | `VARCHAR(32)` | No | — | — | Environment classification: `city` or `highway` |
| `distance_km` | `REAL` | No | `km` | `0.0` | Total distance driven on trip |
| `energy_consumed_kwh` | `REAL` | No | `kWh` | `0.0` | Total energy consumed during trip |
| `energy_regenerated_kwh`| `REAL` | No | `kWh` | `0.0` | Regenerative braking energy recovered |
| `avg_speed_kmh` | `REAL` | No | `km/h` | `0.0` | Average velocity during trip |
| `is_synthetic` | `BOOLEAN` | No | — | `1` | Synthetic data indicator flag |

**Indexes:**
- `idx_trips_vehicle_id` on `(vehicle_id)`
- `idx_trips_start_time` on `(start_time)`
- `idx_trips_end_time` on `(end_time)`
- `idx_trips_driving_mode` on `(driving_mode)`
- `idx_trips_vehicle_start` on `(vehicle_id, start_time)`

---

### 2.3 `telemetry`
High-frequency time-series sensor observations during journeys. Features irregular sampling (30–85s) and occasional simulated dropouts.

| Column | Type | Nullable | Units | Description |
|---|---|---|---|---|
| `id` | `INTEGER` | No | — | Autoincrement Primary Key |
| `vehicle_id` | `VARCHAR(64)` | No | — | FK -> `vehicles.id` |
| `trip_id` | `VARCHAR(64)` | Yes | — | FK -> `trips.id` |
| `timestamp` | `DATETIME` | No | UTC | Telemetry measurement timestamp |
| `speed` | `REAL` | Yes | `km/h` | Vehicle speed (`null` on occasional sensor timeout) |
| `battery_level` | `REAL` | Yes | `%` | State of charge percentage (`0.0 - 100.0%`) |
| `battery_temperature` | `REAL` | Yes | `°C` | Battery cell temperature (`null` on polling timeout) |
| `driving_mode` | `VARCHAR(32)` | Yes | — | Operating mode (`city`, `highway`) |
| `energy_consumed` | `REAL` | No | `kWh` | Incremental energy consumed since prior reading |
| `energy_regenerated`| `REAL` | No | `kWh` | Incremental regenerative braking energy recovered |
| `distance_km` | `REAL` | No | `km` | Incremental distance travelled in segment |
| `latitude` | `REAL` | Yes | `°` | GPS Latitude (`null` during tunnel/canyon dropouts) |
| `longitude` | `REAL` | Yes | `°` | GPS Longitude (`null` during tunnel/canyon dropouts) |
| `is_synthetic` | `BOOLEAN` | No | — | Synthetic data flag (`1`) |

**Indexes:**
- `idx_telemetry_timestamp` on `(timestamp)`
- `idx_telemetry_trip_id` on `(trip_id)`
- `idx_telemetry_vehicle_timestamp` on `(vehicle_id, timestamp)`
- `idx_telemetry_trip_timestamp` on `(trip_id, timestamp)`
- `idx_telemetry_mode` on `(driving_mode)`

---

### 2.4 `events`
Vehicle diagnostic events, ADAS disengagements, thermal alerts, and geofence updates.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `VARCHAR(64)` | No | Primary Key (e.g. `ev-adas-01-08`, `ev-synth-overheat-001`) |
| `vehicle_id` | `VARCHAR(64)` | No | FK -> `vehicles.id` |
| `trip_id` | `VARCHAR(64)` | Yes | FK -> `trips.id` (associated trip during which event occurred) |
| `related_event_id` | `VARCHAR(64)` | Yes | Self-referential FK -> `events.id` (links causes to resolutions) |
| `dtc_code` | `VARCHAR(32)` | Yes | Standard Diagnostic Trouble Code (e.g. `P0A7F`, `C1A12`, `U0100`) |
| `type` | `VARCHAR(32)` | No | Category: `diagnostic`, `alert`, `adas_disengagement`, `battery`, `system`, `maintenance` |
| `severity` | `VARCHAR(32)` | No | Classification: `info`, `warning`, `critical` |
| `message` | `TEXT` | No | Human and LLM readable descriptive event notification |
| `timestamp` | `DATETIME` | No | Event occurrence timestamp in UTC |
| `metadata_json` | `TEXT` | Yes | JSON payload with context (`trigger`, `freeze_frame`, `threshold_celsius`) |
| `is_synthetic` | `BOOLEAN` | No | Synthetic flag (`1`) |

**Indexes:**
- `idx_events_timestamp` on `(timestamp)`
- `idx_events_type` on `(type)`
- `idx_events_severity` on `(severity)`
- `idx_events_type_severity` on `(type, severity)`
- `idx_events_related` on `(related_event_id)`
- `idx_events_trip_id` on `(trip_id)`
- `idx_events_dtc_code` on `(dtc_code)`

---

## 3. Notable Synthetic Scenarios

### 3.1 Battery Overheating Warning & Thermal Ramp Down
- **Target Event ID:** `ev-synth-overheat-001`
- **Location:** Occurs on **Day 18** of the 30-day simulation during high-speed highway transit.
- **Telemetry Pre-Warning:** Temperature climbs from `30.0°C` to peak at `58.6°C` (> `55.0°C` safety limit).
- **Warning Notification:** Severity `warning`, DTC `P0A12` announcing active chiller coolant engagement.
- **Telemetry Post-Warning:** Cooling ramp down from `58.6°C` back to `34.0°C`.
- **Linked Resolution Event:** `ev-synth-overheat-resolved` referencing `related_event_id="ev-synth-overheat-001"`.

### 3.2 ADAS Disengagements
- **Type:** `adas_disengagement`
- **Scenarios:** Construction lane marking fades, manual driver steering override torque (> 2.5 Nm), low sun glare camera occlusion, cut-in safety buffer activation.
- **Metadata:** Context includes `takeover_time_ms`, vehicle speed, and trigger classification.

### 3.3 Diagnostic Trouble Codes (DTC)
- **Codes:** `C1A12` (Forward radar misalignment), `P0A7F` (Battery pack resistance degradation), `U0100` (CAN bus communication loss).
- **Event Linkages:** Primary DTC warnings are linked to secondary diagnostic freeze-frame telemetry scans via `related_event_id`.
