"""LLM monitoring and logging utilities.

This module provides logging and monitoring for LLM operations.
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LLMApiCall:
    """Record of an LLM API call for monitoring."""
    service_name: str
    provider: str  # "google_ai_studio"
    model: str
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None
    token_usage: Optional[Dict[str, int]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class LLMMonitor:
    """Monitor for LLM operations."""

    # MVP: Limit history size to prevent memory leak
    MAX_API_CALLS_HISTORY = 100

    def __init__(self):
        self.api_calls: list[LLMApiCall] = []
        self.success_count = 0
        self.error_count = 0

    def record_api_call(
        self,
        service_name: str,
        provider: str,
        model: str,
        success: bool,
        response_time_ms: int = None,
        token_usage: Dict[str, int] = None,
        error_type: str = None,
        error_message: str = None
    ):
        """Record an LLM API call.

        Args:
            service_name: Service name (e.g., "reduce", "comment_synthesis")
            provider: API provider ("google_ai_studio")
            model: Model name used
            success: Whether the call was successful
            response_time_ms: Response time in milliseconds
            token_usage: Token usage information
            error_type: Type of error if failed
            error_message: Error message if failed
        """
        call = LLMApiCall(
            service_name=service_name,
            provider=provider,
            model=model,
            success=success,
            error_type=error_type,
            error_message=error_message,
            response_time_ms=response_time_ms,
            token_usage=token_usage
        )

        self.api_calls.append(call)

        # MVP: Prevent memory leak - limit history size
        if len(self.api_calls) > self.MAX_API_CALLS_HISTORY:
            self.api_calls = self.api_calls[-self.MAX_API_CALLS_HISTORY:]

        # Update counters
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        # Log the call
        self._log_api_call(call)

    def _log_api_call(self, call: LLMApiCall):
        """Log an API call with appropriate level.

        Args:
            call: The API call record
        """
        if call.success:
            logger.info(
                f"[{call.service_name}] ✅ SUCCESS: "
                f"{call.provider} ({call.model}) - {call.response_time_ms}ms"
            )
        else:
            if call.error_type == "rate_limit":
                logger.warning(
                    f"[{call.service_name}] ⚠️ RATE_LIMIT: "
                    f"{call.provider} ({call.model}) - {call.error_message}"
                )
            else:
                logger.error(
                    f"[{call.service_name}] ❌ ERROR: "
                    f"{call.provider} ({call.model}) - {call.error_message}"
                )

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        total_calls = len(self.api_calls)
        if total_calls == 0:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "google_ai_studio_usage": 0.0
            }

        # Calculate provider usage (should be 100% google now)
        google_calls = len(self.api_calls)
        
        # Calculate success rate
        google_success = sum(1 for call in self.api_calls if call.success)
        
        # Calculate average response times
        google_times = [call.response_time_ms for call in self.api_calls if call.response_time_ms]

        return {
            "total_calls": total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_count / total_calls if total_calls > 0 else 0.0,
            "google_ai_studio": {
                "calls": google_calls,
                "success_rate": google_success / google_calls if google_calls > 0 else 0.0,
                "avg_response_time_ms": sum(google_times) / len(google_times) if google_times else None
            }
        }

    def log_summary(self):
        """Log a summary of monitoring statistics."""
        stats = self.get_stats()

        if stats["total_calls"] == 0:
            logger.info("🔍 LLM Monitor: No API calls recorded")
            return

        logger.info(f"🔍 LLM Monitor Summary ({stats['total_calls']} calls)")
        logger.info(f"   Success Rate: {stats['success_rate']:.1%}")

        google_stats = stats["google_ai_studio"]
        if google_stats["calls"] > 0:
            logger.info(f"   Google AI Studio: {google_stats['calls']} calls "
                       f"({google_stats['success_rate']:.1%} success)")

    def reset(self):
        """Reset all monitoring data."""
        self.api_calls.clear()
        self.fallback_count = 0
        self.success_count = 0
        self.error_count = 0
        logger.info("🔍 LLM Monitor: Reset all statistics")


# Global monitor instance
_global_monitor: Optional[LLMMonitor] = None


def get_monitor() -> LLMMonitor:
    """Get the global monitor instance.

    Returns:
        LLMMonitor instance
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = LLMMonitor()
    return _global_monitor


def log_api_call_with_timing(
    service_name: str,
    provider: str,
    model: str,
    start_time: float,
    success: bool,
    response: Any = None,
    error: Exception = None,
):
    """Log an API call with timing information.

    Args:
        service_name: Service name (e.g., "reduce", "comment_synthesis")
        provider: API provider ("google_ai_studio")
        model: Model name used
        start_time: Start time from time.time()
        success: Whether the call was successful
        response: Response object if successful
        error: Exception if failed
    """
    response_time_ms = int((time.time() - start_time) * 1000)

    # Extract token usage from response
    token_usage = None
    if response and hasattr(response, 'usage') and response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

    # Extract error information
    error_type = None
    error_message = None
    if error:
        error_type = getattr(error, 'error_type', 'unknown')
        error_message = str(error)

    monitor = get_monitor()
    monitor.record_api_call(
        service_name=service_name,
        provider=provider,
        model=model,
        success=success,
        response_time_ms=response_time_ms,
        token_usage=token_usage,
        error_type=error_type,
        error_message=error_message
    )