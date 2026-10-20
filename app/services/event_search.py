"""Event Search and Diagnostic Timeline Service for VehicleGPT.

Provides deterministic search, multi-criteria filtering, predictable pagination,
and chronological time-window telemetry extraction for automotive events.
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, desc, asc, or_
from sqlalchemy.orm import Session

from app.db.models import EventModel, TelemetryModel
from app.schemas.events import (
    EventResponse,
    EventTimeWindow,
    EventTimelineDetailResponse,
)
from app.schemas.vehicle import TelemetrySnapshot

CAUSATION_DISCLAIMER = (
    "Temporal sequence and proximity within the observation window indicate correlation only; "
    "they do not establish causation or definitive root-cause fault origin. "
    "Sensor anomalies occurring prior to an alert must be validated via physical diagnostic testing."
)


def search_events_paginated(
    db: Session,
    vehicle_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
    query: Optional[str] = None,
    sort_by: str = "timestamp",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[EventModel], int]:
    """Search and filter events from the database with predictable sorting and pagination.

    Supports filtering ADAS disengagements, diagnostics, and battery events by date/time,
    severity, and text search across descriptions and DTC codes.
    """
    stmt = db.query(EventModel)

    if vehicle_id:
        stmt = stmt.filter(EventModel.vehicle_id == vehicle_id)
    if event_type and event_type.lower() != "all":
        stmt = stmt.filter(EventModel.type == event_type.lower())
    if severity and severity.lower() != "all":
        stmt = stmt.filter(EventModel.severity == severity.lower())
    if start_time:
        stmt = stmt.filter(EventModel.timestamp >= start_time)
    if end_time:
        stmt = stmt.filter(EventModel.timestamp <= end_time)
    if query:
        search_filter = or_(
            EventModel.message.ilike(f"%{query}%"),
            EventModel.dtc_code.ilike(f"%{query}%"),
            EventModel.id.ilike(f"%{query}%"),
        )
        stmt = stmt.filter(search_filter)

    total = stmt.count()

    # Predictable, deterministic sorting with secondary unique tie-breaker on ID
    is_asc = sort_order.lower() == "asc"
    if sort_by == "severity":
        order_clauses = [
            EventModel.severity.asc() if is_asc else EventModel.severity.desc(),
            EventModel.timestamp.desc(),
            EventModel.id.asc(),
        ]
    elif sort_by == "type":
        order_clauses = [
            EventModel.type.asc() if is_asc else EventModel.type.desc(),
            EventModel.timestamp.desc(),
            EventModel.id.asc(),
        ]
    else:  # default timestamp
        order_clauses = [
            EventModel.timestamp.asc() if is_asc else EventModel.timestamp.desc(),
            EventModel.id.asc() if is_asc else EventModel.id.desc(),
        ]

    items = stmt.order_by(*order_clauses).offset(offset).limit(limit).all()
    return items, total


def search_events(
    db: Session,
    vehicle_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[EventModel]:
    """Compatibility wrapper returning list of items without total count."""
    items, _ = search_events_paginated(
        db=db,
        vehicle_id=vehicle_id,
        event_type=event_type,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return items


def get_event_by_id(db: Session, event_id: str) -> Optional[EventModel]:
    """Retrieve a single event record by ID."""
    return db.query(EventModel).filter(EventModel.id == event_id).first()


def build_event_timeline(
    db: Session,
    event: EventModel,
    before_minutes: int = 30,
    after_minutes: int = 30,
) -> EventTimelineDetailResponse:
    """Build a complete chronological fault timeline around an event.

    Separates measurements before the warning from measurements after it,
    and includes an explicit engineering disclaimer that temporal correlation
    does not establish causation.
    """
    window_start = event.timestamp - datetime.timedelta(minutes=before_minutes)
    window_end = event.timestamp + datetime.timedelta(minutes=after_minutes)

    # Related events in window for same vehicle (excluding the target event itself), strictly ordered
    rel_event_records = (
        db.query(EventModel)
        .filter(
            EventModel.vehicle_id == event.vehicle_id,
            EventModel.id != event.id,
            EventModel.timestamp >= window_start,
            EventModel.timestamp <= window_end,
        )
        .order_by(EventModel.timestamp.asc(), EventModel.id.asc())
        .all()
    )

    # Related telemetry in window for same vehicle, strictly ordered chronologically
    rel_telem_records = (
        db.query(TelemetryModel)
        .filter(
            TelemetryModel.vehicle_id == event.vehicle_id,
            TelemetryModel.timestamp >= window_start,
            TelemetryModel.timestamp <= window_end,
        )
        .order_by(TelemetryModel.timestamp.asc())
        .all()
    )

    # Map telemetry and annotate phases (pre_warning, at_event, post_warning)
    all_telemetry: List[TelemetrySnapshot] = []
    pre_telemetry: List[TelemetrySnapshot] = []
    post_telemetry: List[TelemetrySnapshot] = []

    for t in rel_telem_records:
        if t.timestamp < event.timestamp:
            phase = "pre_warning"
        elif t.timestamp == event.timestamp:
            phase = "at_event"
        else:
            phase = "post_warning"

        snapshot = TelemetrySnapshot(
            timestamp=t.timestamp,
            trip_id=t.trip_id,
            speed_kmh=t.speed,
            battery_level_percent=t.battery_level,
            battery_temperature_celsius=t.battery_temperature,
            driving_mode=t.driving_mode,
            energy_consumed_kwh=t.energy_consumed,
            energy_regenerated_kwh=t.energy_regenerated,
            distance_km=t.distance_km,
            latitude=t.latitude,
            longitude=t.longitude,
            phase=phase,
            is_synthetic=t.is_synthetic,
        )
        all_telemetry.append(snapshot)
        if t.timestamp <= event.timestamp:
            pre_telemetry.append(snapshot)
        else:
            post_telemetry.append(snapshot)

    # Map related events and partition into pre/post
    all_events: List[EventResponse] = []
    pre_events: List[EventResponse] = []
    post_events: List[EventResponse] = []

    for e in rel_event_records:
        ev_resp = EventResponse.model_validate(e)
        all_events.append(ev_resp)
        if e.timestamp <= event.timestamp:
            pre_events.append(ev_resp)
        else:
            post_events.append(ev_resp)

    return EventTimelineDetailResponse(
        event=EventResponse.model_validate(event),
        timestamp=event.timestamp,
        time_window=EventTimeWindow(
            before_minutes=before_minutes,
            after_minutes=after_minutes,
            window_start=window_start,
            window_end=window_end,
        ),
        related_events=all_events,
        related_telemetry=all_telemetry,
        pre_event_telemetry=pre_telemetry,
        post_event_telemetry=post_telemetry,
        pre_event_events=pre_events,
        post_event_events=post_events,
        causation_disclaimer=CAUSATION_DISCLAIMER,
    )


def get_event_window_context(
    db: Session,
    event: EventModel,
    before_minutes: int = 30,
    after_minutes: int = 30,
) -> Tuple[datetime.datetime, datetime.datetime, List[EventModel], List[TelemetryModel]]:
    """Legacy compatibility helper returning raw tuples."""
    window_start = event.timestamp - datetime.timedelta(minutes=before_minutes)
    window_end = event.timestamp + datetime.timedelta(minutes=after_minutes)

    related_events = (
        db.query(EventModel)
        .filter(
            EventModel.vehicle_id == event.vehicle_id,
            EventModel.id != event.id,
            EventModel.timestamp >= window_start,
            EventModel.timestamp <= window_end,
        )
        .order_by(EventModel.timestamp.asc(), EventModel.id.asc())
        .all()
    )

    related_telemetry = (
        db.query(TelemetryModel)
        .filter(
            TelemetryModel.vehicle_id == event.vehicle_id,
            TelemetryModel.timestamp >= window_start,
            TelemetryModel.timestamp <= window_end,
        )
        .order_by(TelemetryModel.timestamp.asc())
        .all()
    )

    return window_start, window_end, related_events, related_telemetry
