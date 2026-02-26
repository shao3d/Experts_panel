# Retry Strategy (Google AI Studio)

**Статус:** Implemented ✅
**Дата:** 2026-02-26

---

## Архитектура: 3-Layer Protection

### Layer 1 — Client-Level Retry (Tenacity)
**Где:** `google_ai_studio_client.py` → `chat_completions_create()`

- `AsyncRetrying` с `wait_random_exponential(multiplier=1.5, max=15)`, **5 попыток**.
- Кастомный предикат `_should_retry`: ретраит **только** rate limit (429) и timeout. Auth/BadRequest ошибки проваливаются мгновенно.
- Prompt preparation (JSON instruction concat) вынесен **перед** retry-циклом — фикс бага конкатенации.
- Все ошибки оборачиваются в `GoogleAIStudioError` для единого контракта.
- **Суммарно:** ~15 секунд на обработку TPM-спайков.

### Layer 2 — Service-Level Retry (Tenacity Decorator)
**Где:** `map_service.py` → `_process_chunk()`, `comment_group_map_service.py`, etc.

- `@retry(stop=stop_after_attempt(3), wait=wait_exponential(...))` — ретраит JSONDecodeError, ValueError, httpx ошибки.
- **НЕ** ретраит `GoogleAIStudioError` (не в `retry_if_exception_type`).

### Layer 3 — Global Chunk Retry (Pipeline)
**Где:** `map_service.py` → `process()` (lines 425-460)

- После основного `asyncio.gather()` — собирает failed chunks.
- **45-секундный cooldown** перед повторной попыткой → пересекает 60-сек RPM-окно Google API.
- Максимум 1 глобальная попытка.

---

## Ключевые моменты

| Вопрос | Ответ |
|--------|-------|
| TPM-спайки (токены) | Layer 1: ~15 сек jitter |
| RPM-лимиты (запросы/мин) | Layer 1 (~15с) + Layer 3 cooldown (45с) = ~60с |
| Auth/Bad Request | Мгновенный провал, без ретраев |
| JSON parse ошибки | Layer 2: tenacity decorator |
| Prompt concatenation баг | Исправлен: подготовка промпта вне retry-цикла |
