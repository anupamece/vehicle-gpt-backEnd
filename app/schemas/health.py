from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Stable response contract for GET /api/health."""

    status: str = Field("ok", description="Overall service status indicator")
