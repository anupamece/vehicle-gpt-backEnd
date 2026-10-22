"""Unit tests for Groq LLM Provider in LLMService."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.services.llm_service import LLMService


@pytest.fixture
def groq_service(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_test_key_12345")
    monkeypatch.setattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b")
    return LLMService()


def test_groq_is_available_with_key(groq_service):
    """Test is_available returns True when GROQ_API_KEY is configured."""
    available, error = groq_service.is_available()
    assert available is True
    assert error is None


def test_groq_is_available_without_key(monkeypatch):
    """Test is_available returns False when GROQ_API_KEY is empty."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    service = LLMService()
    available, error = service.is_available()
    assert available is False
    assert "GROQ_API_KEY" in error


def test_groq_generate_grounded_response_success(groq_service):
    """Test successful response generation from Groq."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Grounded Groq analysis: Battery temperature peaked at 58.6°C.",
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        answer, warning = groq_service.generate_grounded_response(
            question="What was the peak temperature?",
            evidence={"peak_temp": 58.6},
            intent="thermal_anomaly_investigation",
        )
        assert warning is None
        assert answer == "Grounded Groq analysis: Battery temperature peaked at 58.6°C."
        assert mock_post.called
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer gsk_mock_test_key_12345"


def test_groq_generate_grounded_response_401(groq_service):
    """Test HTTP 401 invalid key returns helpful message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Invalid API Key"

    with patch("httpx.Client.post", return_value=mock_resp):
        answer, warning = groq_service.generate_grounded_response(
            question="Test invalid key",
            evidence={},
            intent="general_telemetry",
        )
        assert answer is None
        assert "Invalid Groq API key" in warning
