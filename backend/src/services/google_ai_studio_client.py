"""Google AI Studio API client for direct Gemini API access.

This module provides a client for calling Google AI Studio's Gemini API directly
with automatic key rotation for free tier limits.
"""

import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .. import config

logger = logging.getLogger(__name__)


class GoogleAIStudioError(Exception):
    """Custom exception for Google AI Studio API errors."""

    def __init__(self, message: str, error_type: str = "unknown", is_rate_limit: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.is_rate_limit = is_rate_limit


class _GoogleAIClientManager:
    """Manages API key rotation and state for Google AI Studio."""

    def __init__(self, api_keys: List[str]):
        if not api_keys or not any(api_keys):
            raise ValueError("At least one Google AI Studio API key is required.")

        self._api_keys = [key for key in api_keys if key]
        self._current_key_index = 0
        self._lock = asyncio.Lock()
        self._last_reset_timestamp = time.time()
        self._exhausted_keys_today = set()
        logger.info(f"Google AI Client Manager initialized with {len(self._api_keys)} API keys.")

    async def get_key(self) -> str:
        async with self._lock:
            # Before getting a key, check if it's time to reset
            now = time.time()
            if now - self._last_reset_timestamp > 86400:  # 24 hours
                if self._current_key_index != 0 or self._exhausted_keys_today:
                    logger.info("Resetting Google AI Studio API key usage after 24 hours.")
                    self._current_key_index = 0
                    self._exhausted_keys_today.clear()
                self._last_reset_timestamp = now
            return self._api_keys[self._current_key_index]

    async def rotate_key(self) -> bool:
        """Rotates to the next available API key."""
        async with self._lock:
            logger.warning(f"🔑 Google AI Studio Key rotation: Key index {self._current_key_index} exhausted (marked: {list(self._exhausted_keys_today)})")
            self._exhausted_keys_today.add(self._current_key_index)

            if len(self._exhausted_keys_today) >= len(self._api_keys):
                logger.error(f"❌ All Google AI Studio API keys exhausted! Total keys: {len(self._api_keys)}, Exhausted: {len(self._exhausted_keys_today)}")
                return False

            # Find the next unused key
            previous_index = self._current_key_index
            for _ in range(len(self._api_keys)):
                self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
                if self._current_key_index not in self._exhausted_keys_today:
                    logger.warning(
                        f"🔄 Google AI Studio Key rotation: {previous_index} -> {self._current_key_index}. "
                        f"Available keys left: {len(self._api_keys) - len(self._exhausted_keys_today) - 1}/{len(self._api_keys)}"
                    )
                    return True

            logger.error(f"❌ No available keys found after rotation attempt")
            return False


_client_manager: Optional[_GoogleAIClientManager] = None
_manager_lock = asyncio.Lock()

# Global lock to serialize access to the stateful genai library, preventing race conditions.
_google_api_lock = asyncio.Lock()


class GoogleAIClient:
    """Client for Google AI Studio Gemini API with rate limit detection."""

    def _is_rate_limit_error(self, error_content: str) -> bool:
        """Check if error indicates rate limit exceeded (both daily and minute).

        Args:
            error_content: Error message content

        Returns:
            True if this is a rate limit error
        """
        # Unified list of all rate limit indicators
        RATE_LIMIT_ERRORS = [
            "Resource has been exhausted", "Rate limit exceeded", "Quota exceeded",
            "Too many requests", "resource_exhausted", "quota_limit_exceeded",
            "rate_limit_exceeded", "429", "generaterequestsperdayperprojectpermodel-freetier",
            "free_tier_requests", "requests per day", "daily quota",
            "generativelanguage.googleapis.com/generate_content",
            "generaterequestsperminuteperprojectpermodel", # Added RPM specific
            "generatecontentrequestsperminuteperprojectpermodel", # Added Content RPM specific
            "user has exceeded", # Added User limit specific
            "limit has been reached" # Generic limit reached
        ]
        error_lower = error_content.lower()
        return any(pattern.lower() in error_lower for pattern in RATE_LIMIT_ERRORS)

    def _should_rotate_key(self, error: Exception) -> bool:
        """Checks if the error warrants a key rotation (Any Rate Limit)."""
        # Check text content
        if self._is_rate_limit_error(str(error)):
            return True

        # Check standard HTTP status attributes
        # Different libraries use different attribute names for the status code
        status_attrs = ['status_code', 'code', 'http_status', 'status']
        for attr in status_attrs:
            val = getattr(error, attr, None)
            # Check for 429 (Too Many Requests) or 403 (Forbidden - sometimes used for quota)
            # Note: We include 403 because specific quota errors can sometimes manifest as permission denials
            # But we rely mainly on text for 403 to avoid rotating on genuine auth errors.
            # For 429, it's almost always a rate limit.
            if val == 429:
                 return True

        return False

    def _convert_openai_json_to_gemini_schema(self, response_format: Optional[Dict[str, str]]) -> Optional[
        Dict[str, Any]]:
        """Convert OpenAI JSON format to Gemini Schema format.

        Args:
            response_format: OpenAI response format specification

        Returns:
            Gemini Schema specification or None
        """
        if not response_format or response_format.get("type") != "json_object":
            return None

        # Define Gemini schema for our expected JSON structure
        gemini_schema = {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The synthesized answer to the user's query"
                },
                "main_sources": {
                    "type": "array",
                    "description": "List of telegram message IDs used as sources",
                    "items": {
                        "type": "integer"
                    }
                },
                "confidence": {
                    "type": "string",
                    "description": "Confidence level (HIGH/MEDIUM/LOW)"
                },
                "has_expert_comments": {
                    "type": "boolean",
                    "description": "Whether expert comments are available"
                },
                "language": {
                    "type": "string",
                    "description": "Response language (e.g., 'ru', 'en')"
                },
                "posts_analyzed": {
                    "type": "integer",
                    "description": "Number of posts analyzed"
                },
                "token_usage": {
                    "type": "object",
                    "description": "Token usage information"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the analysis"
                }
            },
            "required": ["answer", "main_sources", "confidence", "language"]
        }

        return gemini_schema

    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Any]:
        """Convert OpenAI message format to Gemini message format.

        Args:
            messages: List of OpenAI format messages

        Returns:
            List of Gemini format messages
        """
        import google.generativeai as genai

        gemini_messages = []
        system_message = None

        for message in messages:
            if message["role"] == "system":
                # Store system message to prepend later
                system_message = message["content"]
                continue
            elif message["role"] == "user":
                content = message["content"]
                if system_message and not gemini_messages:
                    # Prepend system message to first user message
                    content = f"{system_message}\n\n{content}"
                    system_message = None  # Clear to avoid adding again
                gemini_messages.append(content)
            elif message["role"] == "assistant":
                gemini_messages.append(message["content"])

        # If system message wasn't added yet, add it as first message
        if system_message:
            gemini_messages.insert(0, system_message)

        return gemini_messages

    def _convert_gemini_response_to_openai_format(self, gemini_response: Any) -> Any:
        """Convert Gemini response to OpenAI format for compatibility.

        Args:
            gemini_response: Raw Gemini API response

        Returns:
            Response object compatible with OpenAI format
        """
        # Create a mock response object that mimics OpenAI's response structure
        class MockOpenAIResponse:
            def __init__(self, content: str, model: str):
                self.choices = [MockChoice(content)]
                self.model = model
                self.usage = MockUsage()

        class MockChoice:
            def __init__(self, content: str):
                self.message = MockMessage(content)
                self.finish_reason = "stop"

        class MockMessage:
            def __init__(self, content: str):
                self.content = content
                self.role = "assistant"

        class MockUsage:
            def __init__(self):
                self.prompt_tokens = 0
                self.completion_tokens = 0
                self.total_tokens = 0

        # Extract content from Gemini response
        content = ""
        if hasattr(gemini_response, 'text'):
            content = gemini_response.text
        elif hasattr(gemini_response, 'candidates') and gemini_response.candidates:
            candidate = gemini_response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                content = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))

        # Log the raw response for debugging
        logger.info(f"Gemini raw response (first 200 chars): {content[:200]}")

        return MockOpenAIResponse(content, "gemini-2.0-flash-exp")

    def _extract_error_details(self, error: Exception) -> Dict[str, Any]:
        """Extract error details from API exception.

        Args:
            error: The exception object

        Returns:
            Dictionary with error details
        """
        error_content = str(error)
        is_rate_limit = self._is_rate_limit_error(error_content)

        # Extract more detailed error information from Google AI SDK
        details = None
        if hasattr(error, 'response') and error.response:
            details = error.response
        elif hasattr(error, 'message'):
            details = error.message

        return {
            "error_type": "rate_limit" if is_rate_limit else "api_error",
            "is_rate_limit": is_rate_limit,
            "message": error_content,
            "details": details
        }

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        """
        Create chat completion using Google AI Studio API, with automatic key rotation
        for daily rate limit errors.

        Args:
            model: Model name (e.g., "gemini-2.0-flash")
            messages: List of message dictionaries
            temperature: Sampling temperature
            response_format: Response format specification
            **kwargs: Additional parameters

        Returns:
            Chat completion response

        Raises:
            GoogleAIStudioError: If API call fails with rate limit information
        """
        manager = await _get_client_manager()
        last_error = None

        logger.info(f"🚀 Google AI Studio: Starting API call with model {model}. Total keys available: {len(manager._api_keys)}")

        async with _google_api_lock:
            for attempt in range(len(manager._api_keys)):
                api_key = await manager.get_key()
                current_key_index = manager._current_key_index

                logger.info(f"🔑 Attempt {attempt + 1}/{len(manager._api_keys)}: Using Google AI Studio key index {current_key_index}")

                try:
                    genai.configure(api_key=api_key)

                    # Map model names to Google AI Studio format
                    original_model = model  # Keep original for logging
                    if model == "gemini-2.0-flash":
                        model = "gemini-2.0-flash"
                    elif model == "gemini-2.5-flash-lite":
                        model = "gemini-2.5-flash-lite"
                    elif model == "gemini-3-flash":
                        model = "gemini-3-flash"
                    elif model.startswith("google/"):
                        model = model.replace("google/", "")

                    gemini_messages = self._convert_messages_to_gemini_format(messages)
                    generation_config = {"temperature": temperature, "candidate_count": 1}

                    if response_format and response_format.get("type") == "json_object":
                        gemini_schema = self._convert_openai_json_to_gemini_schema(response_format)
                        if gemini_schema:
                            generation_config["response_mime_type"] = "application/json"
                            try:
                                generation_config["response_schema"] = genai.Schema(**gemini_schema)
                                logger.info("Using Gemini native JSON mode with schema")
                            except Exception as e:
                                logger.warning(f"Failed to create Gemini schema: {e}, using fallback")
                                if gemini_messages:
                                    gemini_messages[0] += "\n\nIMPORTANT: You must respond with valid JSON only."
                        else:
                            if gemini_messages:
                                gemini_messages[0] += "\n\nIMPORTANT: You must respond with valid JSON only."

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
                    logger.info(f"✅ Google AI Studio API call successful with key index {current_key_index}")
                    return self._convert_gemini_response_to_openai_format(response)

                except Exception as error:
                    last_error = error
                    error_str = str(error)

                    logger.error(f"❌ Google AI Studio API error with key index {current_key_index}: {error_str[:200]}...")

                    if self._should_rotate_key(error):
                        # This is a rate limit error (Daily or Minute). Rotate the key and allow the loop to continue.
                        logger.warning(f"🔄 Rate limit hit (RPM or Daily) for key {current_key_index}, attempting rotation...")
                        rotated = await manager.rotate_key()
                        if not rotated:
                            logger.error(f"❌ All Google AI Studio keys exhausted.")
                            raise error  # All keys exhausted, re-raise last error
                        # Continue to next key with same lock
                        logger.info(f"✅ Key rotation successful, trying next key...")
                        continue
                    else:
                        # This is not a rate limit error (e.g., auth error, server error).
                        # We should not rotate the key. Re-raise the error.
                        logger.warning(f"⚠️ Non-rate-limit error for key {current_key_index}: {error_str[:100]}...")
                        raise error

        # If the loop completes, it means all keys were tried and failed with daily limits.
        if last_error:
            error_details = self._extract_error_details(last_error)
            raise GoogleAIStudioError(
                f"Google AI Studio API error after trying all keys: {error_details['message']}",
                error_type=error_details["error_type"],
                is_rate_limit=error_details["is_rate_limit"]
            ) from last_error
        raise GoogleAIStudioError("All Google AI Studio API keys failed.")

    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return True


async def _get_client_manager() -> _GoogleAIClientManager:
    """Initializes and returns the singleton client manager."""
    global _client_manager
    if _client_manager is None:
        async with _manager_lock:
            if _client_manager is None:
                _client_manager = _GoogleAIClientManager(config.GOOGLE_AI_STUDIO_API_KEYS)
    return _client_manager


def create_google_ai_studio_client() -> Optional[GoogleAIClient]:
    """Create and return a singleton Google AI Studio client instance."""
    if not config.GOOGLE_AI_STUDIO_API_KEYS:
        logger.warning("No Google AI Studio API keys found. Client will not be created.")
        return None
    return GoogleAIClient()


def is_google_ai_studio_available() -> bool:
    """Check if Google AI Studio API keys are available in config."""
    return bool(config.GOOGLE_AI_STUDIO_API_KEYS)