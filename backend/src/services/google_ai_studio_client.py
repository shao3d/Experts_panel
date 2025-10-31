"""Google AI Studio API client for direct Gemini API access.

This module provides a client for calling Google AI Studio's Gemini API directly,
bypassing OpenRouter to take advantage of free tier limits when possible.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
import httpx

logger = logging.getLogger(__name__)


class GoogleAIStudioError(Exception):
    """Custom exception for Google AI Studio API errors."""

    def __init__(self, message: str, error_type: str = "unknown", is_rate_limit: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.is_rate_limit = is_rate_limit


class GoogleAIClient:
    """Client for Google AI Studio Gemini API with rate limit detection."""

    # Rate limit error patterns from Google AI Studio
    RATE_LIMIT_ERRORS = [
        "Resource has been exhausted",
        "Rate limit exceeded",
        "Quota exceeded",
        "Too many requests",
        "resource_exhausted",
        "quota_limit_exceeded",
        "rate_limit_exceeded"
    ]

    def __init__(self, api_key: str = None):
        """Initialize Google AI Studio client.

        Args:
            api_key: Google AI Studio API key. If not provided, uses GOOGLE_AI_STUDIO_API_KEY env var.
        """
        if not api_key:
            api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")

        if not api_key:
            raise ValueError("Google AI Studio API key is required. Set GOOGLE_AI_STUDIO_API_KEY environment variable.")

        self.api_key = api_key
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta"
        )

    def _is_rate_limit_error(self, error_content: str) -> bool:
        """Check if error indicates rate limit exceeded.

        Args:
            error_content: Error message content

        Returns:
            True if this is a rate limit error
        """
        error_lower = error_content.lower()
        return any(pattern.lower() in error_lower for pattern in self.RATE_LIMIT_ERRORS)

    def _extract_error_details(self, error: Exception) -> Dict[str, Any]:
        """Extract error details from API exception.

        Args:
            error: The exception object

        Returns:
            Dictionary with error details
        """
        error_content = str(error)
        is_rate_limit = self._is_rate_limit_error(error_content)

        return {
            "error_type": "rate_limit" if is_rate_limit else "api_error",
            "is_rate_limit": is_rate_limit,
            "message": error_content,
            "details": getattr(error, 'response', None)
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
        try:
            # Map model names to Google AI Studio format
            if model == "gemini-2.0-flash":
                model = "gemini-2.0-flash-exp"
            elif model.startswith("google/"):
                # Remove google/ prefix if present
                model = model.replace("google/", "")

            # Prepare request parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }

            # Add response format if specified (JSON mode)
            if response_format and response_format.get("type") == "json_object":
                # For Gemini, we need to add JSON instruction to system message
                system_message = next(
                    (msg for msg in messages if msg["role"] == "system"),
                    None
                )
                if system_message:
                    system_message["content"] += "\n\nIMPORTANT: You must respond with valid JSON only."
                else:
                    messages.insert(0, {
                        "role": "system",
                        "content": "You must respond with valid JSON only."
                    })

            params.update(kwargs)

            logger.info(f"Calling Google AI Studio API with model: {model}")

            # Make the API call with timeout to prevent hanging
            response = await self.client.chat.completions.create(
                timeout=30.0,  # MVP: Add 30 second timeout
                **params
            )

            logger.info(f"Google AI Studio API call successful")
            return response

        except Exception as error:
            error_details = self._extract_error_details(error)

            if error_details["is_rate_limit"]:
                logger.warning(f"Google AI Studio rate limit exceeded: {error_details['message']}")
                raise GoogleAIStudioError(
                    f"Google AI Studio rate limit exceeded: {error_details['message']}",
                    error_type="rate_limit",
                    is_rate_limit=True
                ) from error
            else:
                logger.error(f"Google AI Studio API error: {error_details['message']}")
                raise GoogleAIStudioError(
                    f"Google AI Studio API error: {error_details['message']}",
                    error_type="api_error",
                    is_rate_limit=False
                ) from error

    def is_configured(self) -> bool:
        """Check if client is properly configured.

        Returns:
            True if API key is available
        """
        return bool(self.api_key)


def create_google_ai_studio_client(api_key: str = None) -> GoogleAIClient:
    """Create Google AI Studio client.

    Args:
        api_key: Google AI Studio API key

    Returns:
        Configured GoogleAIClient instance
    """
    return GoogleAIClient(api_key=api_key)


def is_google_ai_studio_available() -> bool:
    """Check if Google AI Studio API key is available.

    Returns:
        True if GOOGLE_AI_STUDIO_API_KEY environment variable is set
    """
    return bool(os.getenv("GOOGLE_AI_STUDIO_API_KEY"))