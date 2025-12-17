# backend/src/config.py

import os

"""
Централизованный модуль для управления конфигурацией приложения.
Все переменные окружения считываются здесь, чтобы обеспечить единый источник истины.
"""

# --- Вспомогательные функции ---
def _mask_value(value: str) -> str:
    """Маскирует чувствительные значения для безопасного вывода в логи."""
    if not isinstance(value, str) or len(value) < 12:
        return "Not configured or too short to mask"
    return f"{value[:5]}...{value[-4:]}"

# --- API Ключи ---
GOOGLE_AI_STUDIO_API_KEYS_STR = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
GOOGLE_AI_STUDIO_API_KEYS = [
    key.strip() for key in (GOOGLE_AI_STUDIO_API_KEYS_STR or "").split(',') if key.strip()
]

# --- Model Configuration ---
# Only Google Gemini models are supported.
# Defined in .env or defaulting to stable versions here.

MODEL_MAP: str = os.getenv("MODEL_MAP", "gemini-2.5-flash-lite")

MODEL_SYNTHESIS: str = os.getenv("MODEL_SYNTHESIS", "gemini-3-flash")

MODEL_ANALYSIS: str = os.getenv("MODEL_ANALYSIS", "gemini-2.0-flash")

MODEL_MEDIUM_SCORING: str = os.getenv("MODEL_MEDIUM_SCORING", "gemini-2.0-flash")

MODEL_COMMENT_GROUPS: str = os.getenv("MODEL_COMMENT_GROUPS", "gemini-2.0-flash")

# --- Medium Scoring Configuration ---
# Threshold for accepting medium posts (0.0-1.0)
MEDIUM_SCORE_THRESHOLD: float = float(os.getenv("MEDIUM_SCORE_THRESHOLD", "0.7"))
# Max number of medium posts to include in context
MEDIUM_MAX_SELECTED_POSTS: int = int(os.getenv("MEDIUM_MAX_SELECTED_POSTS", "5"))
# Hard limit on posts processed to prevent OOM
MEDIUM_MAX_POSTS: int = int(os.getenv("MEDIUM_MAX_POSTS", "50"))

# --- Лимиты (Rate Limiting) ---
MAP_MAX_PARALLEL: int = int(os.getenv("MAP_MAX_PARALLEL", "8"))

# --- Прочие настройки ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/experts.db")

# --- Конфигурация логирования ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
# Use relative paths for development, absolute for production
if os.getenv("ENVIRONMENT") == "production":
    BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "/app/data/backend.log")
    FRONTEND_LOG_FILE: str = os.getenv("FRONTEND_LOG_FILE", "/app/data/frontend.log")
else:
    BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "data/backend.log")
    FRONTEND_LOG_FILE: str = os.getenv("FRONTEND_LOG_FILE", "data/frontend.log")

# Логирование для проверки при запуске
if os.getenv("ENVIRONMENT") != "production":
    print("--- Загруженная конфигурация API ---")
    if GOOGLE_AI_STUDIO_API_KEYS:
        print(f"  Google AI Studio Keys: Configured ({len(GOOGLE_AI_STUDIO_API_KEYS)} keys)")
    else:
        print("  Google AI Studio Keys: Not configured")

    print("\n--- Загруженная конфигурация моделей ---")
    print(f"  Map фаза:          {MODEL_MAP}")
    print(f"  Синтез:            {MODEL_SYNTHESIS}")
    print(f"  Анализ:            {MODEL_ANALYSIS}")
    print("--------------------------------------")
    print("--- Загруженная конфигурация логирования ---")
    print(f"  Log Level:         {LOG_LEVEL}")
    print(f"  Backend Log File:  {BACKEND_LOG_FILE}")
    print(f"  Frontend Log File: {FRONTEND_LOG_FILE}")
    print("------------------------------------------")
else:
    # В production не выводим чувствительные данные
    print("--- Production mode: API configuration loaded ---")