"""Dual-Mode LLM Service for VehicleGPT (Local Ollama & Cloud Groq).

Supports:
1. Local Ollama: Zero cloud leakage, local inference using llama3.2:3b.
2. Cloud Groq: Fast, zero-cost cloud inference using llama-3.2-3b-preview via Groq LPU API.

Ensures strict evidence-based grounding, automotive prompt constraints,
and graceful fallback to deterministic telemetry summaries when inference is unavailable.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are VehicleGPT, an automotive engineering telemetry reasoning engine.
Your task is to answer the user's natural language question accurately and concisely using EXCLUSIVELY the verified vehicle telemetry evidence provided below.

MANDATORY RULES:
1. STRICT EVIDENCE BOUNDARY: Base all claims, numbers, dates, timestamps, and conclusions solely on the provided EVIDENCE.
2. NO HALLUCINATION: Never invent vehicle events, trouble codes (DTCs), speed/battery readings, or telemetry data.
3. INSUFFICIENT DATA: If the provided evidence is not sufficient to fully answer the question, you must explicitly state that the available evidence is insufficient.
4. CORRELATION VS CAUSATION: You must NEVER claim a confirmed root cause based on temporal correlation or event proximity alone. Acknowledge that correlation indicates observation, not definitive causation.
5. NO ARBITRARY CODE: Do not execute or output code (SQL, Python, Bash) to be run; synthesize analytical findings in clear text.
6. UNITS: Always format units explicitly and accurately (e.g., kWh/100 km, %, °C, km/h, km).
7. TONE: Objective, safety-oriented, technical automotive engineering perspective.
"""


class LLMService:
    """Service client for VehicleGPT LLM inference (Ollama or Groq)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._custom_base_url = base_url
        self._custom_model = model
        self._custom_timeout = timeout

        # Ollama specific defaults (for backward compatibility with tests)
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.chat_endpoint = f"{self.base_url}/api/chat"
        self.groq_endpoint = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"

    @property
    def provider(self) -> str:
        """Active LLM provider: 'ollama' or 'groq'."""
        return (settings.LLM_PROVIDER or "ollama").strip().lower()

    @property
    def model(self) -> str:
        """Active model identifier based on current provider."""
        if self._custom_model:
            return self._custom_model
        if self.provider == "groq":
            return settings.GROQ_MODEL
        return settings.OLLAMA_MODEL

    @model.setter
    def model(self, value: str) -> None:
        self._custom_model = value

    @property
    def timeout(self) -> float:
        """Active timeout in seconds."""
        if self._custom_timeout is not None:
            return self._custom_timeout
        if self.provider == "groq":
            return settings.GROQ_TIMEOUT_SECONDS
        return settings.OLLAMA_TIMEOUT_SECONDS

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._custom_timeout = value

    def is_available(self) -> Tuple[bool, Optional[str]]:
        """Check if active LLM provider (Ollama or Groq) is ready for inference."""
        if self.provider == "groq":
            api_key = settings.GROQ_API_KEY
            if not api_key or not api_key.strip():
                return False, "Groq API key is not configured. Set GROQ_API_KEY in .env."
            return True, None

        # Default: Local Ollama daemon check
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_found = any(self.model in m for m in models)
                    if not model_found:
                        return False, f"Ollama model '{self.model}' not found in local library. Run 'ollama pull {self.model}'."
                    return True, None
                return False, f"Ollama returned HTTP status {res.status_code} on health check."
        except httpx.ConnectError:
            return False, f"Local Ollama server is unreachable at {self.base_url}. Start it with 'ollama serve'."
        except httpx.TimeoutException:
            return False, f"Connection to local Ollama server at {self.base_url} timed out."
        except Exception as exc:
            return False, f"Ollama availability check failed: {exc}"

    def generate_grounded_response(
        self,
        question: str,
        evidence: Dict[str, Any],
        intent: str,
        causation_notice: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send question and structured evidence to active provider for grounded synthesis."""
        if self.provider == "groq":
            return self._generate_groq_response(question, evidence, intent, causation_notice)
        elif self.provider == "ollama":
            return self._generate_ollama_response(question, evidence, intent, causation_notice)
        else:
            return None, f"Unsupported LLM provider '{self.provider}'."

    def _prepare_prompt_payload(
        self, question: str, evidence: Dict[str, Any], intent: str, causation_notice: Optional[str]
    ) -> str:
        evidence_payload = {
            "query_intent": intent,
            "evidence_data": evidence,
        }
        if causation_notice:
            evidence_payload["engineering_causation_notice"] = causation_notice

        evidence_str = json.dumps(evidence_payload, indent=2, default=str)
        return (
            f"USER QUESTION:\n{question}\n\n"
            f"VERIFIED TELEMETRY EVIDENCE:\n{evidence_str}\n\n"
            "Provide a grounded explanation answering the user's question based strictly on the verified evidence above."
        )

    def _generate_groq_response(
        self,
        question: str,
        evidence: Dict[str, Any],
        intent: str,
        causation_notice: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Inference via Groq Cloud API."""
        api_key = settings.GROQ_API_KEY
        if not api_key or not api_key.strip():
            msg = "Groq API key is missing. Set GROQ_API_KEY in .env."
            logger.warning(msg)
            return None, msg

        user_content = self._prepare_prompt_payload(question, evidence, intent, causation_notice)
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.groq_endpoint, headers=headers, json=request_body)

                if response.status_code == 401:
                    msg = "Invalid Groq API key (HTTP 401). Verify GROQ_API_KEY in .env."
                    logger.warning(msg)
                    return None, msg

                if response.status_code == 429:
                    msg = "Groq rate limit exceeded (HTTP 429). Please wait a moment."
                    logger.warning(msg)
                    return None, msg

                if response.status_code != 200:
                    msg = f"Groq API error (HTTP {response.status_code}): {response.text[:200]}"
                    logger.warning(msg)
                    return None, msg

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return None, "Groq returned empty choices."

                content = choices[0].get("message", {}).get("content", "").strip()
                if not content:
                    return None, "Groq returned an empty response."

                return content, None

        except httpx.ConnectError:
            msg = "Could not connect to Groq API. Please check your internet connection."
            logger.warning(msg)
            return None, msg

        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            msg = f"Groq inference timed out after {self.timeout}s ({exc.__class__.__name__})."
            logger.warning(msg)
            return None, msg

        except Exception as exc:
            msg = f"Unexpected error communicating with Groq API: {exc}"
            logger.exception(msg)
            return None, msg

    def _generate_ollama_response(
        self,
        question: str,
        evidence: Dict[str, Any],
        intent: str,
        causation_notice: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Inference via local Ollama daemon."""
        user_content = self._prepare_prompt_payload(question, evidence, intent, causation_notice)
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "keep_alive": getattr(settings, "OLLAMA_KEEP_ALIVE", "5m"),
            "options": {
                "temperature": 0.1,  # Low temperature for factual grounding
                "top_p": 0.9,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.chat_endpoint, json=request_body)

                if response.status_code == 404:
                    msg = (
                        f"Local Ollama model '{self.model}' is not downloaded (HTTP 404). "
                        f"Run 'ollama pull {self.model}' to enable local inference."
                    )
                    logger.warning(msg)
                    return None, msg

                if response.status_code != 200:
                    msg = f"Ollama API error (HTTP {response.status_code}): {response.text[:200]}"
                    logger.warning(msg)
                    return None, msg

                data = response.json()
                content = data.get("message", {}).get("content", "").strip()

                if not content:
                    return None, "Ollama returned an empty response."

                return content, None

        except httpx.ConnectError:
            msg = (
                f"Local Ollama server unreachable at {self.base_url}. "
                "Ensure Ollama daemon is running ('ollama serve')."
            )
            logger.warning(msg)
            return None, msg

        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            msg = f"Local Ollama inference timed out after {self.timeout}s ({exc.__class__.__name__})."
            logger.warning(msg)
            return None, msg

        except Exception as exc:
            msg = f"Unexpected error communicating with local Ollama: {exc}"
            logger.exception(msg)
            return None, msg


# Backward compatibility aliases
OllamaService = LLMService
ollama_service = LLMService()
llm_service = ollama_service
