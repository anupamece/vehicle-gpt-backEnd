import json
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import EventModel, TelemetryModel, TripModel, VehicleModel
from app.simulator.generate_data import clear_synthetic_data, generate_synthetic_dataset


@pytest.fixture(scope="module")
def sim_db() -> Session:
    """Create a dedicated in-memory database for testing the synthetic generator."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_database_initialization_and_indexes(sim_db: Session):
    """Verify that all tables and required performance indexes are properly created."""
    inspector = inspect(sim_db.bind)
    table_names = inspector.get_table_names()

    assert "vehicles" in table_names
    assert "trips" in table_names
    assert "events" in table_names
    assert "telemetry" in table_names

    # Verify event indexes
    event_indexes = [idx["name"] for idx in inspector.get_indexes("events")]
    assert "idx_events_timestamp" in event_indexes
    assert "idx_events_related" in event_indexes
    assert "idx_events_type_severity" in event_indexes
    assert "idx_events_trip_id" in event_indexes or "idx_events_trip" in event_indexes

    # Verify telemetry indexes
    telemetry_indexes = [idx["name"] for idx in inspector.get_indexes("telemetry")]
    assert "idx_telemetry_timestamp" in telemetry_indexes
    assert "idx_telemetry_trip_id" in telemetry_indexes


def test_synthetic_generation_and_labeling(sim_db: Session):
    """Verify dataset generation covering multiple city & highway trips, labeled as synthetic."""
    stats = generate_synthetic_dataset(db=sim_db, days=30, seed=42, reset=True)

    assert stats["trips"] > 40
    assert stats["telemetry_points"] > 1000
    assert stats["events"] > 10

    # Verify that all generated rows are explicitly marked as synthetic
    assert sim_db.query(VehicleModel).filter(VehicleModel.is_synthetic == True).count() > 0  # noqa: E712
    assert sim_db.query(TripModel).filter(TripModel.is_synthetic == False).count() == 0  # noqa: E712
    assert sim_db.query(TelemetryModel).filter(TelemetryModel.is_synthetic == False).count() == 0  # noqa: E712
    assert sim_db.query(EventModel).filter(EventModel.is_synthetic == False).count() == 0  # noqa: E712

    # Verify driving mode distribution contains both city and highway
    modes = {t.driving_mode for t in sim_db.query(TripModel).all()}
    assert "city" in modes
    assert "highway" in modes


def test_event_relationships_and_dtcs(sim_db: Session):
    """Verify foreign key linkages: related_event_id, trip_id, and DTC assignments."""
    events_with_related = sim_db.query(EventModel).filter(EventModel.related_event_id.isnot(None)).all()
    assert len(events_with_related) > 0

    for ev in events_with_related:
        parent_event = sim_db.query(EventModel).filter(EventModel.id == ev.related_event_id).first()
        assert parent_event is not None
        assert parent_event.vehicle_id == ev.vehicle_id

    # Verify Diagnostic Trouble Codes (DTCs) exist
    dtc_events = sim_db.query(EventModel).filter(EventModel.dtc_code.isnot(None)).all()
    assert len(dtc_events) >= 3
    dtc_codes = {e.dtc_code for e in dtc_events}
    assert any(c.startswith("C1") or c.startswith("P0") or c.startswith("U0") for c in dtc_codes)


def test_battery_overheating_scenario_with_thermal_history(sim_db: Session):
    """Verify the documented battery overheating warning scenario and telemetry curve before/after."""
    overheat_event = sim_db.query(EventModel).filter(EventModel.id == "ev-synth-overheat-001").first()
    assert overheat_event is not None
    assert overheat_event.severity == "warning"
    assert overheat_event.type == "battery"
    assert "58.6°C" in overheat_event.message

    # Verify telemetry before the overheating event (temperatures rising towards ~58.6°C)
    pre_telemetry = (
        sim_db.query(TelemetryModel)
        .filter(
            TelemetryModel.vehicle_id == overheat_event.vehicle_id,
            TelemetryModel.trip_id == overheat_event.trip_id,
            TelemetryModel.timestamp <= overheat_event.timestamp,
        )
        .order_by(TelemetryModel.timestamp.desc())
        .limit(10)
        .all()
    )
    assert len(pre_telemetry) > 0
    max_pre_temp = max(t.battery_temperature for t in pre_telemetry if t.battery_temperature is not None)
    assert max_pre_temp >= 55.0  # Exceeded 55°C threshold

    # Verify telemetry after the overheating event (temperatures cooling down towards ~34°C)
    post_telemetry = (
        sim_db.query(TelemetryModel)
        .filter(
            TelemetryModel.vehicle_id == overheat_event.vehicle_id,
            TelemetryModel.trip_id == overheat_event.trip_id,
            TelemetryModel.timestamp > overheat_event.timestamp,
        )
        .order_by(TelemetryModel.timestamp.asc())
        .limit(40)
        .all()
    )
    assert len(post_telemetry) > 0
    min_post_temp = min(t.battery_temperature for t in post_telemetry if t.battery_temperature is not None)
    assert min_post_temp < 40.0  # Cooled down significantly

    # Verify resolution event exists and links back to the original overheat warning
    resolution_event = (
        sim_db.query(EventModel)
        .filter(EventModel.related_event_id == overheat_event.id)
        .first()
    )
    assert resolution_event is not None
    assert resolution_event.severity == "info"
    assert "returned to nominal range" in resolution_event.message.lower()


def test_adas_disengagements(sim_db: Session):
    """Verify ADAS disengagement events have timestamps, descriptions, and contextual metadata."""
    adas_events = sim_db.query(EventModel).filter(EventModel.type == "adas_disengagement").all()
    assert len(adas_events) > 0

    for adas_ev in adas_events:
        assert adas_ev.message.startswith("ADAS disengagement:")
        assert adas_ev.trip_id is not None
        assert adas_ev.metadata_json is not None
        meta = json.loads(adas_ev.metadata_json)
        assert "trigger" in meta
        assert meta["data_origin"] == "synthetic_generator"


def test_missing_measurements_and_irregular_intervals(sim_db: Session):
    """Verify occasional null sensor readings (GPS dropouts) and irregular sampling deltas."""
    # Check for occasional GPS dropout
    gps_dropouts = (
        sim_db.query(TelemetryModel)
        .filter(TelemetryModel.latitude.is_(None))
        .count()
    )
    assert gps_dropouts > 0

    # Check for irregular sampling intervals between consecutive readings
    sample_trip = sim_db.query(TripModel).first()
    readings = (
        sim_db.query(TelemetryModel)
        .filter(TelemetryModel.trip_id == sample_trip.id)
        .order_by(TelemetryModel.timestamp.asc())
        .limit(10)
        .all()
    )
    assert len(readings) >= 5
    intervals = []
    for i in range(1, len(readings)):
        delta = (readings[i].timestamp - readings[i - 1].timestamp).total_seconds()
        intervals.append(delta)

    # Intervals must vary (e.g. 32s, 45s, 58s rather than a constant 60s)
    assert len(set(intervals)) > 1


def test_reproducibility_with_fixed_seed(sim_db: Session):
    """Verify that running with fixed seed 42 produces identical deterministic output."""
    # Generate run 1
    stats1 = generate_synthetic_dataset(db=sim_db, days=5, seed=99, reset=True)
    trip_ids1 = [t.id for t in sim_db.query(TripModel).order_by(TripModel.id).all()]

    # Generate run 2 with same seed
    stats2 = generate_synthetic_dataset(db=sim_db, days=5, seed=99, reset=True)
    trip_ids2 = [t.id for t in sim_db.query(TripModel).order_by(TripModel.id).all()]

    assert stats1 == stats2
    assert trip_ids1 == trip_ids2

    # Rerun without reset does not duplicate
    stats_rerun = generate_synthetic_dataset(db=sim_db, days=5, seed=99, reset=False)
    assert stats_rerun["trips"] == stats2["trips"]
