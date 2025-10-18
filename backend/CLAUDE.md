
## 🚀 ВАЖНО: Правильный запуск сервера (сохрани себе время!)

### Проблемы, которые возникают:
- API ключ не загружается из .env файла
- Сервер запускается без переменных окружения
- uv не передает переменные окружения в приложение

### РЕШЕНИЕ:
1. **Убедись что в main.py есть load_dotenv():**
   ```python
   from dotenv import load_dotenv
   load_dotenv()  # Должно быть в начале файла
   ```

2. **Запускай сервер ТОЛЬКО ТАК:**
   ```bash
   cd backend && uv run uvicorn src.api.main:app --reload --port 8000
   ```

3. **Проверь что API ключ загружен:**
   ```bash
   curl -s http://localhost:8000/health | grep openai_configured
   # Должно вернуть: "openai_configured":true
   ```

## 📝 Правильная отправка запросов в API

### Формат запроса:
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "ТЕКСТ ЗАПРОСА НА РУССКОМ"}' \
  -o /tmp/result.json
```

### ВАЖНО:
- Endpoint: `/api/v1/query` (НЕ /api/query, НЕ /query)
- Поле: `query` (НЕ question, НЕ text)
- Content-Type обязателен
- Результат в SSE формате (Server-Sent Events)

### Пример полного теста:
```bash
# Отправить запрос
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что автор пишет про AI агентов?"}' \
  -o /tmp/test.json

# Подождать обработку (30-40 сек)
sleep 35

# Посмотреть результат
tail -5 /tmp/test.json | grep main_sources
```

## Language Enforcement System

### Purpose
Multi-lingual support system that detects query language and enforces consistent response language across all LLM calls.

### Key Components
- `utils/language_utils.py:10-60` - Language detection engine
- `utils/language_utils.py:62-104` - Language instruction generation
- `utils/language_utils.py:107-172` - Prompt preparation utilities

### Integration Points
The language system is integrated into all core LLM services:
- **Map Service** (`services/map_service.py:18`) - Uses `prepare_system_message_with_language()` for language enforcement
- **Reduce Service** (`services/reduce_service.py:15`) - Uses `prepare_system_message_with_language()`
- **Comment Group Map Service** (`services/comment_group_map_service.py:22`) - Uses `prepare_prompt_with_language_instruction()`
- **Comment Synthesis Service** (`services/comment_synthesis_service.py:13`) - Uses both system message and prompt preparation functions

### Language Detection Logic
- Analyzes character patterns (ASCII vs Cyrillic)
- Counts words for more accurate detection
- Defaults to Russian for ambiguous cases
- Enforces response language regardless of source content language

### Usage Pattern
```python
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

# Method 1: System message override (preferred for LLMs)
system_message = prepare_system_message_with_language(base_system, query)

# Method 2: Prompt prepending (fallback method)
enhanced_prompt = prepare_prompt_with_language_instruction(prompt_template, query)
```

## ⚠️ Частые ошибки:
- ❌ source .env && uv run... - НЕ РАБОТАЕТ
- ❌ export $(cat .env) && uv run... - НЕ РАБОТАЕТ
- ❌ uv run --env-file .env... - НЕ РАБОТАЕТ
- ✅ load_dotenv() в main.py - РАБОТАЕТ!

