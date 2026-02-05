# Reddit Integration Summary

**Дата:** 2026-02-05  
**Статус:** ✅ Активно используется

---

## Обзор

Reddit интеграция реализована через direct Reddit API с использованием библиотеки asyncpraw. OAuth аутентификация, rate limiting, retry logic.

---

## Архитектура

```
User Query → Main Backend → OAuth → Reddit API (asyncpraw)
                ↓
         8-phase pipeline + Direct Reddit Search
                ↓
         SSE Response
```

---

## Ключевые файлы

| Файл | Описание |
|------|----------|
| `backend/src/services/reddit_client.py` | Reddit API клиент |
| `backend/src/api/simplified_query_endpoint.py` | Интеграция в endpoint |
| `backend/src/services/reddit_synthesis_service.py` | Gemini synthesis |
| `backend/src/services/reddit_service.py` | Типы для synthesis |

---

## API

### Поиск

```python
from services.reddit_client import search_reddit

result = await search_reddit(
    query="AI agent skills",
    limit=25,
    time_filter="all",
    sort="relevance"
)
```

### Результат

```python
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
    selftext: str          # Текст для LLM
    score: int
    num_comments: int
    subreddit: str
    url: str
    permalink: str
    created_utc: float
    author: str
```

---

## Зависимости

```bash
pip install asyncpraw==7.7.1
```

---

## Метрики

| Метрика | Значение |
|---------|----------|
| Релевантность | >80% |
| Cold start | 0s |
| Latency | 2-5s |
| Rate limit | 50 req/min |
| Retry attempts | 2 |

---

## Документация

Полная документация: `docs/REDDIT_INTEGRATION.md`
