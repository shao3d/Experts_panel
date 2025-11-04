# backend/src/config.py

import os

"""
Централизованный модуль для управления конфигурацией приложения.
Все переменные окружения считываются здесь, чтобы обеспечить единый источник истины.
"""

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
print("--- Загруженная конфигурация моделей ---")
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