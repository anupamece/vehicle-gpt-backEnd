import os
from pathlib import Path
from typing import List, Optional, Union

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

    # Dedicated Local Ollama LLM Configuration
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0  # Dedicated timeout for LLM inference (seconds)
    OLLAMA_KEEP_ALIVE: str = "5m"  # Keep model in memory after inference for warm requests

    # Cloud Groq LLM Configuration (Zero-Cost Fast Cloud Deployment)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_TIMEOUT_SECONDS: float = 30.0

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
