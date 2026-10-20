import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.simulator.generate_data import seed_mock_data

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vehicle_gpt")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager: initialize database and seed initial mock data."""
    logger.info("Starting up %s (version: %s)", settings.PROJECT_NAME, settings.VERSION)
    # Ensure SQLite directory exists and create tables
    init_db()

    # Seed mock data if database is empty
    with SessionLocal() as db_session:
        seed_mock_data(db_session, force=False)

    logger.info("Database initialized and ready at %s", settings.sqlite_db_path)
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Automotive Telemetry and Fleet Intelligence REST API",
    docs_url=settings.DOCS_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan,
)

# Configure CORS
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled server exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred.", "type": type(exc).__name__},
    )


# Mount modular API router
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    """Root redirect to OpenAPI documentation."""
    return {
        "app": settings.PROJECT_NAME,
        "docs": settings.DOCS_URL,
        "health": f"{settings.API_PREFIX}/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
