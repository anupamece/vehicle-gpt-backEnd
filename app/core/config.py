import os
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VehicleGPT Telemetry API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    API_PREFIX: str = "/api"
    DOCS_URL: str = "/docs"
    OPENAPI_URL: str = "/openapi.json"

    # CORS origins: list of origins or comma-separated string
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database (Default: backend/data/vehicle.db)
    DATABASE_URL: str = "sqlite:///./data/vehicle.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def sqlite_db_path(self) -> Path:
        """Resolve SQLite path and ensure parent directory exists."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "", 1)
            path = Path(raw_path).resolve()
            # Ensure data directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        return Path("./data/vehicle_gpt.db").resolve()


settings = Settings()
# Ensure data directory is created on configuration load
settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
