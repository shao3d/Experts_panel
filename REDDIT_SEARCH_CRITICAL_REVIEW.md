# Критическое ревью Reddit поиска в Experts Panel

**Дата анализа:** 2026-02-12
**Аналитик:** Claude (GLM-5)
**Версия кода:** main branch (fea1c25)

---

## 📋 Общая оценка: ⭐⭐⭐ (3/5)

**Вердикт:** Система функциональна и продумана, но имеет серьёзные архитектурные риски и "дыры" в реализации.

---

## 📊 Архитектура системы

### Общая схема
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LAYERS OF COMPLEXITY                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  L1: Frontend (React)                                                       │
│      └── QueryForm.tsx → include_reddit toggle                             │
│                                                                             │
│  L2: Backend Orchestration (simplified_query_endpoint.py)                   │
│      └── process_reddit_pipeline() → Translation → Search → Synthesis      │
│                                                                             │
│  L3: Enhanced Service (reddit_enhanced_service.py)                          │
│      └── AI Scout → Multi-strategy search → Semantic Ranking               │
│                                                                             │
│  L4: HTTP Client (reddit_service.py)                                        │
│      └── Circuit Breaker → Retry → HTTP Proxy                              │
│                                                                             │
│  L5: Proxy Service (services/reddit-proxy/src/index.ts)                     │
│      └── MCP Watchdog → Aggregator → Cache                                 │
│                                                                             │
│  L6: MCP Server (reddit-mcp-buddy)                                          │
│      └── Reddit API → asyncpraw                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Ключевые файлы
| Файл | Строки | Назначение |
|------|--------|------------|
| `backend/src/api/simplified_query_endpoint.py` | ~1100 | Оркестрация Reddit pipeline |
| `backend/src/services/reddit_enhanced_service.py` | 757 | Multi-strategy search, AI Scout |
| `backend/src/services/reddit_synthesis_service.py` | 445 | Gemini-powered synthesis |
| `backend/src/services/reddit_service.py` | 398 | HTTP client, Circuit Breaker |
| `services/reddit-proxy/src/index.ts` | 803 | MCP Watchdog, Aggregator |

---

## ✅ СИЛЬНЫЕ СТОРОНЫ

### 1. Архитектура Sidecar Pattern 🏗️

```
Backend → Reddit Proxy (Fly.io) → MCP reddit-buddy → Reddit API
```

**Плюсы:**
- ✅ Изоляция сбоев — Reddit не роняет основной бэкенд
- ✅ IP защита — Reddit не блокирует основной сервер
- ✅ Независимое масштабирование
- ✅ Watchdog pattern с автоматическим respawn

**Реализация:**
```typescript
// services/reddit-proxy/src/index.ts
class WatchdogMCPManager {
  private readonly maxRestarts = 10;

  async executeTool<T>(toolName: string, args: Record<string, unknown>): Promise<T> {
    // Auto-restart if not ready
    if (!this.isReady || !this.client) {
      await this.respawn();
    }
    // 15s timeout → SIGKILL → respawn
  }
}
```

### 2. AI Scout v2 (Gemini 3 Flash) 🤖

**Инновация:** Intent-based планирование поиска вместо простого keyword matching.

```python
# backend/src/services/reddit_enhanced_service.py:209-289
async def _plan_search_strategy(self, query: str) -> Dict[str, Any]:
    prompt = f"""You are an expert Reddit OSINT Navigator.
    User Query: "{query}"

    Task: Create a precise Search Plan to find practical, technical information.
    1. Identify 3-7 relevant technical subreddits.
    2. Generate 3-5 SPECIFIC search queries to find guides, workflows, or technical details.
    3. Extract 2-3 CRITICAL keywords from the user query.

    Output JSON:
    {{
      "subreddits": ["LocalLLaMA", "ClaudeAI"],
      "queries": ["\"Claude Code\" workflow", "\"Claude Code\" setup guide"],
      "keywords": ["Skills", "CLI", "Claude"]
    }}
    """
```

**Плюсы:**
- ✅ Автоматический подбор субреддитов
- ✅ Извлечение критичных ключевых слов для semantic ranking
- ✅ Intent queries для точного поиска

### 3. Multi-Strategy Parallel Search ⚡

**6 стратегий выполняются параллельно:**

| Стратегия | Query | Ценность |
|-----------|-------|----------|
| `combined_relevance` | `(query) AND (subreddit:A OR ...)` | Лучшее совпадение |
| `combined_top_year` | Same, sort=top, time=year | Качество за год |
| `combined_new_month` | Same, sort=new, time=month | Свежесть |
| `ai_intent_N` | AI-сгенерированные запросы | Intent coverage |
| `high_signal_title` | `title:(query) AND title:(Guide OR ...)` | Гайды/туториалы |
| `comparison_heavy` | `(query) AND (vs OR solved OR ...)` | Сравнения |

**Реализация:**
```python
# backend/src/services/reddit_enhanced_service.py:331-455
sort_tasks = []

# Task 1-3: Standard sorts
sort_tasks.append(("combined_relevance", self._search_with_sort(..., sort="relevance")))
sort_tasks.append(("combined_top_year", self._search_with_sort(..., sort="top", time="year")))
sort_tasks.append(("combined_new_month", self._search_with_sort(..., sort="new", time="month")))

# Task 4: AI Intent Queries
ai_queries = search_plan.get("queries", [])
for ai_q in ai_queries[:3]:
    sort_tasks.append((f"ai_intent_{i}", self._search_with_sort(full_ai_q, ...)))

# Task 5-6: High Signal + Comparison
sort_tasks.append(("high_signal_title", ...))
sort_tasks.append(("comparison_heavy", ...))

results = await asyncio.gather(*[task for _, task in sort_tasks], return_exceptions=True)
```

**Плюсы:**
- ✅ Покрытие разных типов контента
- ✅ Deduplication across strategies
- ✅ Smart merging scores

### 4. Semantic Ranking Algorithm 📊

**Context-Aware Freshness Score:**

```python
# backend/src/services/reddit_enhanced_service.py:513-565
def calculate_freshness_score(p: RedditPost) -> float:
    # Base engagement
    base_score = p.score + (p.num_comments * 2)

    # Boost Factors
    boost = 1.0

    # 1. Technical Guide Boost (Evergreen Content)
    if p.is_technical_guide:
        boost *= 1.2

    # 2. Semantic Keyword Boost (Relevance)
    if target_keywords:
        title_lower = p.title.lower()
        matches = sum(1 for k in target_keywords if k.lower() in title_lower)
        if matches > 0:
            keyword_boost = min(1.0 + (matches * 0.5), 3.0)  # Cap at x3.0
            boost *= keyword_boost

    score = base_score * boost

    # Skip Time Decay for highly relevant content
    is_highly_relevant = p.is_technical_guide or (boost > 1.5)
    if is_highly_relevant:
        return score

    # Hacker News Gravity for News/Discussions
    age_hours = (current_time - p.created_utc) / 3600
    gravity = 1.5
    return score / pow((age_hours + 2), gravity)
```

**Плюсы:**
- ✅ Evergreen контент (гайды) не penalизируется за возраст
- ✅ Niche ответы могут конкурировать с viral постами
- ✅ Hacker News Gravity для news/discussions

### 5. Circuit Breaker Pattern 🛡️

```
CLOSED → (5 failures) → OPEN → (30s) → HALF_OPEN → (success) → CLOSED
                                    └── (fail) → OPEN
```

**Реализация:**
```python
# backend/src/services/reddit_service.py:54-137
@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: int = 30

    async def _on_failure(self, is_client_error: bool = False):
        # FIX: Client errors (4xx) don't count toward circuit breaker
        if is_client_error:
            return
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
```

**Плюсы:**
- ✅ 4xx ошибки не считаются как failures
- ✅ Автоматическое восстановление
- ✅ Защита от cascade failures

### 6. Synthesis Quality 📝

**Структура ответа (Inverted Pyramid):**

```python
# backend/src/services/reddit_synthesis_service.py:262-295
system_prompt = f"""...
RESPONSE STRUCTURE (Inverted Pyramid):
1. **Direct Answer / Solution:** Start immediately with the working solution or "best practice" for 2026.
2. **Technical Details:** Configs, flags, code snippets.
3. **Nuance & Debate:** If there is disagreement, state it clearly.
4. **Edge Cases:** Warnings from users (bugs, limitations).

CRITICAL ANALYSIS:
- PIVOT ALERT: If community advises against user's premise, start with 🚨 COMMUNITY PIVOT
- COMPARISON TABLES: For "vs" queries, output Markdown table
- CODE VERIFICATION: Use corrected version from comments
"""
```

**Дополнительные фичи:**
- ✅ OP Verification detection: `[✅ OP VERIFIED SOLUTION]`
- ✅ Deep comments tree (depth=3)
- ✅ Multi-language support (RU/EN)

---

## ❌ СЛАБЫЕ СТОРОНЫ

### 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (P0)

#### 1. `_enrich_post_content` НЕ РЕАЛИЗОВАН

**Файл:** `backend/src/services/reddit_enhanced_service.py:692-702`

```python
async def _enrich_post_content(self, post: RedditPost) -> RedditPost:
    """Fetch full content and comments for a post.

    Note: This would require the reddit-proxy to expose get_post_details
    and get_comments tools. For now, it's a placeholder for future enhancement.
    """
    # TODO: Implement when reddit-proxy supports get_post_details
    # This would make MCP calls to fetch:
    # - Full selftext (not truncated)
    # - Top comments with content
    return post  # ← ПРОСТО ВОЗВРАЩАЕТ БЕЗ ИЗМЕНЕНИЙ!
```

**Последствия:**
- 🔴 Deep comment analysis НЕ РАБОТАЕТ
- 🔴 Топ комментарии не обогащаются
- 🔴 Теряется ~50% ценной информации из discussions

**Но:** В Reddit Proxy (`services/reddit-proxy/src/index.ts:559-628`) enrichment РЕАЛИЗОВАН:
```typescript
private async enrichResults(results: RedditSearchResult[]): Promise<RedditSearchResult[]> {
    const details = await this.mcp.executeTool<any>('get_post_details', {
      post_id: post.id,
      subreddit: post.subreddit,
      comment_limit: 50,
      comment_depth: 3
    });
    // Extract selftext and comments...
}
```

**Проблема:** Backend вызывает `_enrich_post_content`, который ничего не делает, вместо использования уже обогащённых данных от Proxy.

#### 2. Credentials в открытом виде

**Файл:** `services/reddit-proxy/.env` (может попасть в git)

```env
REDDIT_CLIENT_ID=-SPb2C1BNI82qJVWSej41Q
REDDIT_CLIENT_SECRET=ry0Pvmuf9fEC-vgu4XFh5tDE82ehnQ
REDDIT_USERNAME=External-Way5292
REDDIT_PASSWORD=3dredditforce
```

**Риск:**
- 🔴 Утечка через git history
- 🔴 Reddit может забанить аккаунт
- 🔴 Security audit fail

**Решение:** Использовать Fly.io secrets:
```bash
fly secrets set REDDIT_CLIENT_SECRET=xxx REDDIT_PASSWORD=xxx
```

#### 3. Нет fallback стратегии при падении Reddit Proxy

**Файл:** `backend/src/api/simplified_query_endpoint.py:1036-1044`

```python
if not reddit_complete and not reddit_task.done():
    reddit_task.cancel()
    logger.warning("Reddit pipeline timed out, proceeding without Reddit results")
    reddit_result = None  # ← Просто null, никаких alternatives
```

**Последствие:**
- 🔴 Пользователь видит "Reddit: unavailable"
- 🔴 Нет объяснения причин
- 🔴 Нет retry с кэшированными результатами

---

### 🟠 СЕРЬЁЗНЫЕ ПРОБЛЕМЫ (P1)

#### 4. Query Translation — нет кэширования

**Файл:** `backend/src/services/translation_service.py`

```python
async def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
    # Каждый раз вызывается Gemini для перевода
    # Одинаковые запросы переводятся заново
    response = await self._call_llm(self.primary_model, messages)
```

**Последствие:**
- 🟠 Лишние затраты на API (Gemini calls)
- 🟠 Latency ~500ms на каждый перевод

**Решение:** Добавить LRU cache:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def _get_cached_translation(self, text_hash: str) -> Optional[str]:
    ...
```

#### 5. Magic Numbers без конфигурации

**Захардкожены в коде:**

| Значение | Файл | Контекст |
|----------|------|----------|
| `Semaphore(5)` | translation_service.py:197 | Concurrency limit |
| `target_posts: int = 25` | reddit_enhanced_service.py:295 | Results limit |
| `top_posts[:10]` | reddit_enhanced_service.py:575 | Deep analysis |
| `cache.max = 100` | reddit-proxy/index.ts:689 | Cache size |
| `maxRestarts = 10` | reddit-proxy/index.ts:156 | Watchdog limit |
| `MIN_SCORE = 5` | reddit-proxy/index.ts:542 | Filter threshold |

**Проблема:**
- 🟠 Невозможно тюнить под load без изменения кода
- 🟠 Нет документации почему именно эти значения

**Решение:** Вынести в конфиг:
```python
# config.py
REDDIT_TARGET_POSTS = int(os.getenv("REDDIT_TARGET_POSTS", "25"))
REDDIT_DEEP_ANALYSIS_LIMIT = int(os.getenv("REDDIT_DEEP_ANALYSIS_LIMIT", "10"))
```

#### 6. SSE Progress — нет детализации

**Сейчас:**
```python
{"phase": "reddit_search", "status": "processing", "message": "Searching Reddit..."}
```

**Хотелось бы:**
```python
{
  "phase": "reddit_search",
  "status": "processing",
  "stage": "fetching_subreddit_LocalLLaMA",
  "progress": "2/6",
  "strategies_completed": ["combined_relevance", "combined_top_year"]
}
```

**Проблема:**
- 🟠 Пользователь не видит прогресс
- 🟠 Выглядит как "зависло"
- 🟠 Нет информации о времени ожидания

#### 7. Нет rate limiting защиты

**Reddit API rate limits:**
- 60 requests/minute для OAuth
- 10 requests/minute для unauthenticated

**В коде:** НИЧЕГО не ограничивает запросы к Reddit Proxy

**Риск:**
- 🟠 Reddit может забанить за превышение лимитов
- 🟠 Cascade failures при burst traffic

**Решение:** Добавить rate limiter:
```python
from aiolimiter import AsyncLimiter

# 50 requests per minute (safe margin)
reddit_rate_limiter = AsyncLimiter(50, 60)
```

---

### 🟡 УМЕРЕННЫЕ ПРОБЛЕМЫ (P2)

#### 8. DEBUG логи в production

```python
# Множество INFO логов, которые должны быть DEBUG:
logger.info(f"🤖 Gemini Scout Plan for '{query}': {result}")
logger.info(f"REDDIT PROXY DEBUG: Got {len(sources)} sources")
logger.info(f"SYNTHESIS DEBUG: Building context from {len(sources)} sources")
logger.info(f"[DEBUG] get_post_details for {post.id} returned keys: ...")
```

**Проблема:**
- 🟡 Засоряет логи
- 🟡 Потенциально sensitive data в логах

#### 9. Frontend markdown — ограниченная поддержка

**Поддерживает:**
- Headers (## ### ####)
- **bold**, *italic*
- `code` и ```code blocks```

**НЕ поддерживает:**
- Tables (хотя synthesis их генерирует!)
- Task lists
- Footnotes

**Последствие:**
- 🟡 Comparison tables рендерятся как plain text
- 🟡 Плохой UX для vs-запросов

#### 10. Нет интеграционных тестов

**Есть:**
```bash
backend/test_reddit_api.py           # Unit test API
backend/test_reddit_comprehensive.py # Manual test script
backend/test_reddit_api2.py          # Another manual test
```

**НЕТ:**
- ❌ Frontend → Backend → Reddit Proxy end-to-end
- ❌ SSE streaming tests
- ❌ Error scenario tests
- ❌ Performance tests

---

## 🏗️ АРХИТЕКТУРНЫЕ ВОПРОСЫ

### 1. Дублирование типов данных

```python
# reddit_service.py
@dataclass
class RedditSource:
    title: str
    url: str
    score: int
    comments_count: int  # ← comments_count

# reddit_enhanced_service.py
@dataclass
class RedditPost:
    id: str
    title: str
    num_comments: int  # ← num_comments (другое имя!)
```

**Проблема:** Different naming conventions = confusion

### 2. Два уровня Circuit Breaker

```
RedditEnhancedService._circuit_breaker (instance)
    ↓
RedditService._circuit_breaker (inherited)
```

**Вопрос:** Оба активны? Как взаимодействуют?

### 3. Proxy Timeout vs Pipeline Timeout

```python
# reddit_enhanced_service.py
DEFAULT_TIMEOUT = 30.0  # HTTP timeout

# simplified_query_endpoint.py
reddit_timeout = 120.0  # Pipeline timeout
```

**Расчёт:** 4 HTTP запроса × 30s = 120s — точно на границе!

**Риск:** При медленной сети pipeline timeout может сработать раньше

---

## 📊 Итоговая таблица оценки

| Компонент | Оценка | Главная проблема |
|-----------|--------|------------------|
| **Architecture** | ⭐⭐⭐⭐ | Sidecar хорош, но single point of failure |
| **AI Scout** | ⭐⭐⭐⭐⭐ | Отличная реализация intent-based поиска |
| **Search Strategies** | ⭐⭐⭐⭐ | Хорошее покрытие, но нет адаптивности |
| **Semantic Ranking** | ⭐⭐⭐⭐⭐ | Продуманный algorithm с context-awareness |
| **Circuit Breaker** | ⭐⭐⭐⭐ | Работает, но дублирование |
| **Deep Analysis** | ⭐ | **НЕ РАБОТАЕТ** — TODO placeholder |
| **Translation** | ⭐⭐⭐ | Нет кэша, magic numbers |
| **Error Handling** | ⭐⭐⭐ | Generic, не Reddit-specific |
| **SSE Progress** | ⭐⭐ | Нет детализации, user confusion |
| **Testing** | ⭐⭐ | Нет integration tests |
| **Security** | ⭐⭐ | Credentials exposure, no rate limiting |
| **Frontend** | ⭐⭐⭐⭐ | Good UX, limited markdown |

---

## 🎯 Приоритетные рекомендации

### P0 — Критично (сделать сейчас)

| # | Задача | Файл | Оценка времени |
|---|--------|------|----------------|
| 1 | Реализовать `_enrich_post_content` | reddit_enhanced_service.py | 2h |
| 2 | Удалить credentials из .env → Fly.io secrets | .env, fly.toml | 0.5h |
| 3 | Добавить rate limiting | reddit_enhanced_service.py | 1h |

### P1 — Важно (эта неделя)

| # | Задача | Файл | Оценка времени |
|---|--------|------|----------------|
| 4 | Кэширование переводов | translation_service.py | 1h |
| 5 | Конфигурируемые лимиты → env vars | config.py | 1h |
| 6 | Детальный SSE progress | simplified_query_endpoint.py | 2h |

### P2 — Улучшения (следующий спринт)

| # | Задача | Файл | Оценка времени |
|---|--------|------|----------------|
| 7 | Integration tests | tests/ | 4h |
| 8 | Metrics & Monitoring | monitoring/ | 2h |
| 9 | Better markdown support (tables) | CommunityInsightsSection.tsx | 2h |
| 10 | Fallback strategy (cached results) | simplified_query_endpoint.py | 2h |

---

## 📈 Потенциал улучшений

После исправления P0 проблем:
- Оценка поднимется с ⭐⭐⭐ до ⭐⭐⭐⭐
- Deep analysis начнёт работать
- Security риски устранены

После исправления P0 + P1:
- Оценка поднимется до ⭐⭐⭐⭐⭐
- User experience значительно улучшится
- Система станет production-ready

---

## 🔗 Связанные файлы

- Документация: `docs/pipeline-architecture.md`
- Backend docs: `backend/CLAUDE.md`
- Frontend docs: `frontend/CLAUDE.md`
- Proxy README: `services/reddit-proxy/README.md`

---

*Анализ выполнен Claude (GLM-5) в рамках code review сессии.*
