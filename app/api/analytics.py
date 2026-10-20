from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.vehicle import EnergyAnalyticsResponse, EnergyDataPointResponse
from app.services.energy_analysis import (
    analyze_energy_by_driving_mode,
    analyze_energy_telemetry,
    calculate_fleet_efficiency,
)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/analytics/energy",
    summary="Energy Consumption and Regeneration Metrics",
    response_model=Union[EnergyAnalyticsResponse, List[EnergyDataPointResponse]],
)
def get_energy_analytics(
    group_by: Optional[str] = Query(
        "driving_mode",
        description="Aggregation dimension: 'driving_mode' for city/highway kWh/100km metrics, or 'hourly' for time-series",
    ),
    vehicle_id: Optional[str] = Query(None, description="Optional vehicle ID filter"),
    db: Session = Depends(get_db),
):
    """Retrieve energy analytics. When group_by=driving_mode, returns comparable city and highway

    energy metrics normalized to kWh/100 km.
    """
    if group_by == "driving_mode":
        return analyze_energy_by_driving_mode(db=db, vehicle_id=vehicle_id)
    # Fallback to hourly time series points
    return analyze_energy_telemetry(db=db, vehicle_id=vehicle_id)


@router.get(
    "/energy",
    response_model=List[EnergyDataPointResponse],
    summary="Energy telemetry time series (Frontend Dashboard alias)",
    include_in_schema=False,
)
def get_energy_series(
    vehicle_id: Optional[str] = Query(None, description="Optional vehicle ID filter"),
    db: Session = Depends(get_db),
) -> List[EnergyDataPointResponse]:
    """Time-series telemetry points for dashboard energy area charts."""
    return analyze_energy_telemetry(db=db, vehicle_id=vehicle_id)


@router.get(
    "/analytics/efficiency",
    summary="Fleet energy efficiency calculation",
)
def get_fleet_efficiency(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Calculate net kWh consumption and regenerative braking recovery efficiency percentage."""
    return calculate_fleet_efficiency(db=db)
