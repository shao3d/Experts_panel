"""Google AI Studio API client for direct Gemini API access.

This module provides a client for calling Google AI Studio's Gemini API directly,
bypassing OpenRouter to take advantage of free tier limits when possible.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
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
        genai.configure(api_key=api_key)

    def _is_rate_limit_error(self, error_content: str) -> bool:
        """Check if error indicates rate limit exceeded.

        Args:
            error_content: Error message content

        Returns:
            True if this is a rate limit error
        """
        error_lower = error_content.lower()
        return any(pattern.lower() in error_lower for pattern in self.RATE_LIMIT_ERRORS)

    def _convert_openai_json_to_gemini_schema(self, response_format: Optional[Dict[str, str]]) -> Optional[Dict[str, Any]]:
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

            # Convert OpenAI messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini_format(messages)

            # Create generation config
            generation_config = {
                "temperature": temperature,
                "candidate_count": 1,
            }

            # Handle JSON response format for Gemini
            if response_format and response_format.get("type") == "json_object":
                # Convert OpenAI JSON format to Gemini Schema
                gemini_schema = self._convert_openai_json_to_gemini_schema(response_format)
                if gemini_schema:
                    # Use Gemini's native JSON mode
                    generation_config["response_mime_type"] = "application/json"
                    try:
                        generation_config["response_schema"] = genai.Schema(**gemini_schema)
                        logger.info(f"Using Gemini native JSON mode with schema")
                    except Exception as e:
                        logger.warning(f"Failed to create Gemini schema: {e}, using fallback JSON instruction")
                        # Fallback to JSON instruction
                        if gemini_messages:
                            gemini_messages[0] = gemini_messages[0] + "\n\nIMPORTANT: You must respond with valid JSON only."
                else:
                    # Fallback: Add JSON instruction to first message
                    if gemini_messages:
                        gemini_messages[0] = gemini_messages[0] + "\n\nIMPORTANT: You must respond with valid JSON only."

            # Update generation config with additional kwargs
            for key, value in kwargs.items():
                if key not in ["response_format"]:  # Skip response_format as we handle it separately
                    generation_config[key] = value

            logger.info(f"Calling Google AI Studio API with model: {model}")

            # Create model and make the API call
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

            # Make the API call
            response = await gemini_model.generate_content_async(gemini_messages)

            logger.info(f"Google AI Studio API call successful")

            # Convert Gemini response to OpenAI format for compatibility
            return self._convert_gemini_response_to_openai_format(response)

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