"""Error Handling Utility

Centralizes error handling and provides user-friendly error responses.
"""

import logging
from typing import Dict, Any, Optional
from ..utils.api_error_detector import APIErrorDetector

logger = logging.getLogger(__name__)


class QueryErrorHandler:
    """Handles errors in query processing and provides user-friendly responses."""

    def __init__(self):
        self.error_detector = APIErrorDetector()

    def process_api_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process API error and return user-friendly error information.

        Args:
            error: The exception that occurred
            context: Additional context (phase, expert_id, etc.)

        Returns:
            Dictionary with error information for SSE event
        """
        error_message = str(error)
        context = context or {}

        # Extract status code from error message if available
        status_code = self._extract_status_code(error_message)

        # Get error information from detector
        error_info = self.error_detector.get_error_info(error_message, status_code)

        # Add context information
        error_info.update({
            "phase": context.get("phase", "unknown"),
            "expert_id": context.get("expert_id", "unknown"),
            "timestamp": context.get("timestamp"),
            "request_id": context.get("request_id")
        })

        logger.info(f"Processed API error: {error_info['error_type']} - {error_info['title']}")

        return error_info

    def _extract_status_code(self, error_message: str) -> Optional[int]:
        """Extract HTTP status code from error message."""
        import re
        match = re.search(r'Error code: (\d+)', error_message)
        if match:
            return int(match.group(1))
        return None

    def create_error_event(self, error_info: Dict[str, Any], event_type: str = "error") -> Dict[str, Any]:
        """
        Create SSE error event from error information.

        Args:
            error_info: Error information from process_api_error
            event_type: Type of SSE event (error, expert_error, etc.)

        Returns:
            Dictionary ready for SSE event
        """
        return {
            "event_type": event_type,
            "phase": error_info.get("phase", "unknown"),
            "status": "error",
            "message": error_info["title"],
            "data": {
                "error_type": error_info["error_type"],
                "user_message": error_info["message"],
                "suggested_action": error_info["suggested_action"],
                "expert_id": error_info.get("expert_id"),
                "original_error": error_info.get("original_error"),
                "status_code": error_info.get("status_code"),
                "user_friendly": error_info["user_friendly"]
            }
        }

    def is_payment_error(self, error: Exception) -> bool:
        """Quick check if error is payment-related."""
        return self.error_detector.is_payment_error(str(error))


# Global error handler instance
error_handler = QueryErrorHandler()