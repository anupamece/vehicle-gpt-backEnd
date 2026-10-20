import datetime
import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.vehicle import TelemetrySnapshot


class EventTypeEnum(str, Enum):
    DIAGNOSTIC = "diagnostic"
    ALERT = "alert"
    MAINTENANCE = "maintenance"
    GEOFENCE = "geofence"
    BATTERY = "battery"
    SYSTEM = "system"


class EventSeverityEnum(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventBase(BaseModel):
    vehicle_id: str = Field(..., serialization_alias="vehicleId", description="Referenced vehicle ID")
    type: EventTypeEnum = Field(..., description="Category of the event")
    severity: EventSeverityEnum = Field(..., description="Severity level")
    message: str = Field(..., description="Descriptive event message")
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        description="Event timestamp",
    )


class EventCreate(EventBase):
    id: str = Field(..., description="Unique event identifier")
    metadata_json: Optional[str] = Field(None, description="Optional raw JSON metadata string")


class EventResponse(BaseModel):
    id: str
    vehicle_id: str = Field(..., serialization_alias="vehicleId")
    trip_id: Optional[str] = Field(None, serialization_alias="tripId")
    related_event_id: Optional[str] = Field(None, serialization_alias="relatedEventId")
    dtc_code: Optional[str] = Field(None, serialization_alias="dtcCode")
    type: str
    severity: str
    message: str
    timestamp: datetime.datetime
    metadata: Optional[Dict[str, Any]] = None
    is_synthetic: bool = Field(True, serialization_alias="isSynthetic")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def filter_sqlalchemy_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if type(v).__name__ == "MetaData" or hasattr(v, "_tables"):
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return None


class PaginatedEventsResponse(BaseModel):
    """Paginated event list contract for GET /api/events."""

    items: List[EventResponse]
    total: int
    limit: int
    offset: int


class EventTimeWindow(BaseModel):
    before_minutes: int = Field(..., description="Minutes before target event included in window", serialization_alias="beforeMinutes")
    after_minutes: int = Field(..., description="Minutes after target event included in window", serialization_alias="afterMinutes")
    window_start: datetime.datetime = Field(..., description="Window start timestamp", serialization_alias="windowStart")
    window_end: datetime.datetime = Field(..., description="Window end timestamp", serialization_alias="windowEnd")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class EventTimelineDetailResponse(BaseModel):
    """Contract for GET /api/events/{event_id}/timeline."""

    event: EventResponse
    timestamp: datetime.datetime
    time_window: EventTimeWindow = Field(..., serialization_alias="timeWindow")
    related_events: List[EventResponse] = Field(..., serialization_alias="relatedEvents")
    related_telemetry: List[TelemetrySnapshot] = Field(..., serialization_alias="relatedTelemetry")
    pre_event_telemetry: List[TelemetrySnapshot] = Field(
        default_factory=list,
        description="Telemetry recordings ordered chronologically before the incident event",
        serialization_alias="preEventTelemetry",
    )
    post_event_telemetry: List[TelemetrySnapshot] = Field(
        default_factory=list,
        description="Telemetry recordings ordered chronologically after the incident event",
        serialization_alias="postEventTelemetry",
    )
    pre_event_events: List[EventResponse] = Field(
        default_factory=list,
        description="Related events occurring prior to the target event in the time window",
        serialization_alias="preEventEvents",
    )
    post_event_events: List[EventResponse] = Field(
        default_factory=list,
        description="Related events occurring after the target event in the time window",
        serialization_alias="postEventEvents",
    )
    causation_disclaimer: str = Field(
        "Temporal sequence and proximity within the observation window indicate correlation only; they do not establish causation or definitive root-cause fault origin.",
        description="Formal engineering caveat that temporal sequence does not imply causation",
        serialization_alias="causationDisclaimer",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class EventTimelineGroup(BaseModel):
    severity: str
    count: int
    events: List[EventResponse]
