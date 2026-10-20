import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class QueryRequest(BaseModel):
    """Stable request schema for POST /api/query."""

    question: str = Field(..., min_length=1, description="Natural language user question or query")

    # Optional alias support for backward compatibility
    @model_validator(mode="before")
    @classmethod
    def allow_message_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "question" not in data and "message" in data:
                data["question"] = data["message"]
            elif "question" not in data and "query" in data:
                data["question"] = data["query"]
        return data


class QueryResponse(BaseModel):
    """Stable response contract for POST /api/query."""

    question: str = Field(..., description="The user question processed")
    answer: str = Field(..., description="Natural language answer or structured analytical summary")
    intent: str = Field(..., description="Detected query intent (e.g. battery, fault, fleet_status, energy)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured domain data payload related to the query")
    sources: List[str] = Field(default_factory=list, description="Data sources or database tables queried")
    warnings: List[str] = Field(default_factory=list, description="Any warnings, caveats, or fallback notices")

    # Extra helper property for frontend compatibility with { reply: string }
    @property
    def reply(self) -> str:
        return self.answer
