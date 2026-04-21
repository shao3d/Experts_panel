"""Canonical Vertex-backed Gemini client.

This module is the source of truth for the backend runtime LLM client.
It authenticates via Vertex AI service account credentials / ADC.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from .vertex_ai_auth import VertexAICredentialsError, get_vertex_ai_auth_manager

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 60


class VertexLLMError(Exception):
    """Unified error wrapper for Vertex-backed Gemini calls."""

    def __init__(self, message: str, error_type: str = "unknown", is_rate_limit: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.is_rate_limit = is_rate_limit


class VertexLLMClient:
    """Unified Vertex-backed Gemini client with OpenAI-style responses."""

    def __init__(self):
        self._auth_manager = get_vertex_ai_auth_manager()
        if self._auth_manager.is_configured():
            logger.info(
                "✅ Vertex LLM client configured for project=%s location=%s",
                self._auth_manager.project_id,
                self._auth_manager.location,
            )
        else:
            logger.error("❌ Vertex LLM client is not configured")

    def _normalize_model_name(self, model: str) -> str:
        if model.startswith("google/"):
            return model.replace("google/", "", 1)
        return model

    def _resolve_location_for_model(self, model: str) -> str:
        """Route Gemini 3 family through global endpoint on Vertex AI."""
        if model.startswith("gemini-3"):
            return "global"
        return self._auth_manager.location

    def _is_rate_limit_error(self, error_content: str) -> bool:
        rate_limit_patterns = [
            "resource has been exhausted",
            "rate limit exceeded",
            "quota exceeded",
            "too many requests",
            "resource_exhausted",
            "quota_limit_exceeded",
            "rate_limit_exceeded",
            "429",
            "requests per day",
            "requests per minute",
            "daily quota",
        ]
        error_lower = error_content.lower()
        return any(pattern in error_lower for pattern in rate_limit_patterns)

    def _extract_system_instruction(
        self, messages: List[Dict[str, str]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        system_messages: List[str] = []
        contents: List[Dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                if content:
                    system_messages.append(content)
                continue

            vertex_role = "model" if role == "assistant" else "user"
            contents.append(
                {
                    "role": vertex_role,
                    "parts": [{"text": content}],
                }
            )

        return "\n\n".join(system_messages), contents

    def _to_vertex_generation_config(
        self,
        temperature: float,
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, str]],
        extra_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "candidateCount": 1,
        }

        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens

        if response_format and response_format.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        key_map = {
            "top_p": "topP",
            "topP": "topP",
            "top_k": "topK",
            "topK": "topK",
            "candidate_count": "candidateCount",
            "candidateCount": "candidateCount",
            "max_output_tokens": "maxOutputTokens",
            "maxOutputTokens": "maxOutputTokens",
            "response_mime_type": "responseMimeType",
            "responseMimeType": "responseMimeType",
        }

        for key, value in extra_kwargs.items():
            mapped_key = key_map.get(key, key)
            generation_config[mapped_key] = value

        return generation_config

    def _build_generate_content_url(self, model: str) -> str:
        project_id = self._auth_manager.project_id
        location = self._resolve_location_for_model(model)
        host = (
            "aiplatform.googleapis.com"
            if location == "global"
            else f"{location}-aiplatform.googleapis.com"
        )
        return (
            f"https://{host}/v1/"
            f"projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
        )

    def _post_json(self, url: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )

        if response.ok:
            return response.json()

        try:
            error_body = response.json()
            error_message = error_body.get("error", {}).get("message", response.text)
        except ValueError:
            error_message = response.text

        raise RuntimeError(f"Error code: {response.status_code} - {error_message}")

    async def _generate_content_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        response_format: Optional[Dict[str, str]],
        max_tokens: Optional[int],
        **kwargs,
    ) -> Dict[str, Any]:
        system_instruction, contents = self._extract_system_instruction(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": self._to_vertex_generation_config(
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                extra_kwargs=kwargs,
            ),
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
            ],
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        token = await self._auth_manager.get_access_token()
        url = self._build_generate_content_url(model)
        return await asyncio.to_thread(self._post_json, url, token, payload)

    def _extract_error_details(self, error: Exception) -> Dict[str, Any]:
        error_str = str(error).lower()
        is_rate_limit = self._is_rate_limit_error(error_str)

        if is_rate_limit:
            error_type = "rate_limit"
        elif "invalid" in error_str or "auth" in error_str or "permission" in error_str:
            error_type = "authentication"
        elif "timeout" in error_str:
            error_type = "timeout"
        else:
            error_type = "unknown"

        return {
            "message": str(error),
            "error_type": error_type,
            "is_rate_limit": is_rate_limit,
        }

    def _convert_vertex_response_to_openai_format(self, vertex_response: Dict[str, Any]) -> Any:
        class MockMessage:
            def __init__(self, content: str):
                self.content = content
                self.role = "assistant"

        class MockChoice:
            def __init__(self, content: str):
                self.message = MockMessage(content)
                self.finish_reason = "stop"

        class MockUsage:
            def __init__(self, usage_metadata: Dict[str, Any]):
                self.prompt_tokens = usage_metadata.get("promptTokenCount", 0)
                self.completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
                self.total_tokens = usage_metadata.get("totalTokenCount", 0)

        class MockOpenAIResponse:
            def __init__(self, content: str, model: str, usage_metadata: Dict[str, Any]):
                self.choices = [MockChoice(content)]
                self.model = model
                self.usage = MockUsage(usage_metadata)

        candidate = (vertex_response.get("candidates") or [{}])[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason == "SAFETY":
            logger.warning("Vertex AI response blocked by SAFETY settings.")
            return MockOpenAIResponse(
                "Запрос был заблокирован фильтрами безопасности (Safety Settings). Пожалуйста, переформулируйте запрос.",
                vertex_response.get("modelVersion", "gemini"),
                vertex_response.get("usageMetadata", {}),
            )

        parts = candidate.get("content", {}).get("parts", [])
        content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        return MockOpenAIResponse(
            content,
            vertex_response.get("modelVersion", "gemini"),
            vertex_response.get("usageMetadata", {}),
        )

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Any:
        if not self._auth_manager.is_configured():
            raise VertexLLMError(
                "Vertex AI credentials are not configured",
                error_type="authentication",
                is_rate_limit=False,
            )

        normalized_model = self._normalize_model_name(model)

        def _should_retry(exc: Exception) -> bool:
            error_str = str(exc).lower()
            return self._is_rate_limit_error(error_str) or "timeout" in error_str

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_random_exponential(multiplier=1.5, max=15),
                retry=retry_if_exception(_should_retry),
                reraise=True,
            ):
                with attempt:
                    attempt_num = attempt.retry_state.attempt_number
                    logger.info(
                        "🚀 Vertex AI: API call attempt %s/5 with model %s",
                        attempt_num,
                        normalized_model,
                    )
                    response = await self._generate_content_request(
                        model=normalized_model,
                        messages=messages,
                        temperature=temperature,
                        response_format=response_format,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                    logger.info("✅ Vertex AI API call successful")

            return self._convert_vertex_response_to_openai_format(response)

        except (VertexAICredentialsError, RuntimeError, requests.RequestException) as last_error:
            error_str = str(last_error)
            logger.error("❌ Vertex AI API error: %s", error_str[:300])
            error_details = self._extract_error_details(last_error)
            raise VertexLLMError(
                f"Vertex AI API error: {error_details['message']}",
                error_type=error_details["error_type"],
                is_rate_limit=error_details["is_rate_limit"],
            ) from last_error

    def is_configured(self) -> bool:
        return self._auth_manager.is_configured()


_client_instance: Optional[VertexLLMClient] = None


def get_vertex_llm_client() -> VertexLLMClient:
    """Return the singleton Vertex-backed Gemini client."""

    global _client_instance
    if _client_instance is None:
        _client_instance = VertexLLMClient()
    return _client_instance


__all__ = [
    "VertexLLMClient",
    "VertexLLMError",
    "get_vertex_llm_client",
]
