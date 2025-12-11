"""Monitored Google Gemini LLM client.

This module provides a monitored interface for Google AI Studio.
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List

from .google_ai_studio_client import (
    GoogleAIClient, GoogleAIStudioError, create_google_ai_studio_client
)
from .llm_monitor import log_api_call_with_timing

logger = logging.getLogger(__name__)


class MonitoredLLMClient:
    """LLM client that uses Google AI Studio with monitoring."""

    def __init__(
        self
    ):
        """Initialize LLM client."""
        self.google_available = True

        self.google_client = None

        try:
            self.google_client = create_google_ai_studio_client()
            logger.info("LLM client initialized with Google AI Studio")
        except Exception as e:
            logger.warning(f"Failed to initialize Google AI Studio client: {e}")
            self.google_available = False

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        service_name: str = "unknown",
        **kwargs
    ) -> Any:
        """Create chat completion using Google AI Studio.

        Args:
            model: Model name (e.g., "gemini-2.0-flash")
            messages: List of message dictionaries
            temperature: Sampling temperature
            response_format: Response format specification
            service_name: Service name for logging (e.g., "reduce", "comment_synthesis")
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        
        if not self.google_client:
            raise RuntimeError(f"[{service_name}] Google AI Studio client not initialized")

        start_time = time.time()
        try:
            # logger.info(f"[{service_name}] Calling Google AI Studio API with model: {model}")

            response = await self.google_client.chat_completions_create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                **kwargs
            )
            # logger.info(f"[{service_name}] Google AI Studio API call successful")

            log_api_call_with_timing(
                service_name=service_name,
                provider="google_ai_studio",
                model=model,
                start_time=start_time,
                success=True,
                response=response
            )

            return response

        except Exception as e:
            log_api_call_with_timing(
                service_name=service_name,
                provider="google_ai_studio",
                model=model,
                start_time=start_time,
                success=False,
                error=e
            )
            logger.error(f"[{service_name}] Google AI Studio API call failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get client status information.

        Returns:
            Dictionary with client status
        """
        return {
            "google_ai_studio_available": self.google_available
        }


def create_monitored_client() -> MonitoredLLMClient:
    """Create monitored LLM client.

    Returns:
        Configured MonitoredLLMClient instance
    """
    return MonitoredLLMClient()