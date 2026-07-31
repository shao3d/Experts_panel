"""Canonical OpenRouter-backed LLM client.

The filename is kept as a temporary import-compatibility seam for existing
services. Query-time traffic no longer uses Vertex AI credentials.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from .. import config

logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT_SECONDS = 90


class OpenRouterLLMError(Exception):
    """Unified error wrapper for OpenRouter chat-completion calls."""

    def __init__(
        self,
        message: str,
        error_type: str = "unknown",
        is_rate_limit: bool = False,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.is_rate_limit = is_rate_limit
        self.status_code = status_code


class _Message:
    def __init__(self, content: str):
        self.content = content
        self.role = "assistant"


class _Choice:
    def __init__(self, content: str, finish_reason: Optional[str] = None):
        self.message = _Message(content)
        self.finish_reason = finish_reason or "stop"


class _Usage:
    def __init__(self, usage: Dict[str, Any] | None):
        usage = usage or {}
        self.prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        self.total_tokens = int(usage.get("total_tokens", 0) or 0)


class _Response:
    def __init__(self, payload: Dict[str, Any], requested_model: str):
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise OpenRouterLLMError(
                "OpenRouter response did not contain a usable completion choice",
                error_type="invalid_response",
            )

        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise OpenRouterLLMError(
                "OpenRouter response did not contain an assistant message",
                error_type="invalid_response",
            )

        content = message.get("content")
        if not isinstance(content, str):
            raise OpenRouterLLMError(
                "OpenRouter response contained no textual assistant content",
                error_type="invalid_response",
            )
        self.choices = [_Choice(content, choice.get("finish_reason"))]
        self.model = payload.get("model") or requested_model
        self.usage = _Usage(payload.get("usage"))


class OpenRouterLLMClient:
    """Small OpenAI-compatible client with strict provider capability routing."""

    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        if self.api_key:
            logger.info("OpenRouter LLM client configured")
        else:
            logger.error("OpenRouter LLM client is not configured")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _classify_error(status_code: Optional[int], message: str) -> tuple[str, bool]:
        if status_code in {401, 403}:
            return "authentication", False
        if status_code == 402:
            return "billing_error", False
        if status_code == 404:
            return "model_unavailable", False
        if status_code == 429:
            return "rate_limit", True
        if status_code in {500, 502, 503, 504, 529}:
            return "server_error", False
        if status_code and 400 <= status_code < 500:
            return "invalid_request", False
        if "timeout" in message.lower():
            return "timeout", False
        return "unknown", False

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://expa.beyondhorizon.dev",
            "X-Title": "Experts Panel",
        }
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
        except httpx.TimeoutException as exc:
            raise OpenRouterLLMError(str(exc), "timeout") from exc
        except httpx.HTTPError as exc:
            raise OpenRouterLLMError(str(exc), "network_error") from exc

        if response.is_success:
            return response.json()

        try:
            body = response.json()
            message = body.get("error", {}).get("message") or response.text
        except ValueError:
            message = response.text
        error_type, is_rate_limit = self._classify_error(response.status_code, message)
        raise OpenRouterLLMError(
            f"Error code: {response.status_code} - {message}",
            error_type=error_type,
            is_rate_limit=is_rate_limit,
            status_code=response.status_code,
        )

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        if not self.is_configured():
            raise OpenRouterLLMError(
                "OpenRouter API key is not configured", error_type="authentication"
            )

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            # Do not silently route JSON/tool requests to a provider that
            # lacks the requested parameter support.
            "provider": {"require_parameters": True},
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format
        payload.update(kwargs)

        def should_retry(exc: BaseException) -> bool:
            return isinstance(exc, OpenRouterLLMError) and (
                exc.is_rate_limit
                or exc.error_type in {"timeout", "network_error", "server_error"}
            )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(4),
                wait=wait_random_exponential(multiplier=1, max=12),
                retry=retry_if_exception(should_retry),
                reraise=True,
            ):
                with attempt:
                    logger.info(
                        "OpenRouter API attempt %s/4 with model %s",
                        attempt.retry_state.attempt_number,
                        model,
                    )
                    result = await self._post(payload)
            return _Response(result, model)
        except OpenRouterLLMError:
            raise
        except Exception as exc:
            raise OpenRouterLLMError(str(exc)) from exc


_client_instance: Optional[OpenRouterLLMClient] = None


def get_openrouter_llm_client() -> OpenRouterLLMClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenRouterLLMClient()
    return _client_instance


# Compatibility names allow existing service imports to keep working while the
# canonical runtime is OpenRouter. Remove only after a dedicated import cleanup.
VertexLLMClient = OpenRouterLLMClient
VertexLLMError = OpenRouterLLMError
get_vertex_llm_client = get_openrouter_llm_client

__all__ = [
    "OpenRouterLLMClient", "OpenRouterLLMError", "get_openrouter_llm_client",
    "VertexLLMClient", "VertexLLMError", "get_vertex_llm_client",
]
