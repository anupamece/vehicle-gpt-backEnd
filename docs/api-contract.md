# VehicleGPT API Contract Specification

**Version:** 1.0.0  
**Status:** Stable  
**Base URL:** `http://localhost:8000/api`  
**CORS Allowed Origin:** `http://localhost:5173`  
**OpenAPI Swagger Documentation:** `http://localhost:8000/docs`

---

## 1. Global Conventions & Physical Units Standard

All measurements across VehicleGPT adhere to strict engineering units. Nullable values return `null` when telemetry sensors are offline or measurements are unavailable rather than inventing placeholder values.

| Measurement Dimension | Engineering Unit | Symbol | Range / Format |
|---|---|---|---|
| **Battery State of Charge** | Percentage | `%` | `0.0` to `100.0` |
| **Battery Pack Temperature** | Degrees Celsius | `°C` | `-40.0` to `80.0` |
| **Vehicle Speed** | Kilometers per hour | `km/h` | `0.0` to `300.0` |
| **Cumulative Distance** | Kilometers | `km` | `>= 0.0` |
| **Cumulative Energy** | Kilowatt-hours | `kWh` | `>= 0.0` |
| **Standardized Energy Rate** | kWh per 100 kilometers | `kWh/100 km` | Normalized consumption rate |
| **Timestamps** | ISO-8601 UTC | — | `YYYY-MM-DDTHH:MM:SSZ` |
| **Geographic Coordinates** | Decimal Degrees (WGS 84) | `°` | Lat: `[-90, 90]`, Lng: `[-180, 180]` |

---

## 2. Shared Type Mapping Matrix

| Endpoint | Backend Pydantic Schema | Frontend TypeScript Interface |
|---|---|---|
| `GET /api/health` | `HealthResponse` | `HealthResponse` |
| `GET /api/vehicle/summary` | `VehicleSummaryResponse` | `VehicleSummaryResponse` |
| `GET /api/events` | `PaginatedEventsResponse` | `PaginatedEventsResponse` |
| `GET /api/events/{id}/timeline` | `EventTimelineDetailResponse` | `EventTimelineDetailResponse` |
| `GET /api/analytics/energy` | `EnergyAnalyticsResponse` | `EnergyAnalyticsResponse` |
| `POST /api/query` | `QueryResponse` | `QueryResponse` |

---

## 3. Endpoint Specifications

### 3.1 Health Check
- **Route:** `GET /api/health`
- **Summary:** Simple status check verifying service availability.
- **Request Parameters:** None.
- **Response Status:** `200 OK`
- **Response Schema:**
```json
{
  "status": "ok"
}
```

---

### 3.2 Vehicle Summary
- **Route:** `GET /api/vehicle/summary`
- **Summary:** Returns typed telemetry and diagnostic summary for a vehicle with explicit engineering units.
- **Query Parameters:**
  - `vehicle_id` *(optional, string)*: Specific vehicle ID. If omitted, returns the primary active fleet vehicle.
- **Behavior on Missing Data:** If no vehicle or measurements are available, returns typed `null` values without fabricating data. If an invalid ID is specified, returns `404 Not Found`.
- **Response Schema:**
```typescript
interface VehicleSummaryResponse {
  vehicleId: string | null;
  vin: string | null;
  make: string | null;
  model: string | null;
  year: number | null;
  status: "online" | "offline" | "charging" | "driving" | "idle" | string | null;
  batteryPercentage: number | null;        // Unit: % (0.0 - 100.0)
  batteryTemperature: number | null;       // Unit: °C
  totalDistanceKm: number | null;          // Unit: km
  energyConsumptionKwh: number | null;     // Unit: kWh
  recentEventCounts: {
    info: number;
    warning: number;
    critical: number;
    total: number;
  };
  latestTelemetry: {
    timestamp: string;
    speedKmh: number | null;
    batteryLevelPercent: number | null;
    batteryTemperatureCelsius: number | null;
    drivingMode: "city" | "highway" | string | null;
    energyConsumedKwh: number | null;
    energyRegeneratedKwh: number | null;
    latitude: number | null;
    longitude: number | null;
  } | null;
  lastMeasurementTime?: string | null;     // When the latest telemetry measurement was recorded
  isLive?: boolean;                        // False for historical simulation, True for live CAN bus
  isSynthetic?: boolean;                   // Indicator of synthetic simulation data origin
  dataSource?: string;                     // "historical_simulation" | "live_sensor_stream"
  dataQualityNotes?: string | null;        // Quality caveats, dropout rates, sensor tolerances
}
```
- **Example Response:**
```json
{
  "vehicleId": "v-001",
  "vin": "1HGCM82633A004352",
  "make": "Tesla",
  "model": "Model 3",
  "year": 2024,
  "status": "driving",
  "batteryPercentage": 78.0,
  "batteryTemperature": 29.5,
  "totalDistanceKm": 14320.0,
  "energyConsumptionKwh": 2680.0,
  "recentEventCounts": {
    "info": 2,
    "warning": 1,
    "critical": 0,
    "total": 3
  },
  "latestTelemetry": {
    "timestamp": "2026-10-20T05:00:00Z",
    "speedKmh": 88.5,
    "batteryLevelPercent": 78.0,
    "batteryTemperatureCelsius": 29.5,
    "drivingMode": "highway",
    "energyConsumedKwh": 7.38,
    "energyRegeneratedKwh": 0.95,
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "lastMeasurementTime": "2026-10-20T05:00:00Z",
  "isLive": false,
  "isSynthetic": true,
  "dataSource": "historical_simulation",
  "dataQualityNotes": "Telemetry derived from 30-day deterministic automotive simulation; includes sensor noise and occasional GPS dropouts."
}
```

---

### 3.3 Paginated Telemetry Events
- **Route:** `GET /api/events`
- **Summary:** Filtered and paginated list of telemetry, alert, diagnostic, and geofence events.
- **Query Parameters:**
  - `event_type` *(optional, string)*: Filter by event type (`diagnostic`, `alert`, `maintenance`, `geofence`, `battery`, `system`, `adas_disengagement`).
  - `severity` *(optional, string)*: Filter by severity (`info`, `warning`, `critical`).
  - `start_time` *(optional, string)*: ISO-8601 timestamp floor (`timestamp >= start_time`).
  - `end_time` *(optional, string)*: ISO-8601 timestamp ceiling (`timestamp <= end_time`).
  - `vehicle_id` *(optional, string)*: Filter to specific vehicle ID.
  - `query` *(optional, string)*: Case-insensitive search across event messages, DTC codes, and identifiers.
  - `sort_by` *(optional, string, default: "timestamp")*: Sort attribute (`timestamp`, `severity`, `type`).
  - `sort_order` *(optional, string, default: "desc")*: Sort direction (`desc` or `asc`).
  - `limit` *(optional, integer, default: 50, max: 200)*: Items per page.
  - `offset` *(optional, integer, default: 0)*: Starting pagination offset.
- **Response Schema:**
```typescript
interface PaginatedEventsResponse {
  items: Array<{
    id: string;
    vehicleId: string;
    tripId?: string | null;
    relatedEventId?: string | null;
    dtcCode?: string | null;
    type: "diagnostic" | "alert" | "maintenance" | "geofence" | "battery" | "system" | "adas_disengagement" | string;
    severity: "info" | "warning" | "critical";
    message: string;
    timestamp: string;
    metadata?: Record<string, unknown> | null;
    isSynthetic?: boolean;
  }>;
  total: number;
  limit: number;
  offset: number;
}
```
- **Example Response:**
```json
{
  "items": [
    {
      "id": "ev-adas-27-10",
      "vehicleId": "v-001",
      "tripId": "trip-v-001-20261017-1030",
      "relatedEventId": null,
      "dtcCode": null,
      "type": "adas_disengagement",
      "severity": "warning",
      "message": "ADAS disengagement: driver steering wheel override torque applied (> 2.5 Nm)",
      "timestamp": "2026-10-17T10:43:00Z",
      "metadata": {
        "trigger": "manual_driver_override",
        "speed_kmh": 104.5,
        "takeover_time_ms": 320
      },
      "isSynthetic": true
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### 3.4 Event Context Timeline
- **Route:** `GET /api/events/{event_id}/timeline`
- **Summary:** Returns the target event, its timestamp, and related events and telemetry in a documented time window before and after it.
- **Path Parameters:**
  - `event_id` *(string, required)*: The target event identifier.
- **Query Parameters:**
  - `before_minutes` *(optional, integer, default: 30)*: Window lookback duration in minutes.
  - `after_minutes` *(optional, integer, default: 30)*: Window lookahead duration in minutes.
- **Response Schema:**
```typescript
interface EventTimelineDetailResponse {
  event: VehicleEvent;
  timestamp: string;
  timeWindow: {
    beforeMinutes: number;
    afterMinutes: number;
    windowStart: string;
    windowEnd: string;
  };
  relatedEvents: VehicleEvent[];
  relatedTelemetry: TelemetrySnapshot[];
  preEventTelemetry: TelemetrySnapshot[];   // Strictly ordered chronologically before the warning
  postEventTelemetry: TelemetrySnapshot[];  // Strictly ordered chronologically after the warning
  preEventEvents: VehicleEvent[];
  postEventEvents: VehicleEvent[];
  causationDisclaimer: string;              // Formal note that temporal sequence does not imply causation
}
```
- **Example Response:**
```json
{
  "event": {
    "id": "ev-synth-overheat-001",
    "vehicleId": "v-001",
    "type": "battery",
    "severity": "warning",
    "message": "Battery pack temperature exceeded safe threshold (58.6°C > 55.0°C) — active thermal liquid chiller cooling pump initiated at 100% capacity.",
    "timestamp": "2026-10-08T13:33:00Z",
    "metadata": {
      "peak_temperature_celsius": 58.6,
      "threshold_celsius": 55.0
    }
  },
  "timestamp": "2026-10-08T13:33:00Z",
  "timeWindow": {
    "beforeMinutes": 30,
    "afterMinutes": 30,
    "windowStart": "2026-10-08T13:03:00Z",
    "windowEnd": "2026-10-08T14:03:00Z"
  },
  "relatedEvents": [],
  "relatedTelemetry": [],
  "preEventTelemetry": [],
  "postEventTelemetry": [],
  "causationDisclaimer": "Temporal sequence and proximity within the observation window indicate correlation only; they do not establish causation or definitive root-cause fault origin."
}
```

---

### 3.5 Energy Analytics by Driving Mode
- **Route:** `GET /api/analytics/energy?group_by=driving_mode`
- **Summary:** Returns comparable city vs highway energy metrics with a normalized denominator (`kWh/100 km`), validation exclusion of anomalous measurements, and data-quality warnings.
- **Query Parameters:**
  - `group_by` *(optional, string, default: "driving_mode")*: Aggregation strategy (`driving_mode` or `hourly`).
  - `vehicle_id` *(optional, string)*: Filter to a specific vehicle.
- **Metric Definition:**
  $$\text{Consumption Rate} = \left(\frac{\text{Total Consumed kWh}}{\text{Total Distance km}}\right) \times 100 \quad [\text{kWh}/100\text{ km}]$$
- **Response Schema:**
```typescript
interface EnergyAnalyticsResponse {
  groupBy: "driving_mode";
  metricDefinition: string;
  breakdown: Array<{
    drivingMode: "city" | "highway";
    energyMetricUnit: "kWh/100 km";
    consumptionPer100km: number | null;
    totalEnergyConsumedKwh: number;
    totalEnergyRegeneratedKwh: number;
    netEnergyConsumedKwh: number;
    totalDistanceKm: number;
    averageSpeedKmh: number;
    efficiencyScorePercent: number;
  }>;
  summary: {
    total_distance_km: number;
    total_consumed_kwh: number;
    total_regenerated_kwh: number;
    net_consumed_kwh: number;
    fleet_avg_kwh_per_100km: number | null;
    valid_trips?: number;
    excluded_trips?: number;
  };
  warnings: string[];                       // Discarded near-zero distances, non-positive energy, sparse samples
  comparison: Record<string, unknown> | null; // Delta, ratio, efficiency comparison
}
```
- **Example Response:**
```json
{
  "groupBy": "driving_mode",
  "metricDefinition": "Standardized energy consumption rate measured in kilowatt-hours per 100 kilometers (kWh/100 km).",
  "breakdown": [
    {
      "drivingMode": "city",
      "energyMetricUnit": "kWh/100 km",
      "consumptionPer100km": 15.2,
      "totalEnergyConsumedKwh": 9.12,
      "totalEnergyRegeneratedKwh": 2.55,
      "netEnergyConsumedKwh": 6.57,
      "totalDistanceKm": 60.0,
      "averageSpeedKmh": 38.0,
      "efficiencyScorePercent": 28.0
    },
    {
      "drivingMode": "highway",
      "energyMetricUnit": "kWh/100 km",
      "consumptionPer100km": 20.5,
      "totalEnergyConsumedKwh": 21.52,
      "totalEnergyRegeneratedKwh": 2.58,
      "netEnergyConsumedKwh": 18.94,
      "totalDistanceKm": 105.0,
      "averageSpeedKmh": 88.0,
      "efficiencyScorePercent": 12.0
    }
  ],
  "summary": {
    "total_distance_km": 165.0,
    "total_consumed_kwh": 30.64,
    "total_regenerated_kwh": 5.13,
    "net_consumed_kwh": 25.51,
    "fleet_avg_kwh_per_100km": 18.57
  }
}
```

---

### 3.6 Natural Language Query Router
- **Route:** `POST /api/query`
- **Summary:** Processes natural language telemetry queries. Returns structured domain analysis, queried sources, and warnings (deterministic placeholder mode prior to LLM integration).
- **Request Headers:** `Content-Type: application/json`
- **Request Body Schema:**
```json
{
  "question": "What is the battery health and charge status?"
}
```
- **Response Schema:**
```typescript
interface QueryResponse {
  question: string;
  answer: string;
  intent: "battery_status" | "fault_diagnostics" | "fleet_status" | "energy_efficiency" | "general_telemetry";
  data: Record<string, unknown>;
  sources: string[];
  warnings: string[];
}
```
- **Example Response:**
```json
{
  "question": "What is the battery health and charge status?",
  "answer": "Fleet average battery state of charge is 58.2% with an average pack temperature of 25.6°C. There are 1 vehicle(s) below 20% charge threshold.",
  "intent": "battery_status",
  "data": {
    "average_battery_level_percent": 58.2,
    "average_pack_temperature_celsius": 25.6,
    "low_battery_count": 1,
    "low_battery_vehicles": ["v-005"]
  },
  "sources": [
    "vehicles",
    "telemetry"
  ],
  "warnings": [
    "LLM inference engine not integrated at this stage; response generated using deterministic telemetry query router."
  ]
}
```
