from fastapi import APIRouter
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health Check")
def health_check() -> HealthResponse:
    """Return status: ok per stable API contract specification."""
    return HealthResponse(status="ok")
