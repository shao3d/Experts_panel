# backend/src/config.py

import os

"""
Централизованный модуль для управления конфигурацией приложения.
Все переменные окружения считываются здесь, чтобы обеспечить единый источник истины.
"""

# --- API Ключи ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

# --- Конфигурация моделей для каждой фазы ---

# Модель для Map фазы (только для поиска релевантных постов)
# Использует Qwen 2.5 72B для максимального качества relevance detection
# Если не задана в .env, использует значение по умолчанию
MODEL_MAP: str = os.getenv("MODEL_MAP", "qwen/qwen-2.5-72b-instruct")

# Модель для анализа (Medium Scoring, Translation, Validation)
# Значение по умолчанию согласовано с .env.example
MODEL_ANALYSIS: str = os.getenv("MODEL_ANALYSIS", "qwen/qwen-2.5-72b-instruct")

# Модель для синтеза ответа (Reduce)
MODEL_REDUCE: str = os.getenv("MODEL_REDUCE", "gemini-2.0-flash")

# Модель для поиска групп комментариев
MODEL_COMMENT_GROUPS: str = os.getenv("MODEL_COMMENT_GROUPS", "qwen/qwen-2.5-72b-instruct")

# Модель для синтеза из комментариев
MODEL_COMMENT_SYNTHESIS: str = os.getenv("MODEL_COMMENT_SYNTHESIS", "gemini-2.0-flash")

# --- Прочие настройки ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/experts.db")

# Логирование для проверки при запуске
print("--- Загруженная конфигурация моделей ---")
print(f"  Map фаза:           {MODEL_MAP}")
print(f"  Анализ (Scoring):   {MODEL_ANALYSIS}")
print(f"  Синтез (Reduce):     {MODEL_REDUCE}")
print(f"  Группы коммент.:     {MODEL_COMMENT_GROUPS}")
print(f"  Синтез коммент.:   {MODEL_COMMENT_SYNTHESIS}")
print("------------------------------------")