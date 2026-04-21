"""Monitored Gemini LLM client.

This module provides a monitored interface for Vertex AI.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from .vertex_llm_client import get_vertex_llm_client
from .llm_monitor import log_api_call_with_timing

logger = logging.getLogger(__name__)


class MonitoredLLMClient:
    """LLM client that uses Vertex AI with monitoring."""

    def __init__(
        self
    ):
        """Initialize LLM client."""
        self.vertex_available = True

        self.llm_client = None

        try:
            self.llm_client = get_vertex_llm_client()
            logger.info("LLM client initialized with Vertex AI")
        except Exception as e:
            logger.warning(f"Failed to initialize Vertex AI client: {e}")
            self.vertex_available = False

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        service_name: str = "unknown",
        **kwargs
    ) -> Any:
        """Create chat completion using Vertex AI.

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
        
        if not self.llm_client:
            raise RuntimeError(f"[{service_name}] Vertex AI client not initialized")

        start_time = time.time()
        try:
            response = await self.llm_client.chat_completions_create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                **kwargs
            )

            log_api_call_with_timing(
                service_name=service_name,
                provider="vertex_ai",
                model=model,
                start_time=start_time,
                success=True,
                response=response
            )

            return response

        except Exception as e:
            log_api_call_with_timing(
                service_name=service_name,
                provider="vertex_ai",
                model=model,
                start_time=start_time,
                success=False,
                error=e
            )
            logger.error(f"[{service_name}] Vertex AI API call failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get client status information.

        Returns:
            Dictionary with client status
        """
        return {
            "vertex_ai_available": self.vertex_available
        }


def create_monitored_client() -> MonitoredLLMClient:
    """Create monitored LLM client.

    Returns:
        Configured MonitoredLLMClient instance
    """
    return MonitoredLLMClient()
