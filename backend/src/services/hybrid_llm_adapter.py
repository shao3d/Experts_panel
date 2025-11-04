"""Hybrid LLM adapter combining Google AI Studio and OpenRouter.

This module provides a unified interface that tries Google AI Studio first,
then falls back to OpenRouter when rate limits are exceeded.
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI

from .google_ai_studio_client import (
    GoogleAIClient, GoogleAIStudioError, create_google_ai_studio_client, is_google_ai_studio_available
)
from .openrouter_adapter import create_openrouter_client, convert_model_name
from .hybrid_llm_monitor import log_api_call_with_timing

logger = logging.getLogger(__name__)


class HybridLLMClient:
    """Hybrid LLM client that tries Google AI Studio first, then falls back to OpenRouter."""

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        fallback_model: str = None,
        enable_hybrid: bool = True
    ):
        """Initialize hybrid LLM client.

        Args:
            openrouter_api_key: OpenRouter API key (fallback)
            fallback_model: The specific model to use on OpenRouter during a fallback.
            enable_hybrid: Enable hybrid mode (try Google AI Studio first)
        """
        self.enable_hybrid = enable_hybrid
        self.google_available = is_google_ai_studio_available()
        self.fallback_model = fallback_model

        # Initialize clients
        self.openrouter_client = create_openrouter_client(openrouter_api_key)
        self.google_client = None

        if self.google_available and enable_hybrid:
            try:
                self.google_client = create_google_ai_studio_client()
                logger.info("Hybrid LLM client initialized with Google AI Studio as primary")
            except Exception as e:
                logger.warning(f"Failed to initialize Google AI Studio client: {e}")
                self.google_available = False

        if not self.google_available:
            logger.info("Hybrid LLM client using OpenRouter only")

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None,
        service_name: str = "unknown",
        **kwargs
    ) -> Any:
        """Create chat completion with hybrid fallback logic.

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
        # Determine if the model is a Google model to avoid unnecessary API calls
        is_google_model = "gemini" in model or model.startswith("google/")

        # First try Google AI Studio if available and enabled
        if self.enable_hybrid and self.google_available and self.google_client and is_google_model:
            start_time = time.time()
            try:
                logger.info(f"[{service_name}] Trying Google AI Studio API with model: {model}")

                # Google AI Studio uses native JSON format, OpenRouter uses OpenAI format
                response = await self.google_client.chat_completions_create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,  # Will be converted to Gemini format internally
                    **kwargs
                )
                logger.info(f"[{service_name}] Google AI Studio API call successful")

                # Log successful call
                log_api_call_with_timing(
                    service_name=service_name,
                    provider="google_ai_studio",
                    model=model,
                    start_time=start_time,
                    success=True,
                    response=response,
                    is_fallback=False
                )

                return response

            except GoogleAIStudioError as e:
                # Log failed call
                log_api_call_with_timing(
                    service_name=service_name,
                    provider="google_ai_studio",
                    model=model,
                    start_time=start_time,
                    success=False,
                    error=e,
                    is_fallback=False
                )

                if e.is_rate_limit:
                    logger.warning(f"[{service_name}] Google AI Studio rate limit exceeded, switching to OpenRouter: {e}")
                else:
                    logger.error(f"[{service_name}] Google AI Studio API error, switching to OpenRouter: {e}")
            except Exception as e:
                # Log failed call
                log_api_call_with_timing(
                    service_name=service_name,
                    provider="google_ai_studio",
                    model=model,
                    start_time=start_time,
                    success=False,
                    error=e,
                    is_fallback=False
                )
                logger.error(f"[{service_name}] Unexpected Google AI Studio error, switching to OpenRouter: {e}")

        # Fallback to OpenRouter with OpenAI format
        start_time = time.time()
        # Determine which model to use for fallback
        fallback_model_to_use = self.fallback_model or model # Use configured fallback, or default to original model if not set
        openrouter_model_name = convert_model_name(fallback_model_to_use)
        logger.info(f"[{service_name}] Using OpenRouter API with model: {openrouter_model_name} (OpenAI JSON format)")

        try:
            response = await self.openrouter_client.chat.completions.create(
                model=openrouter_model_name,
                messages=messages,
                temperature=temperature,
                response_format=response_format,  # OpenAI format
                timeout=30.0,  # MVP: Add 30 second timeout
                **kwargs
            )
            logger.info(f"[{service_name}] OpenRouter API call successful")

            # Log successful fallback call
            log_api_call_with_timing(
                service_name=service_name,
                provider="openrouter",
                model=openrouter_model_name,
                start_time=start_time,
                success=True,
                response=response,
                is_fallback=self.enable_hybrid and self.google_available
            )

            return response

        except Exception as e:
            # Log failed fallback call
            log_api_call_with_timing(
                service_name=service_name,
                provider="openrouter",
                model=openrouter_model_name,
                start_time=start_time,
                success=False,
                error=e,
                is_fallback=self.enable_hybrid and self.google_available
            )
            logger.error(f"[{service_name}] OpenRouter API call failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get client status information.

        Returns:
            Dictionary with client status
        """
        return {
            "hybrid_enabled": self.enable_hybrid,
            "google_ai_studio_available": self.google_available,
            "google_ai_studio_configured": self.google_client is not None,
            "openrouter_available": self.openrouter_client is not None
        }


def create_hybrid_client(
    openrouter_api_key: str = None,
    fallback_model: str = None,
    enable_hybrid: bool = None
) -> HybridLLMClient:
    """Create hybrid LLM client.

    Args:
        openrouter_api_key: OpenRouter API key (fallback)
        fallback_model: The specific model to use on OpenRouter during a fallback.
        enable_hybrid: Enable hybrid mode (defaults to True if both keys available)

    Returns:
        Configured HybridLLMClient instance
    """
    if enable_hybrid is None:
        # Enable hybrid mode by default if both APIs are available
        enable_hybrid = is_google_ai_studio_available() and (
            openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )

    return HybridLLMClient(
        openrouter_api_key=openrouter_api_key,
        fallback_model=fallback_model,
        enable_hybrid=enable_hybrid
    )


def is_hybrid_mode_enabled() -> bool:
    """Check if hybrid mode is enabled.

    Returns:
        True if hybrid mode is enabled
    """
    return os.getenv("HYBRID_ENABLED", "true").lower() in ["true", "1", "yes", "on"]