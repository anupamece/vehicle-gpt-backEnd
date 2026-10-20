import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VehicleModel(Base):
    """SQLAlchemy model for connected fleet vehicles."""

    __tablename__ = "vehicles"

    id = Column(String(64), primary_key=True, index=True)
    vin = Column(String(32), unique=True, index=True, nullable=False)
    make = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    year = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="idle")  # online, offline, charging, driving, idle
    battery_level = Column(Float, nullable=True, default=100.0)  # Unit: % (0-100)
    battery_temperature = Column(Float, nullable=True, default=25.0)  # Unit: °C
    odometer = Column(Float, nullable=True, default=0.0)  # Unit: km
    total_energy_kwh = Column(Float, nullable=True, default=0.0)  # Unit: kWh
    is_synthetic = Column(Boolean, nullable=False, default=True)  # Clearly labels synthetic records
    last_seen = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    trips = relationship("TripModel", back_populates="vehicle", cascade="all, delete-orphan")
    events = relationship("EventModel", back_populates="vehicle", cascade="all, delete-orphan")
    telemetry = relationship("TelemetryModel", back_populates="vehicle", cascade="all, delete-orphan")


class TripModel(Base):
    """SQLAlchemy model representing individual city or highway driving journeys."""

    __tablename__ = "trips"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "trip-v001-20261001-0800"
    vehicle_id = Column(String(64), ForeignKey("vehicles.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    driving_mode = Column(String(32), nullable=False)  # "city", "highway"
    distance_km = Column(Float, nullable=False, default=0.0)  # Unit: km
    energy_consumed_kwh = Column(Float, nullable=False, default=0.0)  # Unit: kWh
    energy_regenerated_kwh = Column(Float, nullable=False, default=0.0)  # Unit: kWh
    avg_speed_kmh = Column(Float, nullable=False, default=0.0)  # Unit: km/h
    is_synthetic = Column(Boolean, nullable=False, default=True)

    # Relationships
    vehicle = relationship("VehicleModel", back_populates="trips")
    telemetry = relationship("TelemetryModel", back_populates="trip", cascade="all, delete-orphan")
    events = relationship("EventModel", back_populates="trip")

    __table_args__ = (
        Index("idx_trips_vehicle_id", "vehicle_id"),
        Index("idx_trips_start_time", "start_time"),
        Index("idx_trips_end_time", "end_time"),
        Index("idx_trips_driving_mode", "driving_mode"),
        Index("idx_trips_vehicle_start", "vehicle_id", "start_time"),
    )


class EventModel(Base):
    """SQLAlchemy model for vehicle telemetry events, diagnostics, ADAS disengagements, and alerts."""

    __tablename__ = "events"

    id = Column(String(64), primary_key=True, index=True)
    vehicle_id = Column(String(64), ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(String(64), ForeignKey("trips.id"), nullable=True)
    related_event_id = Column(String(64), ForeignKey("events.id"), nullable=True)
    dtc_code = Column(String(32), nullable=True)  # Diagnostic Trouble Code e.g. "P0A7F"
    type = Column(String(32), nullable=False)  # diagnostic, alert, adas_disengagement, battery, etc.
    severity = Column(String(32), nullable=False)  # info, warning, critical
    message = Column(Text, nullable=False)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    metadata_json = Column(Text, nullable=True)  # JSON-encoded extra payload
    is_synthetic = Column(Boolean, nullable=False, default=True)

    # Relationships
    vehicle = relationship("VehicleModel", back_populates="events")
    trip = relationship("TripModel", back_populates="events")
    related_event = relationship("EventModel", remote_side=[id], backref="associated_events")

    __table_args__ = (
        Index("idx_events_vehicle_id", "vehicle_id"),
        Index("idx_events_timestamp", "timestamp"),
        Index("idx_events_type", "type"),
        Index("idx_events_severity", "severity"),
        Index("idx_events_type_severity", "type", "severity"),
        Index("idx_events_related", "related_event_id"),
        Index("idx_events_trip_id", "trip_id"),
        Index("idx_events_dtc_code", "dtc_code"),
    )


class TelemetryModel(Base):
    """SQLAlchemy model for high-frequency telemetry snapshots."""

    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(64), ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(String(64), ForeignKey("trips.id"), nullable=True)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    speed = Column(Float, nullable=True)  # Unit: km/h (nullable for occasional sensor/GPS dropout)
    battery_level = Column(Float, nullable=True)  # Unit: % (0-100)
    battery_temperature = Column(Float, nullable=True)  # Unit: °C
    driving_mode = Column(String(32), nullable=True)  # "city", "highway"
    energy_consumed = Column(Float, nullable=False, default=0.0)  # Unit: kWh
    energy_regenerated = Column(Float, nullable=False, default=0.0)  # Unit: kWh
    distance_km = Column(Float, nullable=False, default=0.0)  # Unit: km
    latitude = Column(Float, nullable=True)  # Unit: decimal degrees
    longitude = Column(Float, nullable=True)  # Unit: decimal degrees
    is_synthetic = Column(Boolean, nullable=False, default=True)

    # Relationships
    vehicle = relationship("VehicleModel", back_populates="telemetry")
    trip = relationship("TripModel", back_populates="telemetry")

    __table_args__ = (
        Index("idx_telemetry_vehicle_id", "vehicle_id"),
        Index("idx_telemetry_trip_id", "trip_id"),
        Index("idx_telemetry_timestamp", "timestamp"),
        Index("idx_telemetry_mode", "driving_mode"),
        Index("idx_telemetry_vehicle_timestamp", "vehicle_id", "timestamp"),
        Index("idx_telemetry_trip_timestamp", "trip_id", "timestamp"),
    )
