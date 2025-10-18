"""OpenRouter adapter for OpenAI-compatible API."""

import os
from openai import AsyncOpenAI


def create_openrouter_client(api_key: str = None) -> AsyncOpenAI:
    """Create OpenAI client configured for OpenRouter.

    Args:
        api_key: OpenRouter API key. If not provided, uses OPENAI_API_KEY env var.

    Returns:
        AsyncOpenAI client configured for OpenRouter
    """
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )


def convert_model_name(openai_model: str) -> str:
    """Convert OpenAI model name to OpenRouter format.

    Args:
        openai_model: OpenAI model name (e.g., "gpt-4o-mini")

    Returns:
        OpenRouter model name (e.g., "openai/gpt-4o-mini")
    """
    # Map of common models including Gemini
    model_map = {
        # OpenAI models
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4o": "openai/gpt-4o",
        "gpt-4-turbo": "openai/gpt-4-turbo",
        "gpt-3.5-turbo": "openai/gpt-3.5-turbo",

        # Google Gemini models
        "gemini-2.0-flash": "google/gemini-2.0-flash-001",  # Stable paid version ($0.10/$0.40 per 1M)
        "gemini-2.0-flash-free": "google/gemini-2.0-flash-exp:free",  # Free experimental version
        "gemini-2.5-flash": "google/gemini-2.5-flash",
        "gemini-1.5-flash": "google/gemini-1.5-flash",

        # Alibaba Qwen models (October 2025)
        "qwen-2.5-72b": "qwen/qwen-2.5-72b-instruct",  # $0.08/$0.33 per 1M - great for document ranking
        "qwen-2.5-32b": "qwen/qwen-2.5-32b-instruct",  # Smaller, faster variant
        "qwen-2.5-coder-32b": "qwen/qwen-2.5-coder-32b-instruct"  # Code-specific
    }

    # Return mapped model or add openai/ prefix if not found
    if openai_model in model_map:
        return model_map[openai_model]
    # If model already has a provider prefix (google/, anthropic/, etc.), don't modify
    elif "/" in openai_model:
        return openai_model
    # Only add openai/ prefix to models without any provider prefix
    else:
        return f"openai/{openai_model}"