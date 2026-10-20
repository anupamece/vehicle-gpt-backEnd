-- VehicleGPT SQLite DDL Schema Definition
-- Synthetic Telemetry & Fleet Intelligence Database

CREATE TABLE IF NOT EXISTS vehicles (
    id VARCHAR(64) PRIMARY KEY,
    vin VARCHAR(32) UNIQUE NOT NULL,
    make VARCHAR(64) NOT NULL,
    model VARCHAR(64) NOT NULL,
    year INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'idle',
    battery_level REAL DEFAULT 100.0,
    battery_temperature REAL DEFAULT 25.0,
    odometer REAL DEFAULT 0.0,
    total_energy_kwh REAL DEFAULT 0.0,
    is_synthetic BOOLEAN NOT NULL DEFAULT 1,
    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles (vin);
CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles (status);

CREATE TABLE IF NOT EXISTS trips (
    id VARCHAR(64) PRIMARY KEY,
    vehicle_id VARCHAR(64) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    driving_mode VARCHAR(32) NOT NULL,
    distance_km REAL NOT NULL DEFAULT 0.0,
    energy_consumed_kwh REAL NOT NULL DEFAULT 0.0,
    energy_regenerated_kwh REAL NOT NULL DEFAULT 0.0,
    avg_speed_kmh REAL NOT NULL DEFAULT 0.0,
    is_synthetic BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trips_vehicle_id ON trips (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trips_start_time ON trips (start_time);
CREATE INDEX IF NOT EXISTS idx_trips_end_time ON trips (end_time);
CREATE INDEX IF NOT EXISTS idx_trips_driving_mode ON trips (driving_mode);
CREATE INDEX IF NOT EXISTS idx_trips_vehicle_start ON trips (vehicle_id, start_time);
CREATE INDEX IF NOT EXISTS idx_trips_mode_time ON trips (driving_mode, start_time);

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(64) PRIMARY KEY,
    vehicle_id VARCHAR(64) NOT NULL,
    trip_id VARCHAR(64),
    related_event_id VARCHAR(64),
    dtc_code VARCHAR(32),
    type VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    is_synthetic BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY (related_event_id) REFERENCES events(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_vehicle_id ON events (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_events_trip_id ON events (trip_id);
CREATE INDEX IF NOT EXISTS idx_events_related ON events (related_event_id);
CREATE INDEX IF NOT EXISTS idx_events_dtc_code ON events (dtc_code);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (type);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events (severity);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type_severity ON events (type, severity);
CREATE INDEX IF NOT EXISTS idx_events_vehicle_timestamp ON events (vehicle_id, timestamp);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id VARCHAR(64) NOT NULL,
    trip_id VARCHAR(64),
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    speed REAL,
    battery_level REAL,
    battery_temperature REAL,
    driving_mode VARCHAR(32) DEFAULT 'city',
    energy_consumed REAL NOT NULL DEFAULT 0.0,
    energy_regenerated REAL NOT NULL DEFAULT 0.0,
    distance_km REAL NOT NULL DEFAULT 0.0,
    latitude REAL,
    longitude REAL,
    is_synthetic BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle_id ON telemetry (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_trip_id ON telemetry (trip_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry (timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_mode ON telemetry (driving_mode);
CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle_timestamp ON telemetry (vehicle_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_trip_timestamp ON telemetry (trip_id, timestamp);
