"""Deprecated compatibility shim for the legacy client module.

The canonical runtime client now lives in `vertex_llm_client.py`.
Keep this module importable during the transition period so older code paths
continue to work without carrying a second implementation.
"""

from .vertex_llm_client import VertexLLMClient, VertexLLMError, get_vertex_llm_client

GoogleAIClient = VertexLLMClient
GoogleAIStudioError = VertexLLMError


def create_google_ai_studio_client() -> VertexLLMClient:
    """Deprecated compatibility alias for the legacy factory name."""

    return get_vertex_llm_client()

__all__ = [
    "VertexLLMClient",
    "VertexLLMError",
    "get_vertex_llm_client",
    "GoogleAIClient",
    "GoogleAIStudioError",
    "create_google_ai_studio_client",
]
