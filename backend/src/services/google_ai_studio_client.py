"""Google AI Studio API client for direct Gemini API access.

This module provides a simplified client for calling Google AI Studio's Gemini API.
Optimized for single API key usage with Tier 1 (paid) accounts.

For multi-key rotation (e.g., multiple free tier keys), see the legacy
_GoogleAIClientManager class commented at the bottom of this file.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List

from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .. import config

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Get API key from config (supports comma-separated list for backward compatibility)
_api_keys = config.GOOGLE_AI_STUDIO_API_KEYS
if not _api_keys:
    logger.error("❌ No Google AI Studio API key configured!")
else:
    _api_key = _api_keys[0]  # Use first key
    genai.configure(api_key=_api_key)
    logger.info(f"✅ Google AI Studio configured with API key (first 5 chars: {_api_key[:5]}...)")

# Retry settings for rate limit errors (Tenacity-based)
# 5 attempts with random exponential jitter, max 15s between attempts
# Total worst-case: ~15 seconds for TPM spikes
# RPM limits are handled by Global Chunk Retry in map_service.py


class GoogleAIStudioError(Exception):
    """Custom exception for Google AI Studio API errors."""

    def __init__(self, message: str, error_type: str = "unknown", is_rate_limit: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.is_rate_limit = is_rate_limit


class GoogleAIClient:
    """Simplified client for Google AI Studio Gemini API.
    
    Features:
    - Single API key (configured at module load)
    - Automatic retry on rate limit (429) errors
    - OpenAI-compatible response format
    """

    def _is_rate_limit_error(self, error_content: str) -> bool:
        """Check if error indicates rate limit exceeded.

        Args:
            error_content: Error message content

        Returns:
            True if this is a rate limit error
        """
        RATE_LIMIT_PATTERNS = [
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
        return any(pattern in error_lower for pattern in RATE_LIMIT_PATTERNS)

    def _extract_system_instruction(self, messages: List[Dict[str, str]]) -> tuple:
        """Extract system instruction and convert remaining messages to Gemini format.

        Args:
            messages: List of OpenAI format messages

        Returns:
            Tuple of (system_instruction, gemini_messages)
        """
        system_instruction = ""
        gemini_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                system_instruction = content
            elif role == "user":
                gemini_messages.append(content)
            elif role == "assistant":
                gemini_messages.append(f"Assistant: {content}")

        return system_instruction, gemini_messages

    def _convert_gemini_response_to_openai_format(self, gemini_response: Any) -> Any:
        """Convert Gemini response to OpenAI format for compatibility.

        Args:
            gemini_response: Raw Gemini API response

        Returns:
            Response object compatible with OpenAI format
        """
        class MockMessage:
            def __init__(self, content: str):
                self.content = content
                self.role = "assistant"

        class MockChoice:
            def __init__(self, content: str):
                self.message = MockMessage(content)
                self.finish_reason = "stop"

        class MockUsage:
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

        class MockOpenAIResponse:
            def __init__(self, content: str, model: str):
                self.choices = [MockChoice(content)]
                self.model = model
                self.usage = MockUsage()

        try:
            # Check if response was blocked by safety settings
            if hasattr(gemini_response, 'candidates') and gemini_response.candidates:
                candidate = gemini_response.candidates[0]
                # In google-generativeai, finish_reason can be an enum or int.
                # Usually FinishReason.SAFETY is 3
                finish_reason = getattr(candidate, 'finish_reason', None)
                if finish_reason and str(finish_reason).endswith('SAFETY') or finish_reason == 3:
                    logger.warning("Google AI Studio response blocked by SAFETY settings.")
                    return MockOpenAIResponse("Запрос был заблокирован фильтрами безопасности (Safety Settings). Пожалуйста, переформулируйте запрос.", "gemini")
            
            content = gemini_response.text
        except (AttributeError, ValueError):
            try:
                content = gemini_response.candidates[0].content.parts[0].text
            except (AttributeError, IndexError, ValueError):
                logger.error(f"Failed to extract text from Gemini response. Raw response: {gemini_response}")
                # Don't leak the raw proto object to the UI. Provide a generic error instead.
                content = "Не удалось сгенерировать ответ из-за внутренней ошибки формата (возможно, сработал фильтр безопасности)."

        return MockOpenAIResponse(content, "gemini")

    def _extract_error_details(self, error: Exception) -> Dict[str, Any]:
        """Extract detailed error information from exception."""
        error_str = str(error).lower()
        is_rate_limit = self._is_rate_limit_error(error_str)
        
        if is_rate_limit:
            error_type = "rate_limit"
        elif "invalid" in error_str or "auth" in error_str:
            error_type = "authentication"
        elif "timeout" in error_str:
            error_type = "timeout"
        else:
            error_type = "unknown"

        return {
            "message": str(error),
            "error_type": error_type,
            "is_rate_limit": is_rate_limit
        }

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Create chat completion using Google AI Studio API.

        Uses Tenacity AsyncRetrying with jitter for intelligent retry on
        rate limit (429) and timeout errors. Auth/BadRequest errors fail
        immediately without retrying.

        Args:
            model: Model name (e.g., "gemini-2.0-flash")
            messages: List of message dictionaries
            temperature: Sampling temperature
            response_format: Response format specification
            max_tokens: Maximum tokens in response (maps to max_output_tokens)
            **kwargs: Additional parameters

        Returns:
            Chat completion response

        Raises:
            GoogleAIStudioError: If API call fails
        """
        # === Prompt Preparation (executed ONCE, before retry loop) ===
        # This MUST stay outside the retry loop to avoid the concatenation bug:
        # gemini_messages[0] += "IMPORTANT:..." would append on every retry.

        # Normalize model name
        if model.startswith("google/"):
            model = model.replace("google/", "")

        # Extract system instruction separately for proper Gemini handling
        system_instruction, gemini_messages = self._extract_system_instruction(messages)
        generation_config = {"temperature": temperature, "candidate_count": 1}

        # Add max_output_tokens if specified
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens

        # Handle JSON response format
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"
            # Add JSON instruction to prompt (once!)
            if gemini_messages:
                gemini_messages[0] += "\n\nIMPORTANT: You must respond with valid JSON only."

        # Add any extra kwargs
        for key, value in kwargs.items():
            if key not in ["response_format", "max_tokens"]:
                generation_config[key] = value

        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
            system_instruction=system_instruction if system_instruction else None,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )

        # === Retry predicate: only retry rate limit and timeout errors ===
        def _should_retry(retry_state):
            exc = retry_state.outcome.exception()
            if exc is None:
                return False
            error_str = str(exc).lower()
            return self._is_rate_limit_error(error_str) or "timeout" in error_str

        # === API Call with Tenacity retry ===
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_random_exponential(multiplier=1.5, max=15),
                retry=_should_retry,
                reraise=True
            ):
                with attempt:
                    attempt_num = attempt.retry_state.attempt_number
                    logger.info(f"🚀 Google AI Studio: API call attempt {attempt_num}/5 with model {model}")
                    response = await gemini_model.generate_content_async(gemini_messages)
                    logger.info("✅ Google AI Studio API call successful")

            return self._convert_gemini_response_to_openai_format(response)

        except Exception as last_error:
            # Wrap all exceptions in GoogleAIStudioError for uniform contract.
            # Without this, Tenacity reraises raw Google SDK errors
            # (e.g. google.api_core.exceptions.ResourceExhausted) which
            # map_service.py and other consumers don't catch.
            error_str = str(last_error)
            logger.error(f"❌ Google AI Studio API error: {error_str[:200]}")
            error_details = self._extract_error_details(last_error)
            raise GoogleAIStudioError(
                f"Google AI Studio API error: {error_details['message']}",
                error_type=error_details["error_type"],
                is_rate_limit=error_details["is_rate_limit"]
            ) from last_error

    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return bool(_api_keys)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_client_instance: Optional[GoogleAIClient] = None


def create_google_ai_studio_client() -> GoogleAIClient:
    """Create or return singleton Google AI Studio client.
    
    Returns:
        GoogleAIClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GoogleAIClient()
    return _client_instance


# =============================================================================
# LEGACY: Multi-Key Rotation Manager (preserved for future use)
# =============================================================================
# 
# If you need to use multiple API keys (e.g., rotating free tier keys),
# uncomment and adapt the _GoogleAIClientManager class below.
#
# class _GoogleAIClientManager:
#     """Manages API key rotation and state for Google AI Studio."""
#
#     def __init__(self, api_keys: List[str]):
#         if not api_keys or not any(api_keys):
#             raise ValueError("At least one Google AI Studio API key is required.")
#
#         self._api_keys = [key for key in api_keys if key]
#         self._current_key_index = 0
#         self._lock = asyncio.Lock()
#         self._last_reset_timestamp = time.time()
#         self._exhausted_keys_today = set()
#         logger.info(f"Google AI Client Manager initialized with {len(self._api_keys)} API keys.")
#
#     async def get_key(self) -> str:
#         async with self._lock:
#             now = time.time()
#             if now - self._last_reset_timestamp > 86400:  # 24 hours
#                 if self._current_key_index != 0 or self._exhausted_keys_today:
#                     logger.info("Resetting Google AI Studio API key usage after 24 hours.")
#                     self._current_key_index = 0
#                     self._exhausted_keys_today.clear()
#                 self._last_reset_timestamp = now
#             return self._api_keys[self._current_key_index]
#
#     async def rotate_key(self) -> bool:
#         """Rotates to the next available API key."""
#         async with self._lock:
#             logger.warning(f"Key rotation: Key index {self._current_key_index} exhausted")
#             self._exhausted_keys_today.add(self._current_key_index)
#
#             if len(self._exhausted_keys_today) >= len(self._api_keys):
#                 logger.error("All Google AI Studio API keys exhausted!")
#                 return False
#
#             for _ in range(len(self._api_keys)):
#                 self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
#                 if self._current_key_index not in self._exhausted_keys_today:
#                     return True
#
#             return False