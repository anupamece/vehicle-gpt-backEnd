import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.db.models import EventModel, TelemetryModel, VehicleModel
from app.schemas.vehicle import (
    DashboardStatsResponse,
    RecentEventCounts,
    TelemetrySnapshot,
    VehicleResponse,
    VehicleSummaryResponse,
)

router = APIRouter(tags=["Vehicles"])


@router.get(
    "/vehicle/summary",
    response_model=VehicleSummaryResponse,
    summary="Vehicle Telemetry & Diagnostics Summary",
)
@router.get(
    "/vehicles/summary",
    response_model=VehicleSummaryResponse,
    include_in_schema=False,
)
def get_vehicle_summary(
    vehicle_id: Optional[str] = Query(None, description="Optional target vehicle ID"),
    db: Session = Depends(get_db),
) -> VehicleSummaryResponse:
    """Return a typed response containing the selected vehicle's latest telemetry, battery temperature (°C),

    battery percentage (%), total distance (km), energy consumption (kWh), and recent event counts.
    If no vehicle or measurements are available, returns appropriate null values without fabricating live data.
    """
    vehicle_query = db.query(VehicleModel)
    if vehicle_id:
        vehicle = vehicle_query.filter(VehicleModel.id == vehicle_id).first()
        if not vehicle:
            # If a specific ID was explicitly requested and not found, return 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID '{vehicle_id}' not found",
            )
    else:
        # Default to first registered fleet vehicle
        vehicle = vehicle_query.first()

    if not vehicle:
        # Return typed empty summary when fleet has no registered vehicles
        return VehicleSummaryResponse()

    # Fetch latest telemetry snapshot for this vehicle
    latest_telemetry_record = (
        db.query(TelemetryModel)
        .filter(TelemetryModel.vehicle_id == vehicle.id)
        .order_by(desc(TelemetryModel.timestamp))
        .first()
    )

    # Compute recent event counts within the last 24 hours
    now = datetime.datetime.now(datetime.timezone.utc)
    since_24h = now - datetime.timedelta(hours=24)

    recent_events = (
        db.query(EventModel)
        .filter(
            EventModel.vehicle_id == vehicle.id,
            EventModel.timestamp >= since_24h,
        )
        .all()
    )

    info_count = sum(1 for e in recent_events if e.severity == "info")
    warning_count = sum(1 for e in recent_events if e.severity == "warning")
    critical_count = sum(1 for e in recent_events if e.severity == "critical")
    total_events = len(recent_events)

    latest_snapshot = None
    if latest_telemetry_record:
        latest_snapshot = TelemetrySnapshot(
            timestamp=latest_telemetry_record.timestamp,
            speed_kmh=latest_telemetry_record.speed,
            battery_level_percent=latest_telemetry_record.battery_level,
            battery_temperature_celsius=latest_telemetry_record.battery_temperature,
            driving_mode=latest_telemetry_record.driving_mode,
            energy_consumed_kwh=latest_telemetry_record.energy_consumed,
            energy_regenerated_kwh=latest_telemetry_record.energy_regenerated,
            latitude=latest_telemetry_record.latitude,
            longitude=latest_telemetry_record.longitude,
        )

    # Extract metrics with precedence: latest telemetry snapshot -> vehicle profile -> null
    battery_pct = (
        latest_snapshot.battery_level_percent
        if latest_snapshot and latest_snapshot.battery_level_percent is not None
        else vehicle.battery_level
    )
    battery_temp = (
        latest_snapshot.battery_temperature_celsius
        if latest_snapshot and latest_snapshot.battery_temperature_celsius is not None
        else vehicle.battery_temperature
    )

    last_measurement = (
        latest_telemetry_record.timestamp
        if latest_telemetry_record
        else vehicle.last_seen
    )
    is_synthetic = bool(vehicle.is_synthetic)
    is_live = False if is_synthetic else (vehicle.status in ("driving", "online", "charging"))
    data_source = "historical_simulation" if is_synthetic else "live_sensor_stream"
    data_quality_notes = (
        "Telemetry and diagnostic alerts derived from 30-day deterministic automotive simulation; "
        "measurements reflect simulated vehicle dynamics with occasional GPS/CAN dropouts."
        if is_synthetic
        else "Live CAN bus stream verified via powertrain control module."
    )

    return VehicleSummaryResponse(
        vehicle_id=vehicle.id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        status=vehicle.status,
        battery_percentage=battery_pct,
        battery_temperature=battery_temp,
        total_distance_km=vehicle.odometer,
        energy_consumption_kwh=vehicle.total_energy_kwh,
        recent_event_counts=RecentEventCounts(
            info=info_count,
            warning=warning_count,
            critical=critical_count,
            total=total_events,
        ),
        latest_telemetry=latest_snapshot,
        last_measurement_time=last_measurement,
        is_live=is_live,
        is_synthetic=is_synthetic,
        data_source=data_source,
        data_quality_notes=data_quality_notes,
    )


@router.get("/vehicles", response_model=List[VehicleResponse], summary="List all fleet vehicles")
def list_vehicles(db: Session = Depends(get_db)) -> List[VehicleResponse]:
    """Retrieve all registered vehicles with latest telemetry status."""
    vehicles = db.query(VehicleModel).all()
    return [VehicleResponse.model_validate(v) for v in vehicles]


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse, summary="Get vehicle by ID")
def get_vehicle(vehicle_id: str, db: Session = Depends(get_db)) -> VehicleResponse:
    """Retrieve telemetry profile for a specific vehicle by ID."""
    vehicle = db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with ID '{vehicle_id}' not found",
        )
    return VehicleResponse.model_validate(vehicle)


@router.get("/dashboard/stats", response_model=DashboardStatsResponse, summary="Dashboard Fleet KPI Stats")
@router.get("/vehicles/stats", response_model=DashboardStatsResponse, include_in_schema=False)
def get_dashboard_stats(db: Session = Depends(get_db)) -> DashboardStatsResponse:
    """Aggregate fleet KPIs including active count, open alerts, and average battery state of charge."""
    vehicles = db.query(VehicleModel).all()
    total_vehicles = len(vehicles)

    if total_vehicles == 0:
        return DashboardStatsResponse(
            total_vehicles=0,
            active_vehicles=0,
            total_alerts=0,
            avg_battery_level=0.0,
        )

    active_vehicles = sum(1 for v in vehicles if v.status in ("driving", "online", "charging"))
    total_alerts = db.query(EventModel).filter(EventModel.severity.in_(["warning", "critical"])).count()
    avg_battery = sum((v.battery_level or 0.0) for v in vehicles) / total_vehicles

    return DashboardStatsResponse(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        total_alerts=total_alerts,
        avg_battery_level=round(avg_battery, 1),
    )
