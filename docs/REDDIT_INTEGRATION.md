# Reddit Integration

**Статус:** Активно используется  
**Реализация:** Direct Reddit API via asyncpraw  
**Дата обновления:** 2026-02-05

---

## Архитектура

```
User Query → Main Backend → OAuth → Reddit API (asyncpraw)
                ↓
         8-phase pipeline + Direct Reddit Search
                ↓
         SSE Response (relevant Reddit data)
```

**Ключевые возможности:**
- Прямой доступ к Reddit API через OAuth
- Гарантированный поиск по query
- Rate limiting (50 req/min)
- Retry logic с exponential backoff
- Нет cold start

---

## Файлы

| Файл | Назначение |
|------|------------|
| `backend/src/services/reddit_client.py` | Reddit API клиент (asyncpraw) |
| `backend/src/api/simplified_query_endpoint.py` | Endpoint с интеграцией Reddit |
| `backend/src/services/reddit_synthesis_service.py` | Gemini synthesis для Reddit контента |
| `backend/src/services/reddit_service.py` | Типы RedditSource/RedditSearchResult для synthesis |

---

## Reddit Client

### Установка

```bash
pip install asyncpraw==7.7.1
```

### Использование

```python
from services.reddit_client import search_reddit

# Поиск
result = await search_reddit(
    query="AI agent skills",
    limit=25,
    time_filter="all",    # all, day, week, month, year
    sort="relevance"      # relevance, hot, top, new
)

# Результат
result.posts              # List[RedditPost]
result.found_count        # int
result.query              # str
result.processing_time_ms # int
```

### RedditPost

```python
@dataclass
class RedditPost:
    id: str
    title: str
    selftext: str          # Полный текст поста для LLM
    score: int
    num_comments: int
    subreddit: str
    url: str
    permalink: str         # https://reddit.com/r/.../comments/...
    created_utc: float
    author: str
```

### Global Client Management

```python
from services.reddit_client import (
    get_global_reddit_client,
    close_global_reddit_client
)

# Получить клиент (создаётся при первом вызове)
client = await get_global_reddit_client()

# Закрыть при shutdown приложения
await close_global_reddit_client()
```

### Retry Logic

```python
async def search_reddit(..., max_retries: int = 2)
```

- **Не ретраит:** Auth ошибки (401/403), Validation errors
- **Ретраит:** Сетевые ошибки, timeout
- **Backoff:** 1s, 2s (exponential)
- **При ошибке:** Сбрасывает global client для переподключения

---

## Интеграция в Endpoint

### Импорты

```python
from ..services.reddit_client import search_reddit
from ..services.reddit_synthesis_service import RedditSynthesisService
from ..services.reddit_service import RedditSearchResult, RedditSource as RS
```

### Поток данных

```python
# 1. Поиск в Reddit
reddit_result = await search_reddit(query=search_query, limit=25)

# 2. Проверка результатов
if not reddit_result.posts:
    return None  # Ничего не найдено

# 3. Создание sources для synthesis (RS = RedditSource)
sources = [
    RS(
        title=post.title,
        url=post.permalink,
        score=post.score,
        comments_count=post.num_comments,
        subreddit=post.subreddit,
        content=post.selftext  # Важно: передаём контент для LLM
    )
    for post in reddit_result.posts
]

# 4. Конвертация в формат для synthesis
# Важно: используется reddit_service.RedditSearchResult (не reddit_client!)
search_result = RedditSearchResult(
    markdown=markdown,
    found_count=len(reddit_result.posts),
    sources=sources,
    query=search_query,
    processing_time_ms=reddit_result.processing_time_ms
)

# 5. Synthesis через Gemini
synthesis_service = RedditSynthesisService()
synthesis = await synthesis_service.synthesize(query, search_result)
```

### Важно: Два разных RedditSearchResult

В коде используются два разных класса с одинаковым именем:

**1. `reddit_client.RedditSearchResult`** (возвращает `search_reddit()`)
```python
@dataclass
class RedditSearchResult:
    posts: List[RedditPost]
    found_count: int
    query: str
    processing_time_ms: int
```

**2. `reddit_service.RedditSearchResult`** (передаётся в `synthesize()`)
```python
@dataclass
class RedditSearchResult:
    markdown: str
    found_count: int
    sources: List[RedditSource]
    query: str
    processing_time_ms: int
```

**Правильное использование:**
- `reddit_result = await search_reddit(...)` → используем `reddit_result.posts`
- `search_result = RedditSearchResult(...)` → передаём в `synthesize()`

---

## Rate Limiting

```python
MAX_REQUESTS_PER_MINUTE = 50  # Conservative, ниже лимита Reddit (60-100)
```

Реализация: Token bucket rate limiter с блокировкой через `asyncio.Lock()`.

---

## Credentials

Хранятся в `backend/src/services/reddit_client.py`:

```python
REDDIT_CLIENT_ID = "-SPb2C1BNI82qJVWSej41Q"
REDDIT_CLIENT_SECRET = "ry0Pvmuf9fEC-vgu4XFh5tDE82ehnQ"
REDDIT_USERNAME = "External-Way5292"
REDDIT_PASSWORD = "3dredditforce"
REDDIT_USER_AGENT = "android:com.experts.panel:v1.0 (by /u/External-Way5292)"
```

---

## Shutdown Hook

В `backend/src/main.py`:

```python
from contextlib import asynccontextmanager
from services.reddit_client import close_global_reddit_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_global_reddit_client()

app = FastAPI(lifespan=lifespan)
```

---

## Troubleshooting

### Auth ошибки
```
Reddit auth error, not retrying: ...
```
- Проверить credentials
- Проверить user_agent

### Rate limit
```
Rate limiting: waiting X.XXs
```
- Нормальное поведение
- Ждёт 1.2s между запросами (50 req/min)

### Пустые результаты
- Проверить query (не пустой после strip)
- Reddit может не находить по некоторым запросам

---

## Метрики

| Метрика | Значение |
|---------|----------|
| Релевантность поиска | >80% |
| Cold start | 0s |
| Latency (median) | 2-5s |
| Ошибки | <5% |
| Rate limit | 50 req/min |

---

## Ссылки

- Клиент: `backend/src/services/reddit_client.py`
- Endpoint: `backend/src/api/simplified_query_endpoint.py`
- Synthesis: `backend/src/services/reddit_synthesis_service.py`
