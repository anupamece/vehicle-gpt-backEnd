import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VehicleStatusEnum(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CHARGING = "charging"
    DRIVING = "driving"
    IDLE = "idle"


class VehicleBase(BaseModel):
    vin: str = Field(..., description="Vehicle Identification Number")
    make: str = Field(..., description="Vehicle Manufacturer")
    model: str = Field(..., description="Vehicle Model")
    year: int = Field(..., description="Manufacturing Year")
    status: VehicleStatusEnum = Field(default=VehicleStatusEnum.IDLE, description="Current operating status")
    battery_level: Optional[float] = Field(default=100.0, ge=0.0, le=100.0)
    odometer: Optional[float] = Field(default=0.0, ge=0.0)


class VehicleCreate(VehicleBase):
    id: str = Field(..., description="Unique vehicle identifier")


class TelemetrySnapshot(BaseModel):
    timestamp: Optional[datetime.datetime] = Field(None, description="Timestamp of telemetry recording")
    trip_id: Optional[str] = Field(None, description="Associated journey ID", serialization_alias="tripId")
    speed_kmh: Optional[float] = Field(None, description="Speed in km/h", serialization_alias="speedKmh")
    battery_level_percent: Optional[float] = Field(None, description="State of charge in % (0.0-100.0)", serialization_alias="batteryLevelPercent")
    battery_temperature_celsius: Optional[float] = Field(None, description="Battery temperature in °C", serialization_alias="batteryTemperatureCelsius")
    driving_mode: Optional[str] = Field(None, description="Driving mode (city, highway, eco, sport)", serialization_alias="drivingMode")
    energy_consumed_kwh: Optional[float] = Field(None, description="Energy consumed in kWh", serialization_alias="energyConsumedKwh")
    energy_regenerated_kwh: Optional[float] = Field(None, description="Energy regenerated in kWh", serialization_alias="energyRegeneratedKwh")
    distance_km: Optional[float] = Field(None, description="Incremental or segment distance in km", serialization_alias="distanceKm")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phase: Optional[str] = Field(None, description="'pre_warning', 'at_event', or 'post_warning' relative to incident event")
    is_synthetic: bool = Field(True, serialization_alias="isSynthetic")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class RecentEventCounts(BaseModel):
    info: int = Field(0, description="Count of info events in last 24h")
    warning: int = Field(0, description="Count of warning alerts in last 24h")
    critical: int = Field(0, description="Count of critical alerts in last 24h")
    total: int = Field(0, description="Total events in last 24h")


class VehicleSummaryResponse(BaseModel):
    """Stable contract for GET /api/vehicle/summary with explicit units."""

    vehicle_id: Optional[str] = Field(None, description="Unique vehicle ID", serialization_alias="vehicleId")
    vin: Optional[str] = Field(None, description="Vehicle Identification Number")
    make: Optional[str] = Field(None, description="Vehicle Manufacturer")
    model: Optional[str] = Field(None, description="Vehicle Model")
    year: Optional[int] = Field(None, description="Model year")
    status: Optional[str] = Field(None, description="Operating status (online, offline, charging, driving, idle)")
    battery_percentage: Optional[float] = Field(
        None,
        description="Battery state of charge. Unit: % (0.0 to 100.0)",
        serialization_alias="batteryPercentage",
    )
    battery_temperature: Optional[float] = Field(
        None,
        description="Battery pack temperature. Unit: °C (Celsius)",
        serialization_alias="batteryTemperature",
    )
    total_distance_km: Optional[float] = Field(
        None,
        description="Total cumulative distance travelled. Unit: km",
        serialization_alias="totalDistanceKm",
    )
    energy_consumption_kwh: Optional[float] = Field(
        None,
        description="Total cumulative energy consumed. Unit: kWh",
        serialization_alias="energyConsumptionKwh",
    )
    recent_event_counts: RecentEventCounts = Field(
        default_factory=RecentEventCounts,
        description="Recent event counts categorized by severity",
        serialization_alias="recentEventCounts",
    )
    latest_telemetry: Optional[TelemetrySnapshot] = Field(
        None,
        description="Latest recorded telemetry snapshot",
        serialization_alias="latestTelemetry",
    )
    last_measurement_time: Optional[datetime.datetime] = Field(
        None,
        description="Timestamp when the most recent telemetry measurement was recorded",
        serialization_alias="lastMeasurementTime",
    )
    is_live: bool = Field(
        False,
        description="Explicit flag distinguishing whether data is live telemetry (False for historical synthetic)",
        serialization_alias="isLive",
    )
    is_synthetic: bool = Field(
        True,
        description="Flag indicating whether data originated from synthetic simulation",
        serialization_alias="isSynthetic",
    )
    data_source: str = Field(
        "historical_simulation",
        description="Explicit data source origin: 'historical_simulation' or 'live_sensor_stream'",
        serialization_alias="dataSource",
    )
    data_quality_notes: Optional[str] = Field(
        None,
        description="Data quality notes, dropout indicators, or simulation caveats",
        serialization_alias="dataQualityNotes",
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class VehicleResponse(BaseModel):
    id: str
    vin: str
    make: str
    model: str
    year: int
    status: str
    battery_level: Optional[float] = Field(None, serialization_alias="batteryLevel")
    odometer: Optional[float] = None
    last_seen: datetime.datetime = Field(..., serialization_alias="lastSeen")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class DashboardStatsResponse(BaseModel):
    total_vehicles: int = Field(..., serialization_alias="totalVehicles")
    active_vehicles: int = Field(..., serialization_alias="activeVehicles")
    total_alerts: int = Field(..., serialization_alias="totalAlerts")
    avg_battery_level: float = Field(..., serialization_alias="avgBatteryLevel")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class DrivingModeEnergyMetric(BaseModel):
    driving_mode: str = Field(..., description="Driving mode name ('city' or 'highway')", serialization_alias="drivingMode")
    energy_metric_unit: str = Field("kWh/100 km", description="Standardized consumption metric unit", serialization_alias="energyMetricUnit")
    consumption_per_100km: Optional[float] = Field(
        None,
        description="Average energy consumed per 100 km. Unit: kWh/100 km",
        serialization_alias="consumptionPer100km",
    )
    total_energy_consumed_kwh: float = Field(
        ...,
        description="Total cumulative energy consumed. Unit: kWh",
        serialization_alias="totalEnergyConsumedKwh",
    )
    total_energy_regenerated_kwh: float = Field(
        ...,
        description="Total regenerative energy recovered. Unit: kWh",
        serialization_alias="totalEnergyRegeneratedKwh",
    )
    net_energy_consumed_kwh: float = Field(
        ...,
        description="Net energy consumed (consumed - regenerated). Unit: kWh",
        serialization_alias="netEnergyConsumedKwh",
    )
    total_distance_km: float = Field(
        ...,
        description="Total distance driven in this mode. Unit: km",
        serialization_alias="totalDistanceKm",
    )
    average_speed_kmh: float = Field(
        ...,
        description="Average vehicle speed in this mode. Unit: km/h",
        serialization_alias="averageSpeedKmh",
    )
    efficiency_score_percent: float = Field(
        ...,
        description="Regenerative braking energy recovery efficiency. Unit: %",
        serialization_alias="efficiencyScorePercent",
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class EnergyAnalyticsResponse(BaseModel):
    group_by: str = Field(..., description="Aggregation dimension ('driving_mode')", serialization_alias="groupBy")
    metric_definition: str = Field(
        "Standardized energy consumption rate measured in kilowatt-hours per 100 kilometers (kWh/100 km).",
        description="Formal definition of the normalized energy metric and denominator",
        serialization_alias="metricDefinition",
    )
    breakdown: List[DrivingModeEnergyMetric] = Field(..., description="Comparable driving mode energy metrics")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Fleet-level cumulative energy summary")
    warnings: List[str] = Field(
        default_factory=list,
        description="Data-quality warnings, excluded invalid trips, or sampling dropouts",
    )
    comparison: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Underlying comparative metrics between driving modes (delta, ratio, efficiency leader)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class EnergyDataPointResponse(BaseModel):
    timestamp: str
    consumed: float
    regenerated: float

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
