"""Google AI Studio API client for direct Gemini API access.

This module provides a simplified client for calling Google AI Studio's Gemini API.
Optimized for single API key usage with Tier 1 (paid) accounts.

For multi-key rotation (e.g., multiple free tier keys), see the legacy
_GoogleAIClientManager class commented at the bottom of this file.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List

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

# Retry settings for rate limit errors
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 65  # Wait for rate limit window to reset


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

    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[str]:
        """Convert OpenAI message format to Gemini message format.

        Args:
            messages: List of OpenAI format messages

        Returns:
            List of Gemini format messages (simplified to content strings)
        """
        gemini_messages = []
        system_prompt = ""

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                if system_prompt:
                    gemini_messages.append(f"{system_prompt}\n\n{content}")
                    system_prompt = ""
                else:
                    gemini_messages.append(content)
            elif role == "assistant":
                gemini_messages.append(f"Assistant: {content}")

        return gemini_messages

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
            content = gemini_response.text
        except (AttributeError, ValueError):
            try:
                content = gemini_response.candidates[0].content.parts[0].text
            except (AttributeError, IndexError, ValueError):
                content = str(gemini_response)

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
        **kwargs
    ) -> Any:
        """Create chat completion using Google AI Studio API.

        Features simple retry on rate limit errors.

        Args:
            model: Model name (e.g., "gemini-2.0-flash")
            messages: List of message dictionaries
            temperature: Sampling temperature
            response_format: Response format specification
            **kwargs: Additional parameters

        Returns:
            Chat completion response

        Raises:
            GoogleAIStudioError: If API call fails
        """
        last_error = None

        for attempt in range(MAX_RETRIES):
            logger.info(f"🚀 Google AI Studio: API call attempt {attempt + 1}/{MAX_RETRIES} with model {model}")

            try:
                # Normalize model name
                if model.startswith("google/"):
                    model = model.replace("google/", "")

                gemini_messages = self._convert_messages_to_gemini_format(messages)
                generation_config = {"temperature": temperature, "candidate_count": 1}

                # Handle JSON response format
                if response_format and response_format.get("type") == "json_object":
                    generation_config["response_mime_type"] = "application/json"
                    # Add JSON instruction to prompt
                    if gemini_messages:
                        gemini_messages[0] += "\n\nIMPORTANT: You must respond with valid JSON only."

                # Add any extra kwargs
                for key, value in kwargs.items():
                    if key not in ["response_format"]:
                        generation_config[key] = value

                gemini_model = genai.GenerativeModel(
                    model_name=model,
                    generation_config=generation_config,
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    }
                )

                response = await gemini_model.generate_content_async(gemini_messages)
                logger.info(f"✅ Google AI Studio API call successful")
                return self._convert_gemini_response_to_openai_format(response)

            except Exception as error:
                last_error = error
                error_str = str(error)
                logger.error(f"❌ Google AI Studio API error: {error_str[:200]}...")

                # Check if rate limit error - retry after wait
                if self._is_rate_limit_error(error_str) and attempt < MAX_RETRIES - 1:
                    logger.warning(f"⏳ Rate limit hit. Waiting {RETRY_WAIT_SECONDS}s before retry...")
                    await asyncio.sleep(RETRY_WAIT_SECONDS)
                    continue
                else:
                    # Non-rate-limit error or last attempt - re-raise
                    break

        # All retries exhausted
        if last_error:
            error_details = self._extract_error_details(last_error)
            raise GoogleAIStudioError(
                f"Google AI Studio API error: {error_details['message']}",
                error_type=error_details["error_type"],
                is_rate_limit=error_details["is_rate_limit"]
            ) from last_error
        
        raise GoogleAIStudioError("Google AI Studio API call failed with no error details.")

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