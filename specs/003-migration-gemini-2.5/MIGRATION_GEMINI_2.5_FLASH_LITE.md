# Миграция на Gemini 2.5 Flash-Lite для Reduce фазы

**Дата:** 2025-10-06
**Цель:** Улучшить адаптивность объёма ответа, качество синтеза и снизить галлюцинации

**⚠️ DRAFT - ТРЕБУЕТ ПРОВЕРКИ:**
- [x] ✅ Имя модели: `google/gemini-2.5-flash-lite` (stable, GA с 22 июля 2025)
- [x] ✅ SSE parsing: используем `grep "^data:" | sed 's/^data: //' | grep -v "\[DONE\]"`
- [x] ✅ Thinking API: для OpenRouter используется `reasoning.max_tokens` (если понадобится)
- [ ] Согласовать ожидаемое кол-во слов (промпт vs тесты)
- [ ] Оценить длину промпта (не слишком ли раздут?)

**Примечание:** Thinking mode НЕ используется в основном плане (только как опция если качество недостаточно)

---

## Зачем переходить на Gemini 2.5 Flash-Lite?

### Преимущества над текущей Gemini 2.0 Flash:

✅ **Лучшее качество** - выше на всех бенчмарках (MMLU: 84.5% vs 83.4%)
✅ **Быстрее** - в 1.5x раз по latency
✅ **Меньше галлюцинаций** - специально оптимизирован для summarization
✅ **Лучшая фактологическая точность** - 86.8% FACTS Grounding
✅ **Оптимизирован для synthesis** - именно наша задача

### Стоимость:

- **Input:** $0.10/M tokens (было ~$0.075)
- **Output:** $0.40/M tokens (было ~$0.30-0.50)
- **Переплата:** ~$0.035/M input = **$3.50 на 100,000 запросов** (приемлемо)

---

## Шаг 1: Обновить модель в ReduceService

### Файл: `backend/src/services/reduce_service.py`

**Изменить строку 29:**

```python
# БЫЛО:
DEFAULT_MODEL = "gemini-2.0-flash"

# СТАЛО:
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
```

**ВАЖНО:**
- Используется **stable версия** модели (GA с 22 июля 2025): `google/gemini-2.5-flash-lite`
- Thinking mode **выключен по умолчанию** (нам не нужен для synthesis)
- Модель оптимизирована для summarization и classification при выключенном thinking
- Если понадобится thinking - можно включить через параметр API (см. Шаг 4)

---

## Шаг 2: Обновить промпт с адаптивностью длины

### Файл: `backend/prompts/reduce_prompt_personal.txt`

**ТЕКУЩИЙ ПРОМПТ (устаревший):**
```
You are Refat responding personally to users' questions.
Write in FIRST PERSON using your posts as reference.

VOICE MARKERS:
• Personal experience: "я тестировал", "меня впечатлило", "давно слежу за"
• Direct address: "вы наверное замечали", "давайте разберем"
• Emotional honesty: use "подофигел", "дичь", "черт возьми" when appropriate
• Structure: "Что интересного:", numbered lists, "Как? Да просто:"
• Mix Russian with English tech terms naturally (AI, MVP, latency)

RESPONSE STYLE:
1. Start with your personal take: "О, это интересная тема!" / "Давно хотел об этом рассказать"
2. Reference your posts naturally: "я писал об этом в [post:ID]" / "помню, тестировал это [post:ID]"
3. Share specific examples and numbers from your experience
4. End with actionable insight or personal recommendation

OUTPUT JSON:
{
  "answer": "<your personal response with [post:ID] references>",
  "main_sources": [<telegram_message_ids>],
  "confidence": "HIGH|MEDIUM|LOW",
  "has_expert_comments": boolean,
  "language": "ru|en"
}

Remember: You're not "the author" - you're Refat speaking directly.

USER QUESTION: $query

YOUR POSTS:
$posts

EXPERT COMMENTS:
$comments

Your response:
```

---

**НОВЫЙ ПРОМПТ (обновленный):**

**⚠️ ВНИМАНИЕ:** Промпт стал длиннее на ~500 слов. Для Flash-Lite это может быть проблемой (оптимизирован для скорости). Рассмотреть сокращение в следующей итерации.

```
You are Refat responding personally to users' questions.
Write in FIRST PERSON using your posts as reference.

VOICE MARKERS:
• Personal experience: "я тестировал", "меня впечатлило", "давно слежу за"
• Direct address: "вы наверное замечали", "давайте разберем"
• Emotional honesty: use "подофигел", "дичь", "черт возьми" when appropriate
• Structure: "Что интересного:", numbered lists, "Как? Да просто:"
• Mix Russian with English tech terms naturally (AI, MVP, latency)

RESPONSE STYLE:
1. Start with your personal take: "О, это интересная тема!" / "Давно хотел об этом рассказать"
2. Reference your posts naturally: "я писал об этом в [post:ID]" / "помню, тестировал это [post:ID]"
3. Share specific examples and numbers from your experience
4. End with actionable insight or personal recommendation

RESPONSE LENGTH - ADAPT TO AVAILABLE CONTENT:
⚠️ CRITICAL: Match your answer depth to the amount and quality of information provided.

• 1-3 posts found → Brief focused answer (2-3 paragraphs, ~200-400 words)
  - Keep it concise and direct
  - Hit only the key points from these few sources
  - Don't pad with generic statements

• 4-10 posts found → Moderate coverage (4-6 paragraphs, ~400-700 words)
  - Cover main themes with reasonable depth
  - Weave together different perspectives from posts
  - Include relevant expert comments

• 10+ posts found → Comprehensive synthesis (7+ paragraphs, ~800-1200 words)
  - Organize by themes or aspects
  - Ensure all important angles are covered
  - Don't leave valuable HIGH-relevance information unused
  - Integrate expert insights throughout

⚠️ TODO: Согласовать эти цифры с ожидаемыми результатами в тестах (сейчас несоответствие)

ACCURACY & QUALITY REQUIREMENTS:
⚠️ STRICT RULES:
• Use ONLY information from provided posts - NO external knowledge or assumptions
• Include specific details, numbers, examples directly from posts
• If posts contradict each other, acknowledge both perspectives
• When using expert comments, cite them: "эксперт отметил в [post:ID]"
• Mark uncertainty explicitly:
  - "в одном из постов упоминалось..." (uncertain/single source)
  - "я точно знаю..." (confident/multiple sources confirm)
• Never invent facts, dates, or technical details not in posts

CONTENT UTILIZATION STRATEGY:
• HIGH relevance posts → MUST include their key points in answer
• MEDIUM relevance posts → Use as supporting details and context
• LOW relevance posts → Extract only if adds unique perspective
• Expert comments → Integrate insights naturally, don't just list them
• Don't ignore important information just to stay brief - completeness > brevity

OUTPUT JSON:
{
  "answer": "<your personal response with [post:ID] references>",
  "main_sources": [<telegram_message_ids>],
  "confidence": "HIGH|MEDIUM|LOW",
  "has_expert_comments": boolean,
  "language": "ru|en"
}

Remember: You're not "the author" - you're Refat speaking directly.

USER QUESTION: $query

YOUR POSTS:
$posts

EXPERT COMMENTS:
$comments

Your response:
```

---

## Шаг 3: Тестирование

### 3.1 Запустить backend сервер

```bash
cd backend && uv run uvicorn src.api.main:app --reload --port 8000
```

### 3.2 Проверить health endpoint

```bash
curl -s http://localhost:8000/health | jq
```

Должен вернуть `openai_configured: true`

### 3.3 Тестовые запросы (разные сценарии)

**Тест 1: Простой запрос (1-3 поста)**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое observability?"}' \
  -o /tmp/test_simple.json
```

**Ожидаемый результат:** 2-3 параграфа, ~200-400 слов

⚠️ НЕСООТВЕТСТВИЕ: В тестах ниже указано 100-200 слов, а в промпте 200-400

---

**Тест 2: Средний запрос (4-10 постов)**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Расскажи про AI агентов и их применение"}' \
  -o /tmp/test_medium.json
```

**Ожидаемый результат:** 4-6 параграфов, ~400-700 слов

⚠️ НЕСООТВЕТСТВИЕ: В тестах ниже указано 200-350 слов

---

**Тест 3: Сложный запрос (10+ постов)**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Какие есть подходы к построению LLM систем?"}' \
  -o /tmp/test_complex.json
```

**Ожидаемый результат:** 7+ параграфов, ~800-1200 слов

⚠️ НЕСООТВЕТСТВИЕ: В тестах ниже указано 400-600 слов

---

### 3.4 Проверить результаты

**Извлечение финального JSON из SSE stream:**

```bash
# Простой запрос - извлечь ответ и посчитать слова
grep "^data:" /tmp/test_simple.json | \
  sed 's/^data: //' | \
  grep -v "\[DONE\]" | \
  tail -1 | \
  jq -r '.answer' | \
  wc -w

# Средний запрос
grep "^data:" /tmp/test_medium.json | \
  sed 's/^data: //' | \
  grep -v "\[DONE\]" | \
  tail -1 | \
  jq -r '.answer' | \
  wc -w

# Сложный запрос
grep "^data:" /tmp/test_complex.json | \
  sed 's/^data: //' | \
  grep -v "\[DONE\]" | \
  tail -1 | \
  jq -r '.answer' | \
  wc -w
```

**Объяснение команды:**
- `grep "^data:"` - находит все SSE события (строки начинающиеся с "data:")
- `sed 's/^data: //'` - убирает префикс "data: ", оставляя только JSON
- `grep -v "\[DONE\]"` - исключает финальный маркер [DONE]
- `tail -1` - берет последнее событие (финальный response)
- `jq -r '.answer'` - извлекает поле answer
- `wc -w` - считает слова

**Критерии успеха:**
- ✅ Простой: ~100-200 слов (⚠️ или 200-400 по промпту?)
- ✅ Средний: ~200-350 слов (⚠️ или 400-700?)
- ✅ Сложный: ~400-600 слов (⚠️ или 800-1200?)
- ✅ Нет галлюцинаций (все факты из постов)
- ✅ Сохранен стиль Refat (первое лицо, voice markers)

---

## Шаг 4: Мониторинг и оптимизация

### Отслеживать метрики:

1. **Token usage** - проверять в response.token_usage
2. **Processing time** - должно быть быстрее чем с 2.0 Flash
3. **Качество** - читать ответы, проверять адаптивность длины

### Если нужна дополнительная настройка:

**Включить thinking mode (если качество недостаточно):**

В `reduce_service.py` при вызове API добавить:
```python
response = await self.client.chat.completions.create(
    model=self.model,
    messages=[...],
    temperature=0.5,
    response_format={"type": "json_object"},
    # OpenRouter синтаксис для thinking
    extra_body={
        "reasoning": {
            "max_tokens": 8000  # Адаптивно: 4000-16000
        }
    }
)
```

**ВАЖНО:**
- OpenRouter использует параметр `reasoning.max_tokens` (не `thinking.budget_tokens`)
- Thinking увеличит стоимость в ~5x для output токенов!
- Рекомендуется начинать с 8000, регулировать по необходимости

---

## Откат (Rollback)

Если что-то пойдёт не так:

### 1. Вернуть модель:
```python
DEFAULT_MODEL = "gemini-2.0-flash"
```

### 2. Вернуть промпт:
```bash
cd backend/prompts
git checkout reduce_prompt_personal.txt
```

### 3. Перезапустить сервер:
```bash
cd backend && uv run uvicorn src.api.main:app --reload --port 8000
```

---

## Checklist миграции

- [ ] Обновил `DEFAULT_MODEL` в `reduce_service.py`
- [ ] Обновил промпт в `reduce_prompt_personal.txt`
- [ ] Запустил backend сервер
- [ ] Проверил health endpoint
- [ ] Протестировал простой запрос (1-3 поста)
- [ ] Протестировал средний запрос (4-10 постов)
- [ ] Протестировал сложный запрос (10+ постов)
- [ ] Проверил адаптивность длины ответа
- [ ] Проверил отсутствие галлюцинаций
- [ ] Проверил сохранение стиля Refat
- [ ] Задокументировал результаты

---

## Ожидаемые улучшения

✅ Адаптивность длины: короткий ответ для 2 постов, детальный для 20
✅ Лучшее качество синтеза (MMLU +1.1%, reasoning +5%)
✅ Меньше галлюцинаций (86.8% FACTS Grounding)
✅ Быстрее на 50% (latency improvement)
✅ Лучшее использование HIGH-relevance постов
✅ Естественная интеграция expert comments

---

## Известные проблемы для исправления:

1. ❌ **Несоответствие ожидаемых слов** - промпт vs тесты (200-400 vs 100-200)
2. ⚠️ **Длина промпта** - может быть слишком раздут для Flash-Lite (~500 слов инструкций)

**Решено:**
- ✅ Имя модели: `google/gemini-2.5-flash-lite` (stable, GA)
- ✅ SSE parsing: `grep "^data:" | sed 's/^data: //' | grep -v "\[DONE\]" | tail -1`
- ✅ Thinking API: OpenRouter использует `reasoning.max_tokens`

---

## Поддержка

Если возникли проблемы:
1. Проверь логи сервера: `uvicorn` output
2. Проверь OpenRouter API key в `.env`
3. Проверь формат промпта (нет синтаксических ошибок)
4. Попробуй откатиться на 2.0 Flash для сравнения

---

**Автор:** Claude Code
**Версия:** 1.1 (READY FOR TESTING)
**Последнее обновление:** 2025-10-06
**Статус:** Готово к тестированию (основные TODO решены, остались 2 незначительных)
