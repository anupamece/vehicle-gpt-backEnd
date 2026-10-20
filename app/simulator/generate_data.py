"""VehicleGPT Synthetic Data Generator.

Generates reproducible, multi-trip automotive telemetry covering 30 days with:
- Multiple city and highway trips with distinct trip IDs.
- Time-series speed, battery %, battery temperature, and energy readings.
- ADAS disengagement events with contextual descriptions and metadata.
- Diagnostic Trouble Codes (DTCs) and associated/related events.
- Documented battery overheating warning with telemetry before and after.
- Irregular sampling intervals (30-90s) and realistic missing measurements (GPS/sensor dropouts).
- Clear labeling as synthetic data across all database tables.

Usage:
  python -m app.simulator.generate_data --days 30 --seed 42 --reset
"""

import argparse
import datetime
import json
import logging
import random
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.database import SessionLocal, init_db
from app.db.models import EventModel, TelemetryModel, TripModel, VehicleModel

logger = logging.getLogger("vehicle_gpt.simulator")

DEFAULT_SEED = 42
DEFAULT_DAYS = 30

# Registered Fleet Vehicles (Synthetic profiles)
FLEET_VEHICLES = [
    {
        "id": "v-001",
        "vin": "1HGCM82633A004352",
        "make": "Tesla",
        "model": "Model 3 Long Range",
        "year": 2024,
        "status": "driving",
        "battery_level": 78.0,
        "battery_temperature": 29.5,
        "odometer": 14320.0,
        "total_energy_kwh": 2680.0,
    },
    {
        "id": "v-002",
        "vin": "5YJSA1E26HF000316",
        "make": "Rivian",
        "model": "R1T Adventure",
        "year": 2025,
        "status": "charging",
        "battery_level": 42.0,
        "battery_temperature": 34.0,
        "odometer": 8710.0,
        "total_energy_kwh": 2180.0,
    },
    {
        "id": "v-003",
        "vin": "WVWZZZ3CZWE012345",
        "make": "BMW",
        "model": "iX xDrive50",
        "year": 2025,
        "status": "online",
        "battery_level": 91.0,
        "battery_temperature": 24.2,
        "odometer": 3200.0,
        "total_energy_kwh": 710.0,
    },
    {
        "id": "v-004",
        "vin": "1N4AZ1CP5JC302958",
        "make": "Nissan",
        "model": "Ariya e-4ORCE",
        "year": 2024,
        "status": "idle",
        "battery_level": 65.0,
        "battery_temperature": 22.0,
        "odometer": 22100.0,
        "total_energy_kwh": 4120.0,
    },
    {
        "id": "v-005",
        "vin": "7SAYGDEE4PA000001",
        "make": "Hyundai",
        "model": "Ioniq 6 AWD",
        "year": 2025,
        "status": "offline",
        "battery_level": 15.0,
        "battery_temperature": 18.5,
        "odometer": 41600.0,
        "total_energy_kwh": 7890.0,
    },
]

# Standard Automotive Diagnostic Trouble Codes
DTC_CATALOG = [
    {
        "code": "C1A12",
        "type": "diagnostic",
        "severity": "warning",
        "message": "DTC C1A12: Forward Radar Sensor Alignment Fault — angle variance exceeds 1.5° threshold.",
        "component": "Forward Radar",
    },
    {
        "code": "P0A7F",
        "type": "diagnostic",
        "severity": "warning",
        "message": "DTC P0A7F: Hybrid/EV Battery Pack Degradation Rate Warning — internal resistance rise detected on block 4.",
        "component": "High Voltage Battery",
    },
    {
        "code": "C1A00",
        "type": "diagnostic",
        "severity": "info",
        "message": "DTC C1A00: Adaptive Cruise Control Optical Camera Temporary Obstruction — glare/grime alert.",
        "component": "Windshield Vision Sensor",
    },
    {
        "code": "U0100",
        "type": "diagnostic",
        "severity": "critical",
        "message": "DTC U0100: Lost CAN Bus Communication with Powertrain Control Module — bus latency exceeded 500ms.",
        "component": "CAN Bus Gateway",
    },
]

# ADAS Disengagement Scenarios
ADAS_DISENGAGEMENT_REASONS = [
    (
        "ADAS disengagement: lane marking fading detected in highway construction zone",
        {"trigger": "lane_marking_unclear", "speed_kmh": 92.0, "takeover_time_ms": 780},
    ),
    (
        "ADAS disengagement: driver steering wheel override torque applied (> 2.5 Nm)",
        {"trigger": "manual_driver_override", "speed_kmh": 104.5, "takeover_time_ms": 320},
    ),
    (
        "ADAS disengagement: forward vision camera sun glare temporary occlusion",
        {"trigger": "sensor_glare_occlusion", "speed_kmh": 85.0, "takeover_time_ms": 610},
    ),
    (
        "ADAS disengagement: adjacent cut-in vehicle safety margin threshold fallback",
        {"trigger": "proximity_safety_buffer", "speed_kmh": 78.0, "takeover_time_ms": 450},
    ),
]


def clear_synthetic_data(db: Session) -> None:
    """Safely clear existing synthetic data without touching potential production records."""
    logger.info("Clearing existing synthetic records from SQLite database...")
    db.query(TelemetryModel).filter(TelemetryModel.is_synthetic == True).delete()  # noqa: E712
    db.query(EventModel).filter(EventModel.is_synthetic == True).delete()  # noqa: E712
    db.query(TripModel).filter(TripModel.is_synthetic == True).delete()  # noqa: E712
    db.query(VehicleModel).filter(VehicleModel.is_synthetic == True).delete()  # noqa: E712
    db.commit()


def seed_vehicles(db: Session) -> Dict[str, VehicleModel]:
    """Seed or retrieve vehicle fleet records."""
    vehicle_map: Dict[str, VehicleModel] = {}
    for v_data in FLEET_VEHICLES:
        existing = db.query(VehicleModel).filter(VehicleModel.id == v_data["id"]).first()
        if not existing:
            v = VehicleModel(
                id=v_data["id"],
                vin=v_data["vin"],
                make=v_data["make"],
                model=v_data["model"],
                year=v_data["year"],
                status=v_data["status"],
                battery_level=v_data["battery_level"],
                battery_temperature=v_data["battery_temperature"],
                odometer=v_data["odometer"],
                total_energy_kwh=v_data["total_energy_kwh"],
                is_synthetic=True,
                last_seen=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(v)
            vehicle_map[v.id] = v
        else:
            vehicle_map[existing.id] = existing
    db.commit()
    return vehicle_map


def generate_synthetic_dataset(
    db: Session,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    reset: bool = False,
) -> Dict[str, int]:
    """Generate a reproducible, multi-trip synthetic dataset covering the specified number of days."""
    random.seed(seed)

    if reset:
        clear_synthetic_data(db)
    else:
        # Check if dataset is already present to prevent duplicate inflation
        existing_trips = db.query(TripModel).filter(TripModel.is_synthetic == True).count()  # noqa: E712
        if existing_trips > 0:
            logger.info("Synthetic dataset already present (%d trips). Skipping regeneration.", existing_trips)
            return {
                "vehicles": db.query(VehicleModel).count(),
                "trips": existing_trips,
                "telemetry_points": db.query(TelemetryModel).count(),
                "events": db.query(EventModel).count(),
            }

    # Ensure vehicles are present
    vehicles = seed_vehicles(db)
    primary_vehicle = vehicles["v-001"]

    now = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
    start_date = now - datetime.timedelta(days=days)

    total_trips = 0
    total_telemetry = 0
    total_events = 0

    # Overheating scenario assigned to day 18 of the simulation
    overheating_day = 18
    overheating_event_id = "ev-synth-overheat-001"
    overheating_injected = False

    # Iterate over each day in the simulation window
    for day_idx in range(days):
        current_date = start_date + datetime.timedelta(days=day_idx)
        is_weekend = current_date.weekday() >= 5

        # Define 2 to 3 trips per day
        trip_definitions: List[Tuple[str, int, int, str]] = []
        if not is_weekend:
            # Morning city commute: 07:30 to 08:15 (45 min)
            trip_definitions.append(("city", 7, 30, "morning_commute"))
            # Midday highway or customer transit: 13:00 to 14:00 (60 min)
            if day_idx % 2 == 0 or day_idx == overheating_day:
                trip_definitions.append(("highway", 13, 0, "regional_transit"))
            # Evening city return: 17:30 to 18:20 (50 min)
            trip_definitions.append(("city", 17, 30, "evening_commute"))
        else:
            # Weekend longer highway excursion: 10:30 to 12:30 (120 min)
            trip_definitions.append(("highway", 10, 30, "weekend_highway"))
            trip_definitions.append(("city", 16, 0, "weekend_local"))

        for mode, hour, minute, trip_label in trip_definitions:
            trip_start = current_date.replace(hour=hour, minute=minute)
            duration_minutes = random.randint(35, 65) if mode == "city" else random.randint(55, 90)
            trip_end = trip_start + datetime.timedelta(minutes=duration_minutes)

            trip_id = f"trip-{primary_vehicle.id}-{trip_start.strftime('%Y%m%d-%H%M')}"

            # Create trip record
            trip = TripModel(
                id=trip_id,
                vehicle_id=primary_vehicle.id,
                start_time=trip_start,
                end_time=trip_end,
                driving_mode=mode,
                is_synthetic=True,
            )
            db.add(trip)
            total_trips += 1

            # Determine whether this trip contains the battery overheating warning scenario
            is_overheating_trip = (day_idx == overheating_day and mode == "highway" and not overheating_injected)

            # Telemetry simulation variables
            t_curr = trip_start
            trip_distance = 0.0
            trip_consumed = 0.0
            trip_regen = 0.0
            speeds: List[float] = []

            # State variables
            soc = 85.0 - (day_idx % 5) * 4.0
            battery_temp = 24.0 + random.uniform(0.0, 4.0)

            sample_idx = 0
            while t_curr < trip_end:
                sample_idx += 1
                # Irregular sampling interval: 30 to 85 seconds
                dt_seconds = random.choice([32, 45, 58, 72, 85, 41, 64])
                t_curr += datetime.timedelta(seconds=dt_seconds)
                if t_curr > trip_end:
                    break

                # Speed model based on driving mode
                if mode == "city":
                    # Stop-and-go pattern (0 to 48 km/h)
                    speed = max(0.0, min(52.0, random.gauss(32.0, 14.0)))
                    if random.random() < 0.15:
                        speed = 0.0  # Traffic light stop
                else:
                    # Highway steady cruising (70 to 115 km/h)
                    speed = max(60.0, min(120.0, random.gauss(92.0, 9.0)))

                # Distance delta in km
                dist_delta = (speed * (dt_seconds / 3600.0))
                trip_distance += dist_delta
                speeds.append(speed)

                # Energy consumption & regeneration models
                # City: ~14.5-16.5 kWh/100km, ~25-30% regen recovery
                # Highway: ~19.5-22.5 kWh/100km, ~10-15% regen recovery
                base_rate = (15.2 if mode == "city" else 20.8) / 100.0  # kWh per km
                consumed_delta = round(dist_delta * base_rate * random.uniform(0.92, 1.08), 3)
                regen_ratio = 0.28 if mode == "city" else 0.12
                regen_delta = round(consumed_delta * regen_ratio * random.uniform(0.85, 1.15), 3)

                trip_consumed += consumed_delta
                trip_regen += regen_delta
                soc = max(5.0, soc - (consumed_delta * 1.1) + (regen_delta * 0.9))

                # Battery temperature dynamics
                if is_overheating_trip:
                    # Ramping up to overheating threshold (58.6°C) around middle of trip
                    trip_progress = (t_curr - trip_start).total_seconds() / (duration_minutes * 60.0)
                    if trip_progress < 0.5:
                        # Heating phase: climbs from 30°C to 58.6°C
                        battery_temp = 30.0 + (trip_progress / 0.5) * 28.6
                    else:
                        # Post-warning active liquid chilling cooling phase (exponential chiller drop to nominal 34°C)
                        cool_progress = min(1.0, max(0.0, (trip_progress - 0.5) / 0.5))
                        battery_temp = 34.0 + (58.6 - 34.0) * ((1.0 - cool_progress) ** 2.2)
                else:
                    # Normal thermal behavior: slight warming with ambient cooling (23°C - 33°C)
                    temp_drift = (speed / 100.0) * 0.4 - 0.1
                    battery_temp = max(18.0, min(36.0, battery_temp + temp_drift))

                # Introduce realistic occasional missing measurements
                telemetry_speed: Optional[float] = round(speed, 1)
                telemetry_lat: Optional[float] = round(37.7749 + (sample_idx * 0.0008), 5)
                telemetry_lng: Optional[float] = round(-122.4194 + (sample_idx * 0.0006), 5)
                telemetry_temp: Optional[float] = round(battery_temp, 1)

                # 1.5% chance of GPS dropout (tunnel/urban canyon)
                if random.random() < 0.015:
                    telemetry_lat = None
                    telemetry_lng = None

                # 1.0% chance of CAN sensor polling timeout
                if random.random() < 0.01:
                    telemetry_speed = None

                # Create Telemetry Record
                telem_point = TelemetryModel(
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    timestamp=t_curr,
                    speed=telemetry_speed,
                    battery_level=round(soc, 1),
                    battery_temperature=telemetry_temp,
                    driving_mode=mode,
                    energy_consumed=consumed_delta,
                    energy_regenerated=regen_delta,
                    distance_km=round(dist_delta, 3),
                    latitude=telemetry_lat,
                    longitude=telemetry_lng,
                    is_synthetic=True,
                )
                db.add(telem_point)
                total_telemetry += 1

            # Update aggregated trip metrics
            trip.distance_km = round(trip_distance, 2)
            trip.energy_consumed_kwh = round(trip_consumed, 2)
            trip.energy_regenerated_kwh = round(trip_regen, 2)
            trip.avg_speed_kmh = round(sum(speeds) / len(speeds), 1) if speeds else 0.0

            # ----------------------------------------------------
            # In-Trip Event Injections
            # ----------------------------------------------------

            # 1. Battery Overheating Warning Event (exactly once on Day 18)
            if is_overheating_trip:
                overheat_timestamp = trip_start + datetime.timedelta(minutes=int(duration_minutes * 0.5))
                overheat_event = EventModel(
                    id=overheating_event_id,
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    type="battery",
                    severity="warning",
                    message="Battery pack temperature exceeded safe threshold (58.6°C > 55.0°C) — active thermal liquid chiller cooling pump initiated at 100% capacity.",
                    timestamp=overheat_timestamp,
                    dtc_code="P0A12",
                    is_synthetic=True,
                    metadata_json=json.dumps(
                        {
                            "peak_temperature_celsius": 58.6,
                            "threshold_celsius": 55.0,
                            "cooling_pump_rpm": 4200,
                            "scenario": "battery_overheating_warning",
                            "data_origin": "synthetic_generator",
                        }
                    ),
                )
                db.add(overheat_event)
                total_events += 1

                # Resolution event 18 minutes later linking back via related_event_id
                resolved_timestamp = overheat_timestamp + datetime.timedelta(minutes=18)
                resolve_event = EventModel(
                    id="ev-synth-overheat-resolved",
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    related_event_id=overheating_event_id,
                    type="battery",
                    severity="info",
                    message="Battery pack temperature returned to nominal range (34.0°C) — cooling chiller reverted to standard duty cycle.",
                    timestamp=resolved_timestamp,
                    dtc_code=None,
                    is_synthetic=True,
                    metadata_json=json.dumps(
                        {
                            "stable_temperature_celsius": 34.0,
                            "resolved_event_id": overheating_event_id,
                            "cooling_pump_rpm": 1100,
                            "data_origin": "synthetic_generator",
                        }
                    ),
                )
                db.add(resolve_event)
                total_events += 1
                overheating_injected = True

            # 2. ADAS Disengagement Events (regularly on highway cruising trips)
            if mode == "highway" and (day_idx % 2 == 0 or day_idx % 3 == 0):
                msg, meta = random.choice(ADAS_DISENGAGEMENT_REASONS)
                adas_timestamp = trip_start + datetime.timedelta(minutes=random.randint(10, duration_minutes - 10))
                adas_event = EventModel(
                    id=f"ev-adas-{day_idx:02d}-{hour:02d}",
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    type="adas_disengagement",
                    severity="warning" if "override" in msg else "info",
                    message=msg,
                    timestamp=adas_timestamp,
                    dtc_code=None,
                    is_synthetic=True,
                    metadata_json=json.dumps({**meta, "trip_id": trip_id, "data_origin": "synthetic_generator"}),
                )
                db.add(adas_event)
                total_events += 1

            # 3. Diagnostic Trouble Codes (DTCs) and Associated Follow-up Events
            if day_idx in [5, 12, 22] and hour == 7:
                dtc_spec = DTC_CATALOG[(day_idx // 5) % len(DTC_CATALOG)]
                dtc_timestamp = trip_start + datetime.timedelta(minutes=random.randint(5, duration_minutes - 5))
                primary_dtc_id = f"ev-dtc-{dtc_spec['code']}-{day_idx:02d}"

                # Primary DTC fault event
                dtc_event = EventModel(
                    id=primary_dtc_id,
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    type=dtc_spec["type"],
                    severity=dtc_spec["severity"],
                    message=dtc_spec["message"],
                    dtc_code=dtc_spec["code"],
                    timestamp=dtc_timestamp,
                    is_synthetic=True,
                    metadata_json=json.dumps(
                        {
                            "dtc_code": dtc_spec["code"],
                            "subsystem": dtc_spec["component"],
                            "mil_status": "illuminated",
                            "data_origin": "synthetic_generator",
                        }
                    ),
                )
                db.add(dtc_event)
                total_events += 1

                # Associated follow-up diagnostic telemetry scan event
                followup_event = EventModel(
                    id=f"ev-dtc-followup-{dtc_spec['code']}-{day_idx:02d}",
                    vehicle_id=primary_vehicle.id,
                    trip_id=trip_id,
                    related_event_id=primary_dtc_id,
                    type="diagnostic",
                    severity="info",
                    message=f"Diagnostic snapshot confirmed freeze-frame telemetry for DTC {dtc_spec['code']}.",
                    dtc_code=dtc_spec["code"],
                    timestamp=dtc_timestamp + datetime.timedelta(minutes=5),
                    is_synthetic=True,
                    metadata_json=json.dumps(
                        {
                            "parent_event_id": primary_dtc_id,
                            "freeze_frame_recorded": True,
                            "data_origin": "synthetic_generator",
                        }
                    ),
                )
                db.add(followup_event)
                total_events += 1

        # Commit batches per day to manage SQLite transaction size
        db.commit()

    logger.info(
        "Successfully generated synthetic dataset: %d trips, %d telemetry snapshots, %d events across %d days.",
        total_trips,
        total_telemetry,
        total_events,
        days,
    )
    return {
        "vehicles": len(vehicles),
        "trips": total_trips,
        "telemetry_points": total_telemetry,
        "events": total_events,
    }


def seed_mock_data(db: Session, force: bool = False) -> None:
    """Wrapper function preserving compatibility with app startup lifecycle."""
    generate_synthetic_dataset(db=db, days=DEFAULT_DAYS, seed=DEFAULT_SEED, reset=force)


def main():
    """CLI entrypoint for generating synthetic telemetry."""
    parser = argparse.ArgumentParser(description="VehicleGPT Synthetic Telemetry Generator")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Number of days to simulate (default: 30)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--reset", action="store_true", help="Clear existing synthetic records before regenerating")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        stats = generate_synthetic_dataset(db=db, days=args.days, seed=args.seed, reset=args.reset)
        print("\n" + "=" * 60)
        print("VehicleGPT Synthetic Telemetry Generation Complete")
        print("=" * 60)
        print(f"Days Simulated:     {args.days}")
        print(f"Random Seed:        {args.seed}")
        print(f"Vehicles Seeded:    {stats['vehicles']}")
        print(f"Trips Created:      {stats['trips']}")
        print(f"Telemetry Points:   {stats['telemetry_points']}")
        print(f"Events Generated:   {stats['events']}")
        print("NOTE: All records are strictly synthetic test data.")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
