from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.query import router as query_router
from app.api.vehicle import router as vehicle_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router)
api_router.include_router(vehicle_router)
api_router.include_router(events_router)
api_router.include_router(analytics_router)
api_router.include_router(query_router)

__all__ = ["api_router"]
