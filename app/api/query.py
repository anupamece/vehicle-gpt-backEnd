from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_router import route_natural_language_query

router = APIRouter(tags=["Query & Assistant"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Natural language telemetry query endpoint",
)
def process_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
) -> QueryResponse:
    """Analyze and answer natural language questions about vehicle telemetry,

    battery health, diagnostic faults, and energy analytics.
    """
    return route_natural_language_query(
        db=db, question=payload.question, vehicle_id=payload.vehicle_id
    )


@router.post(
    "/assistant/chat",
    response_model=QueryResponse,
    summary="VehicleGPT assistant chat endpoint (Frontend compatibility alias)",
    include_in_schema=False,
)
def chat_assistant(
    payload: QueryRequest,
    db: Session = Depends(get_db),
) -> QueryResponse:
    """Conversational endpoint compatible with frontend chat panels."""
    return route_natural_language_query(
        db=db, question=payload.question, vehicle_id=payload.vehicle_id
    )
