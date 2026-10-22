"""Unit tests for OllamaService with mocked HTTP responses.

Ensures the service handles successful generation, missing models (404),
connection errors, timeouts, and empty responses safely without requiring
a downloaded model or active network.
"""

from unittest.mock import MagicMock, patch
import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm_service import OllamaService, ollama_service
from app.services.query_router import route_natural_language_query


@pytest.fixture
def test_service():
    return OllamaService(
        base_url="http://mock-ollama:11434",
        model="llama3.2:3b",
        timeout=5.0,
    )


def test_ollama_is_available_success(test_service):
    """Test is_available returns True when model is present."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "llama3.2:3b:latest"}, {"name": "nomic-embed-text:latest"}]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        available, error = test_service.is_available()
        assert available is True
        assert error is None


def test_ollama_is_available_model_missing(test_service):
    """Test is_available returns False when requested model is not downloaded."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "other-model:latest"}]}

    with patch("httpx.Client.get", return_value=mock_resp):
        available, error = test_service.is_available()
        assert available is False
        assert "not found in local library" in error


def test_ollama_is_available_connection_error(test_service):
    """Test is_available returns False on connection error."""
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")):
        available, error = test_service.is_available()
        assert available is False
        assert "unreachable" in error


def test_generate_grounded_response_success(test_service):
    """Test successful response generation returns model content."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "City driving consumed 15.2 kWh/100 km with 28.05% regeneration efficiency.",
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        answer, warning = test_service.generate_grounded_response(
            question="Compare City vs Highway efficiency.",
            evidence={"city_kwh_per_100km": 15.2},
            intent="energy_efficiency",
        )
        assert warning is None
        assert answer is not None
        assert "15.2 kWh/100 km" in answer


def test_generate_grounded_response_model_404(test_service):
    """Test HTTP 404 missing model triggers graceful failure notice."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "model 'llama3.2:3b' not found"

    with patch("httpx.Client.post", return_value=mock_resp):
        answer, warning = test_service.generate_grounded_response(
            question="What is the battery health?",
            evidence={},
            intent="battery_status",
        )
        assert answer is None
        assert warning is not None
        assert "not downloaded" in warning
        assert "ollama pull" in warning


def test_generate_grounded_response_connect_error(test_service):
    """Test connection error triggers graceful fallback warning."""
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Cannot reach Ollama")):
        answer, warning = test_service.generate_grounded_response(
            question="Analyze ADAS disengagements.",
            evidence={},
            intent="adas_disengagement_analysis",
        )
        assert answer is None
        assert warning is not None
        assert "unreachable" in warning
        assert "ollama serve" in warning


def test_generate_grounded_response_timeout(test_service):
    """Test read timeout triggers timeout warning."""
    with patch("httpx.Client.post", side_effect=httpx.ReadTimeout("Request timed out")):
        answer, warning = test_service.generate_grounded_response(
            question="Investigate battery overheating.",
            evidence={},
            intent="thermal_anomaly_investigation",
        )
        assert answer is None
        assert warning is not None
        assert "timed out" in warning


def test_generate_grounded_response_empty_content(test_service):
    """Test empty model content returns fallback warning."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"role": "assistant", "content": "  "}}

    with patch("httpx.Client.post", return_value=mock_resp):
        answer, warning = test_service.generate_grounded_response(
            question="Check fleet status.",
            evidence={},
            intent="fleet_status",
        )
        assert answer is None
        assert "empty response" in warning


def test_query_router_fallback_on_ollama_failure(db_session: Session):
    """Test query_router falls back to deterministic summary when Ollama is unreachable."""
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Daemon offline")):
        resp = route_natural_language_query(
            db=db_session,
            question="Compare City versus Highway energy consumption metrics in kWh/100 km and regeneration performance.",
        )
        assert resp.intent == "energy_efficiency"
        # Must return deterministic calculation, not crash
        assert "15.2" in resp.answer or "kWh/100 km" in resp.answer
        assert len(resp.warnings) > 0
        assert any("unreachable" in w or "deterministic" in w for w in resp.warnings)
        assert "trips" in resp.sources


def test_query_router_success_with_mocked_ollama(db_session: Session):
    """Test query_router adopts LLM synthesis when Ollama responds successfully."""
    mock_llm_text = (
        "Grounded telemetry analysis: City driving achieved 15.2 kWh/100 km "
        "with 28.05% regeneration efficiency, outperforming Highway driving."
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"role": "assistant", "content": mock_llm_text}
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        resp = route_natural_language_query(
            db=db_session,
            question="Compare City versus Highway energy consumption metrics in kWh/100 km and regeneration performance.",
        )
        assert resp.intent == "energy_efficiency"
        assert resp.answer == mock_llm_text
        assert resp.data["comparison"]["more_efficient_mode"] == "city"
        assert any("Ollama" in w for w in resp.warnings)


def test_query_router_timeout_raises_504(db_session: Session):
    """Test query_router raises HTTP 504 on inference timeout rather than fabricating an answer."""
    from fastapi import HTTPException

    with patch("httpx.Client.post", side_effect=httpx.ReadTimeout("Inference timed out")):
        with pytest.raises(HTTPException) as exc_info:
            route_natural_language_query(
                db=db_session,
                question="Compare City versus Highway energy consumption metrics in kWh/100 km.",
            )
        assert exc_info.value.status_code == 504
        assert "timed out" in exc_info.value.detail.lower()
        assert "llama3.2:3b" in exc_info.value.detail
