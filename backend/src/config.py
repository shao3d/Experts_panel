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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
GOOGLE_AI_STUDIO_API_KEYS_STR = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
GOOGLE_AI_STUDIO_API_KEYS = [
    key.strip() for key in (GOOGLE_AI_STUDIO_API_KEYS_STR or "").split(',') if key.strip()
]

# --- Model Configuration ---
# The settings below define the DEFAULT models.
# You can OVERRIDE any of these in your `backend/.env` file.

# Модели для Map фазы (гибридная система)
# Primary: The model to try first.
# Fallback: The model to use if the primary fails with a rate-limit/quota error.
MODEL_MAP_PRIMARY: str = os.getenv("MODEL_MAP_PRIMARY", "qwen/qwen-2.5-72b-instruct")
MODEL_MAP_FALLBACK: str = os.getenv("MODEL_MAP_FALLBACK", "gemini-2.0-flash-lite")

# Модели для Синтеза (Reduce, Comment Synthesis) - гибридный механизм №2
MODEL_SYNTHESIS_PRIMARY: str = os.getenv("MODEL_SYNTHESIS_PRIMARY", "gemini-2.0-flash")
MODEL_SYNTHESIS_FALLBACK: str = os.getenv("MODEL_SYNTHESIS_FALLBACK", "qwen/qwen-2.5-72b-instruct")

# Модель для анализа (Medium Scoring, Translation, Validation)
# Значение по умолчанию согласовано с .env.example
MODEL_ANALYSIS: str = os.getenv("MODEL_ANALYSIS", "qwen/qwen-2.5-72b-instruct")

# Модель для поиска групп комментариев
MODEL_COMMENT_GROUPS: str = os.getenv("MODEL_COMMENT_GROUPS", "qwen/qwen-2.5-72b-instruct")

# --- Назначение моделей для конкретных сервисов ---
# Эти переменные читают значения из гибридных настроек выше для обратной совместимости.
MODEL_MAP: str = MODEL_MAP_PRIMARY
MODEL_REDUCE: str = MODEL_SYNTHESIS_PRIMARY
MODEL_COMMENT_SYNTHESIS: str = MODEL_SYNTHESIS_PRIMARY

# --- Прочие настройки ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/experts.db")

# --- Конфигурация логирования ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "/app/data/backend.log")
FRONTEND_LOG_FILE: str = os.getenv("FRONTEND_LOG_FILE", "/app/data/frontend.log")

# Логирование для проверки при запуске
if os.getenv("ENVIRONMENT") != "production":
    print("--- Загруженная конфигурация API ---")
    print(f"  OpenRouter API Key:    {_mask_value(OPENROUTER_API_KEY)}")

    if GOOGLE_AI_STUDIO_API_KEYS:
        print(f"  Google AI Studio Keys: Configured ({len(GOOGLE_AI_STUDIO_API_KEYS)} keys)")
    else:
        print("  Google AI Studio Keys: Not configured")

    print("\n--- Загруженная конфигурация моделей ---")
    print(f"  Map фаза (Primary):    {MODEL_MAP_PRIMARY}")
    print(f"  Map фаза (Fallback):   {MODEL_MAP_FALLBACK}")
    print(f"  Синтез (Primary):      {MODEL_SYNTHESIS_PRIMARY}")
    print(f"  Синтез (Fallback):     {MODEL_SYNTHESIS_FALLBACK}")
    print(f"  Анализ (Scoring/etc):  {MODEL_ANALYSIS}")
    print(f"  Группы коммент.:       {MODEL_COMMENT_GROUPS}")
    print("--------------------------------------")
    print("--- Загруженная конфигурация логирования ---")
    print(f"  Log Level:         {LOG_LEVEL}")
    print(f"  Backend Log File:  {BACKEND_LOG_FILE}")
    print(f"  Frontend Log File: {FRONTEND_LOG_FILE}")
    print("------------------------------------------")
else:
    # В production не выводим чувствительные данные
    print("--- Production mode: API configuration loaded ---")