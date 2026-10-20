"""Fault Timeline and Diagnostic Correlation Service for VehicleGPT.

Aggregates diagnostic trouble codes, warning alerts, and safety events
in chronological sequence while maintaining strict engineering rigor
regarding correlation vs causation.
"""

from collections import defaultdict
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from app.db.models import EventModel
from app.schemas.events import EventResponse, EventTimelineGroup

CAUSATION_NOTICE = (
    "Engineering Notice: Temporal sequence and proximity indicate empirical correlation only. "
    "Pre-fault sensor fluctuations and subsequent diagnostic codes must not be presumed to have a direct "
    "causal relationship without CAN bus trace verification or component bench isolation."
)


def get_fault_timeline(
    db: Session,
    vehicle_id: Optional[str] = None,
    limit: int = 50,
    chronological: bool = True,
) -> Dict[str, Any]:
    """Retrieve and structure critical and warning diagnostic faults for fleet diagnostics.

    Orders results predictably and attaches an engineering disclaimer separating
    temporal correlation from root-cause causation.
    """
    query = db.query(EventModel).filter(
        EventModel.severity.in_(["warning", "critical"])
    )
    if vehicle_id:
        query = query.filter(EventModel.vehicle_id == vehicle_id)

    order_clauses = [
        EventModel.timestamp.asc() if chronological else EventModel.timestamp.desc(),
        EventModel.id.asc(),
    ]
    events = query.order_by(*order_clauses).limit(limit).all()

    grouped_by_severity: Dict[str, List[EventModel]] = defaultdict(list)
    dtc_faults: List[Dict[str, Any]] = []

    for event in events:
        grouped_by_severity[event.severity].append(event)
        if event.dtc_code:
            dtc_faults.append(
                {
                    "event_id": event.id,
                    "dtc_code": event.dtc_code,
                    "severity": event.severity,
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                    "related_event_id": event.related_event_id,
                }
            )

    timeline_groups = [
        EventTimelineGroup(
            severity=severity,
            count=len(ev_list),
            events=[EventResponse.model_validate(e) for e in ev_list],
        )
        for severity, ev_list in grouped_by_severity.items()
    ]

    critical_count = len(grouped_by_severity.get("critical", []))
    warning_count = len(grouped_by_severity.get("warning", []))

    return {
        "total_faults": len(events),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "dtc_faults_count": len(dtc_faults),
        "dtc_faults": dtc_faults,
        "groups": timeline_groups,
        "causation_disclaimer": CAUSATION_NOTICE,
    }
