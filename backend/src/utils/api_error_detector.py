"""API Error Detection Utility

This module provides utilities for detecting different types of API errors
and categorizing them for user-friendly error messages.
"""

import re
from typing import Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of API errors for user-friendly messaging."""
    PAYMENT_REQUIRED = "payment_required"
    RATE_LIMIT = "rate_limit"
    INVALID_REQUEST = "invalid_request"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    MODEL_UNAVAILABLE = "model_unavailable"
    NETWORK_ERROR = "network_error"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


class APIErrorDetector:
    """Detects and categorizes API errors for user-friendly messaging."""

    # Error patterns for different error types
    ERROR_PATTERNS = {
        ErrorType.PAYMENT_REQUIRED: [
            r'402\s+Payment\s+Required',
            r'Insufficient\s+credits',
            r'prepayment\s+credits?\s+are\s+depleted',
            r'credits?\s+are\s+depleted',
            r'payment.*required',
            r'billing.*issue',
            r'manage\s+your\s+project\s+and\s+billing',
            r'quota.*exceeded',
            r'account.*suspended'
        ],
        ErrorType.RATE_LIMIT: [
            r'429\s+Too\s+Many\s+Requests',
            r'rate\s+limit',
            r'too\s+many\s+requests',
            r'request\s+limit',
            r'frequency\s+limit'
        ],
        ErrorType.INVALID_REQUEST: [
            r'400\s+Bad\s+Request',
            r'invalid\s+request',
            r'malformed\s+request',
            r'invalid\s+parameter',
            r'missing\s+parameter'
        ],
        ErrorType.INSUFFICIENT_PERMISSIONS: [
            r'401\s+Unauthorized',
            r'403\s+Forbidden',
            r'invalid\s+api\s+key',
            r'insufficient\s+permissions',
            r'access\s+denied',
            r'authentication\s+failed'
        ],
        ErrorType.MODEL_UNAVAILABLE: [
            r'model.*not.*found',
            r'model.*unavailable',
            r'invalid.*model',
            r'model.*deprecated',
            r'capacity.*exceeded'
        ],
        ErrorType.NETWORK_ERROR: [
            r'connection.*timeout',
            r'network.*error',
            r'dns.*resolution.*failed',
            r'connection.*refused',
            r'ssl.*error',
            r'certificate.*error'
        ],
        ErrorType.SERVER_ERROR: [
            r'500\s+Internal\s+Server\s+Error',
            r'502\s+Bad\s+Gateway',
            r'503\s+Service\s+Unavailable',
            r'504\s+Gateway\s+Timeout',
            r'server.*error',
            r'service.*unavailable'
        ]
    }

    # User-friendly messages for each error type
    ERROR_MESSAGES = {
        ErrorType.PAYMENT_REQUIRED: {
            "title": "Oops, we've got a problem with the service...",
            "message": "Please try again in a few minutes. If the problem persists, there might be technical maintenance ongoing.",
            "user_friendly": True,
            "suggested_action": "Try again later or contact the administrator"
        },
        ErrorType.RATE_LIMIT: {
            "title": "⚠️ Слишком много запросов",
            "message": "Пожалуйста, подождите несколько минут и попробуйте снова.",
            "user_friendly": True,
            "suggested_action": "Подождите и повторите запрос"
        },
        ErrorType.INVALID_REQUEST: {
            "title": "❌ Неверный формат запроса",
            "message": "Пожалуйста, проверьте ваш запрос и попробуйте снова.",
            "user_friendly": True,
            "suggested_action": "Проверьте параметры запроса"
        },
        ErrorType.INSUFFICIENT_PERMISSIONS: {
            "title": "🔒 Ошибка доступа",
            "message": "Проблемы с доступом к сервису. Пожалуйста, попробуйте позже.",
            "user_friendly": True,
            "suggested_action": "Попробуйте позже или свяжитесь с поддержкой"
        },
        ErrorType.MODEL_UNAVAILABLE: {
            "title": "🔧 Сервис моделей временно недоступен",
            "message": "Некоторые модели обработки недоступны. Пожалуйста, попробуйте позже.",
            "user_friendly": True,
            "suggested_action": "Попробуйте позже"
        },
        ErrorType.NETWORK_ERROR: {
            "title": "🌐 Проблемы с подключением",
            "message": "Проблемы с сетевым подключением. Пожалуйста, проверьте интернет и попробуйте снова.",
            "user_friendly": True,
            "suggested_action": "Проверьте подключение к интернету"
        },
        ErrorType.SERVER_ERROR: {
            "title": "🔧 Временные технические проблемы",
            "message": "Сервис временно недоступен. Мы уже работаем над исправлением.",
            "user_friendly": True,
            "suggested_action": "Попробуйте позже"
        },
        ErrorType.UNKNOWN_ERROR: {
            "title": "❌ Произошла ошибка",
            "message": "Пожалуйста, попробуйте еще раз. Если проблема сохраняется, свяжитесь с администратором.",
            "user_friendly": True,
            "suggested_action": "Попробуйте еще раз"
        }
    }

    @classmethod
    def detect_error_type(cls, error_message: str, status_code: Optional[int] = None) -> ErrorType:
        """
        Detect the type of API error from error message and status code.

        Args:
            error_message: The error message from API response
            status_code: HTTP status code (if available)

        Returns:
            ErrorType enum value
        """
        if not error_message:
            return ErrorType.UNKNOWN_ERROR

        error_message_lower = error_message.lower()

        # Check each error type pattern
        for error_type, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_message, re.IGNORECASE):
                    logger.debug(f"Detected error type {error_type.value} from message: {error_message}")
                    return error_type

        # Fallback to status code if available
        if status_code:
            if status_code == 402:
                return ErrorType.PAYMENT_REQUIRED
            elif status_code == 429:
                return ErrorType.RATE_LIMIT
            elif status_code in [400, 422]:
                return ErrorType.INVALID_REQUEST
            elif status_code in [401, 403]:
                return ErrorType.INSUFFICIENT_PERMISSIONS
            elif status_code in [500, 502, 503, 504]:
                return ErrorType.SERVER_ERROR

        return ErrorType.UNKNOWN_ERROR

    @classmethod
    def get_error_info(cls, error_message: str, status_code: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive error information for user-friendly messaging.

        Args:
            error_message: The error message from API response
            status_code: HTTP status code (if available)

        Returns:
            Dictionary with error information
        """
        error_type = cls.detect_error_type(error_message, status_code)
        error_config = cls.ERROR_MESSAGES[error_type]

        return {
            "error_type": error_type.value,
            "title": error_config["title"],
            "message": error_config["message"],
            "user_friendly": error_config["user_friendly"],
            "suggested_action": error_config["suggested_action"],
            "original_error": error_message,
            "status_code": status_code
        }

    @classmethod
    def is_payment_error(cls, error_message: str) -> bool:
        """
        Quick check if error is related to payment/credits.

        Args:
            error_message: The error message to check

        Returns:
            True if this is a payment-related error
        """
        return cls.detect_error_type(error_message) == ErrorType.PAYMENT_REQUIRED
