import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.events import (
    EventResponse,
    EventTimeWindow,
    EventTimelineDetailResponse,
    PaginatedEventsResponse,
)
from app.schemas.vehicle import TelemetrySnapshot
from app.services.event_search import (
    build_event_timeline,
    get_event_by_id,
    get_event_window_context,
    search_events_paginated,
)
from app.services.fault_timeline import get_fault_timeline

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=PaginatedEventsResponse, summary="Paginated list of vehicle events")
def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event category (diagnostic, alert, adas_disengagement, battery, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, critical)"),
    start_time: Optional[str] = Query(None, description="Filter events on or after ISO timestamp"),
    end_time: Optional[str] = Query(None, description="Filter events on or before ISO timestamp"),
    vehicle_id: Optional[str] = Query(None, description="Filter by vehicle ID"),
    query: Optional[str] = Query(None, description="Keyword search across descriptions and DTC codes"),
    sort_by: str = Query("timestamp", description="Sort field: timestamp, severity, type"),
    sort_order: str = Query("desc", description="Sort direction: desc or asc"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> PaginatedEventsResponse:
    """Retrieve paginated vehicle telemetry events with multi-criteria filtering and predictable sorting."""
    parsed_start: Optional[datetime.datetime] = None
    parsed_end: Optional[datetime.datetime] = None

    if start_time:
        try:
            cleaned_start = start_time.replace(" ", "+")
            parsed_start = datetime.datetime.fromisoformat(cleaned_start)
        except Exception:
            pass

    if end_time:
        try:
            cleaned_end = end_time.replace(" ", "+")
            parsed_end = datetime.datetime.fromisoformat(cleaned_end)
        except Exception:
            pass

    items, total = search_events_paginated(
        db=db,
        vehicle_id=vehicle_id,
        event_type=event_type,
        severity=severity,
        start_time=parsed_start,
        end_time=parsed_end,
        query=query,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return PaginatedEventsResponse(
        items=[EventResponse.model_validate(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{event_id}/timeline",
    response_model=EventTimelineDetailResponse,
    summary="Event Context Timeline",
)
def get_event_timeline(
    event_id: str,
    before_minutes: int = Query(30, ge=1, le=1440, description="Minutes before event to query"),
    after_minutes: int = Query(30, ge=1, le=1440, description="Minutes after event to query"),
    db: Session = Depends(get_db),
) -> EventTimelineDetailResponse:
    """Return the selected event, its timestamp, and related telemetry and events

    in a documented time window before and after it.
    Chronologically partitions telemetry and events into pre-warning and post-warning phases,
    with an explicit disclaimer that temporal correlation does not prove causation.
    """
    event = get_event_by_id(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found",
        )

    return build_event_timeline(
        db=db,
        event=event,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
    )


@router.get("/timeline/faults", summary="Fault timeline overview")
def fault_timeline(
    vehicle_id: Optional[str] = Query(None, description="Optional vehicle ID filter"),
    limit: int = Query(50, ge=1, le=200, description="Max fault events to return"),
    chronological: bool = Query(True, description="Order chronologically (oldest first) if True"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve aggregated fault timeline grouped by warning and critical severities."""
    return get_fault_timeline(db=db, vehicle_id=vehicle_id, limit=limit, chronological=chronological)


@router.get("/{event_id}", response_model=EventResponse, summary="Get event by ID")
def get_event(event_id: str, db: Session = Depends(get_db)) -> EventResponse:
    """Retrieve details for a single telemetry event."""
    event = get_event_by_id(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found",
        )
    return EventResponse.model_validate(event)
