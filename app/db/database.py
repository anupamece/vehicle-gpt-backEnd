import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

# SQLite requires check_same_thread=False for FastAPI multi-threaded requests
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG and False,  # set True if detailed query logging needed
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables according to SQLAlchemy metadata."""
    # Ensure data directory exists before creating tables
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing database tables at %s", settings.sqlite_db_path)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session per request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
