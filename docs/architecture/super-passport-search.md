# Super-Passport Search Architecture (Experts Panel v2.0)

**Статус:** Draft / Proposed (Revised after Code Audit 2026-03-04)
**Цель:** Масштабирование системы для поддержки 30-50+ экспертов без OOM/CPU spikes и без лимитов Google API (429). Оптимизация скорости и стоимости Map Phase через гибридный FTS5-подход.

---

## 📊 Текущая реальность (из кода и БД)

| Метрика | Значение | Источник |
|---------|----------|----------|
| Экспертов | 17 (включая `video_hub`) | `SELECT DISTINCT expert_id FROM posts` |
| Всего постов | 5,487 | `SELECT COUNT(*) FROM posts` |
| Media-only постов (`message_text` = NULL/пусто, ≤30 символов) | 386 (7%) | Прогоняются через LLM впустую |
| Крупнейший эксперт | `doronin` — 817 постов (9 чанков) | |
| Линков в `links` table | 1,737 (81% mention, 19% reply) | |
| Глобальный Semaphore | ❌ Отсутствует | `simplified_query_endpoint.py:972–983` |
| MapService внутренний Semaphore | `Semaphore(MAP_MAX_PARALLEL=25)` per-expert | `map_service.py:385` |
| Стоимость Map Phase (все 16 экспертов) | ~$0.12/запрос (`flash-lite`) | 63 чанка × ~1,300 символов/пост |
| Пайплайн | 6+ фаз: Map → Medium Scoring → Resolve → Reduce → Validation → Comments | `simplified_query_endpoint.py:95–466` |
| Пути записи в `posts` | 4: `add_expert.py` (ORM) / `channel_syncer` (ORM) / `import_video_json.py` (**raw SQLite**) / `update_production_db.sh` (bulk replace) | |

---

## 🏗️ Проблема и Суть архитектуры

Текущий подход (чтение всех постов эксперта через `gemini-2.5-flash-lite`) работает для 17 экспертов. При масштабировании до 30-50 экспертов:

1. **I/O Concurrency взрыв:** FastAPI породит 50 корутин `process_expert_pipeline` **без глобального ограничения**. Каждая создаёт свой `MapService` с `Semaphore(25)` → до 50 × 25 = 1,250 теоретических concurrent API calls. На практике ограничено числом чанков (~160 при 50 экспертах), но все загружают посты в RAM одновременно.

2. **Стоимость токенов (реалистичная оценка):**

| Масштаб | Постов | Чанков | Стоимость/запрос | При 100 зап./день |
|---------|--------|--------|------------------|-------------------|
| 17 экспертов (сейчас) | 5,487 | 63 | $0.12 | $12/день |
| 50 экспертов | ~16,000 | ~160 | $0.39 | $39/день |
| 100 экспертов | ~32,000 | ~320 | $0.78 | $78/день |

> **Вывод:** $0.12–$0.39/запрос — нормальный operating cost. "Сжигание бюджета" начинается при 100+ экспертах или 1000+ запросов/день.

**Коррекция оригинального документа:** «100+ чанков» при 50 экспертах — неверная математика. 50 экспертов × avg 300 постов / 100 = **150 чанков суммарно**, не 100+ на эксперта. С Bulkhead(5): max **5 × ~9 = 45 concurrent чанков** в любой момент.

**Существующий бесполезный индекс:** В БД уже есть `CREATE INDEX idx_text_search ON posts (message_text)` — B-Tree индекс, который **не работает** для `LIKE '%word%'`. FTS5 заменит его правильным инвертированным индексом.

Решение базируется на двух столпах:
1. **Паттерн Bulkhead:** Глобальное ограничение параллельности → спасти сервер от OOM.
2. **Двухэтапная воронка (FTS5):** Pre-filter постов через FTS5 → снижение входа в Map Phase на 70–90%.

### Полный пайплайн (6+ фаз, не 3)

FTS5 влияет ТОЛЬКО на шаг 1. Все остальные фазы работают с результатом Map, не с исходными постами.

```
1. Загрузка постов ← FTS5 атакует ТОЛЬКО ЭТУ ТОЧКУ
2. Map Phase (LLM-чанки по 100)
3. HIGH/MEDIUM split → Medium Scoring (второй LLM)
4. Resolve (link expansion из links table, 1,737 линков)
5. Reduce (финальный синтез)
6. Language Validation
7. Comment Groups (drift analysis)
```

> **Ключевой инсайт:** FTS5 + AI Scout — это **PRE-FILTER, не замена Map Phase.** Map делает то, что FTS5 не может: семантическое понимание (контекст, импликации, фон — см. `map_prompt.txt`). Graceful Fallback — не «аварийный сценарий», а **ожидаемое поведение для ~10–20% запросов**, где ключевые слова не покрывают семантику.

---

## Фаза 0: Защита от I/O взрыва (Global Semaphore)

**Статус: ✅ ДЕЛАТЬ ПЕРВЫМ. ~30 минут.**

Текущий код — все эксперты в параллель без ограничений:
```python
# simplified_query_endpoint.py:972–983
for expert_id in expert_ids:
    task = asyncio.create_task(process_expert_pipeline(...))
```

**Изменения:**

```python
# config.py — новый параметр:
MAX_CONCURRENT_EXPERTS: int = int(os.getenv("MAX_CONCURRENT_EXPERTS", "5"))

# simplified_query_endpoint.py — обёртка перед циклом:
expert_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXPERTS)

async def run_expert_with_semaphore(eid):
    # SSE: показываем "в очереди" ДО ожидания
    await expert_progress_callback({
        "phase": "queued", "status": "waiting",
        "message": f"[{eid}] В очереди...", "expert_id": eid
    })
    async with expert_semaphore:
        return await process_expert_pipeline(eid, request, db, expert_progress_callback)

for expert_id in expert_ids:
    task = asyncio.create_task(run_expert_with_semaphore(expert_id))
```

**Затронутые файлы:** `config.py`, `simplified_query_endpoint.py`

**Edge Case:** Фронтенд должен обрабатывать `phase: "queued"` — иначе покажет "зависание". Проверить `ProgressSection.tsx`.

**Бонус (15 мин, делать сразу):** Фильтр media-only постов:
```python
# simplified_query_endpoint.py — при загрузке постов для Map:
query = db.query(Post).filter(
    Post.expert_id == expert_id,
    Post.message_text.isnot(None),
    func.length(Post.message_text) > 30  # Отсечь 386 media-only постов (NULL/пусто)
)
```

**Почему 30, а не 50:** В диапазоне 31-50 символов есть ценные короткие посты про AI/API:
- "Цены на API GPT-5: немного выше младших моделей." (48)
- "o3-mini уже скоро, до конца месяца. И сразу в API" (50)
- При пороге >30 сохраняем их все, при >50 — теряем.

---

## Фаза 1: FTS5 индекс (Pre-filter для Map Phase)

**Статус: ⚠️ ДЕЛАТЬ ПРИ 30+ ЭКСПЕРТАХ. ~3–4 часа.**

### Простой вариант: FTS5 на сыром `message_text` (без LLM-обогащения)

**Почему без Супер-Паспорта:**
- 4 write-пути в `posts` (включая raw SQLite) → LLM-обогащение нужно дублировать или пост-обрабатывать
- SQLite **triggers** решают FTS5 синхронизацию для ВСЕХ путей автоматически:

```sql
-- Миграция: создать FTS5 таблицу
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    message_text,
    content=posts,
    content_rowid=post_id,
    tokenize='unicode61'
);

-- Триггер: автосинк при INSERT (покрывает ВСЕ 4 write-пути)
CREATE TRIGGER posts_fts_insert AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, message_text)
    VALUES (new.post_id, COALESCE(new.message_text, ''));
END;

CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, message_text)
    VALUES ('delete', old.post_id, COALESCE(old.message_text, ''));
    INSERT INTO posts_fts(rowid, message_text)
    VALUES (new.post_id, COALESCE(new.message_text, ''));
END;

CREATE TRIGGER posts_fts_delete AFTER DELETE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, message_text)
    VALUES ('delete', old.post_id, COALESCE(old.message_text, ''));
END;

-- Backfill существующих данных (только посты с текстом > 30 символов):
INSERT INTO posts_fts(rowid, message_text)
SELECT post_id, COALESCE(message_text, '') FROM posts
WHERE LENGTH(COALESCE(message_text, '')) > 30;
```

### ⚠️ FTS5 Semantic Gap (Экспериментально подтверждён)

FTS5 `unicode61` tokenizer НЕ связывает кросс-языковые варианты:

```
FTS5 MATCH 'kubernetes' → НЕ найдёт "Раскатка кубера в продакшен"
FTS5 MATCH 'кубер*'     → НЕ найдёт "Как настроить kubernetes"
```

**Смягчение:** AI Scout (Фаза 2) должен генерировать **мульти-вариантные** запросы:
`MATCH '(кубер* OR kubernetes OR k8s) AND (деплой* OR deploy* OR раскатка)'`

### Video Hub: исключение

`video_hub` (53 сегмента) имеет отдельный пайплайн (`VideoHubService`) и **не использует** `MapService`. FTS5 для него бессмысленен — уже есть `if expert_id == "video_hub"` branch в `simplified_query_endpoint.py:149`.

---

## Фаза 2: AI Scout (Генерация MATCH-запроса)

**Статус: ⚠️ ДЕЛАТЬ ВМЕСТЕ С FTS5. ~2 часа.**

### Шаг 2.1: AIScoutService

AI Scout вызывается **один раз на весь запрос**, ДО расщепления на expert tasks.

**Архитектурное требование:** Scout должен стартовать параллельно с Reddit Pipeline, expert tasks ждут только Scout:

```python
# simplified_query_endpoint.py — внутри event_generator_parallel:
scout_task = asyncio.create_task(run_ai_scout(request.query))
reddit_task = asyncio.create_task(run_reddit_pipeline())    # не ждёт Scout

# SSE: уведомить о фазе поиска
yield sse_event("scout", "processing", "AI Scout: generating search query...")

scout_query = await scout_task   # ждём 500ms–2s
# Expert tasks стартуют ПОСЛЕ Scout, Reddit продолжает
```

**Промпт Scout (критически важен для русского + английского):**
```
Given user query: "{query}"
Generate an FTS5 MATCH query covering:
1. All literal keywords from the query
2. Russian slang variants (кубер→kubernetes, постгря→postgresql)
3. English translations of Russian terms
4. Prefix wildcards for morphological variations (деплой*, настрой*)

Output ONLY the MATCH string. Example:
(кубер* OR kubernetes OR k8s) AND (деплой* OR deploy* OR раскатка)
```

### Шаг 2.2: FTS5 Retrieval (внутри пайплайна эксперта)

```sql
SELECT p.post_id, p.telegram_message_id, p.message_text
FROM posts_fts f
JOIN posts p ON p.post_id = f.rowid
WHERE f.posts_fts MATCH :scout_query
  AND p.expert_id = :expert_id
  AND (p.created_at >= :cutoff_date OR :cutoff_date IS NULL)
  AND LENGTH(COALESCE(p.message_text, '')) > 30
ORDER BY
  CASE WHEN :use_recent_only THEN p.created_at END DESC,
  CASE WHEN NOT :use_recent_only THEN f.rank END,
  p.created_at DESC
LIMIT :max_fts_results;  -- Конфигурируемый, default=300
```

**Взаимодействие с `max_posts`:** Если `request.max_posts` задан (текущий код: `query.limit(request.max_posts)`), он должен иметь приоритет над `MAX_FTS_RESULTS`:
```python
effective_limit = min(request.max_posts, MAX_FTS_RESULTS) if request.max_posts else MAX_FTS_RESULTS
```

**Конфигурация:** `MAX_FTS_RESULTS = int(os.getenv("MAX_FTS_RESULTS", "300"))` + лог-warning при обрезке.

### Шаг 2.3: Текущий Map Phase

FTS5-кандидаты передаются в `MapService.process(posts=fts_posts, ...)` — контракт сохраняется полностью.

**Data flow проверен:** `posts_by_id` (строка 202) строится из тех же `posts` → MEDIUM enrichment работает. `SimpleResolveService` (строка 285) создаёт свою DB-сессию → link expansion работает независимо.

---

## 🛡️ Архитектурные защиты и Edge Cases

### Graceful Fallback + Circuit Breaker

Если FTS5 вернул 0 результатов → автоматически загрузить все посты (как сейчас).

**Но:** per-expert fallback может вызвать **latency amplification** — Scout (1s) + FTS5 (100ms) + v1.0 fallback (5–10s) = дольше, чем без FTS5.

**Circuit Breaker:** если 3+ экспертов ушли в fallback → отключить FTS5 для оставшихся экспертов в этом запросе:

```python
fallback_count = 0

async def process_expert_with_fts(expert_id, scout_query):
    nonlocal fallback_count
    if fallback_count >= 3:
        posts = load_all_posts(expert_id)  # skip FTS5
    else:
        fts_posts = fts5_search(expert_id, scout_query)
        if not fts_posts:
            fallback_count += 1
            posts = load_all_posts(expert_id)
        else:
            posts = fts_posts
    return await map_service.process(posts=posts, ...)
```

### Feature Flag (Рубильник для A/B тестирования)

FTS5 + Scout path закрыт за флагом `use_super_passport` в `QueryRequest`:

```python
# api/models.py — добавить в QueryRequest:
use_super_passport: Optional[bool] = Field(
    default=False,  # По умолчанию — OFF (старый пайплайн)
    description="Use FTS5 pre-filtering + AI Scout instead of full Map Phase"
)
```

**Логика переключения:**

```python
# simplified_query_endpoint.py — выбор стратегии:
if request.use_super_passport and scout_query and expert_id != "video_hub":
    # НОВЫЙ путь: FTS5 → 300 кандидатов → Map
    posts = await fts5_retrieval(expert_id, scout_query, cutoff_date)
    if not posts:  # Graceful Fallback
        posts = load_all_posts(expert_id, cutoff_date, min_length=30)
else:
    # СТАРЫЙ путь: все посты → Map (v1.0)
    posts = load_all_posts(expert_id, cutoff_date, min_length=30)
```

**Как тестировать:**

```bash
# Тест 1: Старый пайплайн (baseline)
curl -X POST /api/v1/query \
  -d '{"query": "как настроить k8s", "use_super_passport": false}'

# Тест 2: Новый пайплайн (FTS5 + Scout)
curl -X POST /api/v1/query \
  -d '{"query": "как настроить k8s", "use_super_passport": true}'

# Сравнить: expert_responses[].main_sources — совпадают ли посты?
```

**Метрики для сравнения:**

| Метрика | Как измерить |
|---------|--------------|
| **Recall** | % совпадения `main_sources` между v1.0 и FTS5 |
| **Latency** | Время Map Phase (должно быть -70%) |
| **Token cost** | `posts_analyzed` × avg tokens/post |
| **Scout Quality** | % запросов где FTS5 вернул >0 результатов |

**Rollout стратегия:**
1. `default=False` → все пользователи на старом пайплайне
2. Ручное тестирование с `use_super_passport: true`
3. Shadow Testing (см. Этап 3) → измерить Recall ≥80%
4. `default=True` → переключить всех на новый пайплайн

### Полный список Edge Cases

| # | Edge Case | Серьёзность | Решение |
|---|-----------|-------------|---------|
| 1 | FTS5 Semantic Gap (кубер≠kubernetes) | 🔴 | AI Scout генерирует мульти-вариантные MATCH-запросы |
| 2 | Video Hub несовместим | 🟡 | Явное исключение `if expert_id == "video_hub"` |
| 3 | Latency amplification при Fallback | 🟡 | Circuit Breaker (3 fallback → skip FTS5) |
| 4 | 386 media-only постов | 🟡 | Фильтр `LENGTH > 30` (делать в Фазе 0) |
| 5 | `use_recent_only` + FTS5 сортировка | 🟡 | Условный `ORDER BY` в SQL |
| 6 | LIMIT 300 обрезка | 🟡 | Конфигурируемый `MAX_FTS_RESULTS` + лог |
| 7 | Scout delay (500ms–2s) | 🟡 | Scout параллельно с Reddit, SSE-событие "scout" |
| 8 | Деплой-цикл (gzip+sftp) | 🟢 | FTS5 — часть SQLite файла, переживёт sftp |

---

## 🚀 План внедрения (пересмотренный)

### Этап 0: «Bulkhead» — СЕЙЧАС (30 мин + 15 мин бонус)
* `asyncio.Semaphore(MAX_CONCURRENT_EXPERTS=5)` в `simplified_query_endpoint.py`
* SSE-событие `phase: "queued"` для фронтенда
* Фильтр media-only постов (`LENGTH > 30`) — экономит 7% токенов Map Phase
* **Файлы:** `config.py`, `simplified_query_endpoint.py`

### Этап 1: «FTS5 Index» — при 30+ экспертах (3–4 часа)
* Миграция: `posts_fts` + триггеры (sync для ВСЕХ write-путей)
* Backfill существующих ~5,500 постов
* **Файлы:** новый файл в `backend/migrations/`

### Этап 2: «AI Scout + Integration» — вместе с FTS5 (3 часа)
* Реализация `AIScoutService` с двуязычным промптом
* Интеграция FTS5 в `simplified_query_endpoint.py` (за флагом `use_super_passport`)
* Circuit Breaker для fallback
* SSE-событие `phase: "scout"`
* **Файлы:** новый `backend/src/services/ai_scout_service.py`, `simplified_query_endpoint.py`, `api/models.py`

### Этап 3: Shadow Testing (1–2 часа)
* Локальное сравнение FTS5 vs v1.0 : одинаковые запросы, сравнение recall
* **Recall Metric:** % запросов где FTS5-результат совпадает с v1.0 на ≥80%
* **Scout Quality Metric:** % запросов где Scout корректно сгенерировал мульти-язычные варианты (кубер↔kubernetes, постгря↔postgresql). Если <80% — нужен fallback на LLM-паспорт для проблемных доменов

### Этап 4: Production Switch & Scale
* Включение `use_super_passport: true` по умолчанию
* Добавление новых экспертов

---

## ❌ Решение НЕ реализовывать (обоснование)

### Супер-Паспорт (LLM-обогащение при импорте)

**Причины отказа:**
1. **4 write-пути:** `add_expert.py` (ORM), `channel_syncer` (ORM), `import_video_json.py` (raw SQLite), `update_production_db.sh` (bulk replace). LLM-обогащение нужно в каждом ИЛИ отдельный backfill после каждого.
2. **Стоимость vs выгода:** $0.12/запрос на Map Phase не оправдывает Ingestion LLM.
3. **FTS5 + умный Scout покрывает ~80%** пользы паспорта за 0% Ingestion-стоимости.
4. **Простые SQLite triggers** решают синхронизацию FTS5 для ВСЕХ write-путей — не нужны хуки в import-скриптах.

**Когда пересмотреть:** при 100+ экспертах, если FTS5 recall <70% по тестам Shadow Testing.