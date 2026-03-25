# Hybrid Vector + FTS5 Retrieval Layer (v3 — Final)

**Status:** ⏳ Planned / Pending Implementation
**Created:** 2026-03-21

Заменить FTS5-only retrieval на **гибридный** (Vector + FTS5 + RRF) для повышения recall с ~28% до ~85%.

**Принцип:** Vector = семантическое сито, FTS5 = точное совпадение, RRF = объединение, Map Phase = финальный фильтр.

## User Review Required

> [!IMPORTANT]
> **Новая зависимость**: `sqlite-vec` (pip). Пакет включает pre-compiled `.so` для Linux — **работает на `python:3.11-slim` без компилятора**.

> [!IMPORTANT]
> **`base.py` (SQLAlchemy) — критическая интеграция**: `StaticPool` (одно SQLite-соединение). `sqlite-vec` загружается через `event.listen(engine, "connect", ...)` — один раз при старте.

> [!NOTE]
> **Soft Freshness in Retrieval**: Применяется с максимальным штрафом 0.7 (линейное затухание), чтобы старые посты не вытесняли новые в top-k, при этом избегая эффекта double penalty (строгий Hacker News Gravity применяется в Map Phase).

> [!WARNING]
> **BM25 и RRF**: RRF работает с **рангами** (позициями), не со скорами. FTS5 BM25 rank и Vector distance пересчитываются с учетом Soft Freshness, сортируются, и только потом их ранги отправляются в RRF.

> [!WARNING]
> **Обратная совместимость**: `use_super_passport` переиспользуется для hybrid. `false` → стандартный режим (все посты → Map Phase).

---

## Proposed Changes

### 1. sqlite-vec Loading

#### [MODIFY] [base.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/models/base.py)

```python
# После создания engine, ПЕРЕД SessionLocal:
from sqlalchemy import event
import sqlite_vec

@event.listens_for(engine, "connect")
def _load_sqlite_extensions(dbapi_conn, connection_record):
    """Load sqlite-vec extension for vector search support."""
    dbapi_conn.enable_load_extension(True)
    sqlite_vec.load(dbapi_conn)
    dbapi_conn.enable_load_extension(False)
```

С `StaticPool` extension загружается один раз при первом подключении.

---

### 2. Embedding Service

#### [NEW] [embedding_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/embedding_service.py)

**Singleton** pattern (как `create_google_ai_studio_client()`):

```python
import asyncio
import google.generativeai as genai
from .. import config

class EmbeddingService:
    def __init__(self):
        self.model = config.MODEL_EMBEDDING         # "gemini-embedding-001"
        self.dimensions = config.EMBEDDING_DIMENSIONS  # 768 (MRL)

    async def embed_text(self, text: str, task_type="RETRIEVAL_DOCUMENT") -> list[float]:
        """Embed single text. genai.embed_content is sync → asyncio.to_thread."""
        result = await asyncio.to_thread(
            genai.embed_content,
            model=f"models/{self.model}",
            content=text,
            task_type=task_type,
            output_dimensionality=self.dimensions
        )
        return result['embedding']

    async def embed_query(self, query: str) -> list[float]:
        """Embed user query with RETRIEVAL_QUERY task_type."""
        return await self.embed_text(query, task_type="RETRIEVAL_QUERY")

    async def embed_batch(self, texts: list[str], task_type="RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """Embed batch via native genai.embed_content(content=list[str]).
        
        1 API call per batch instead of N. For embed_posts.py:
        ~26 calls (batch 50) vs ~1300 calls (sequential).
        """
        result = await asyncio.to_thread(
            genai.embed_content,
            model=f"models/{self.model}",
            content=texts,  # list[str] → native batch
            task_type=task_type,
            output_dimensionality=self.dimensions
        )
        return result['embedding']  # list[list[float]]

# Singleton
_embedding_instance = None

def get_embedding_service() -> EmbeddingService:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
```

**Ключевые решения:**
- `task_type`: `RETRIEVAL_DOCUMENT` для постов, `RETRIEVAL_QUERY` для запросов
- `output_dimensionality=768`: MRL усекает 3072→768 без потери качества
- `asyncio.to_thread`: `genai.embed_content` — sync, оборачиваем для async
- API ключ: уже настроен через `genai.configure()` в `google_ai_studio_client.py`

---

### 3. Vector Storage

#### [NEW] [021_vector_embeddings.sql](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/021_vector_embeddings.sql)

```sql
-- Метаданные: какие посты обработаны
CREATE TABLE IF NOT EXISTS post_embeddings (
    post_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);

-- Vector index с partition key для фильтрации по expert_id
-- created_at как metadata column — позволяет sqlite-vec фильтровать ДО KNN
CREATE VIRTUAL TABLE IF NOT EXISTS vec_posts USING vec0(
    post_id INTEGER PRIMARY KEY,
    embedding float[768],
    expert_id TEXT PARTITION KEY,
    created_at TEXT              -- metadata column: pre-KNN фильтр по дате
);
```

> [!IMPORTANT]
> **`expert_id TEXT PARTITION KEY`** — критически важно! Без этого KNN ищет среди ВСЕХ 1300 постов всех экспертов. С partition key `sqlite-vec` делает pre-filter по expert_id ДО KNN-вычислений.

> [!IMPORTANT]
> **`created_at TEXT` metadata column** — без этого `cutoff_date` фильтрация через JOIN работает ПОСЛЕ KNN, обрезая recall. С metadata column — `sqlite-vec` фильтрует по дате ДО KNN-вычислений. Решение из CTO Review (баг `_vector_search` с JOIN + cutoff_date).

**Размер:** ~1300 × 768 × 4 bytes ≈ **4MB**.

#### [NEW] [022_rollback_vector.sql](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/022_rollback_vector.sql)

```sql
-- Откат миграции в случае критической проблемы с sqlite-vec
DROP TABLE IF EXISTS vec_posts;
DROP TABLE IF EXISTS post_embeddings;
```

---

### 4. Hybrid Retrieval Service

#### [NEW] [hybrid_retrieval_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/hybrid_retrieval_service.py)

```
Запрос пользователя
       │
  ┌────┴────────────────┐
  │                     │
  ▼                     ▼
Vector Search        FTS5 Search
(cosine KNN)       (BM25 rank)
  │                     │
  │ top-150 post_ids    │ top-100 post_ids
  │ фильтр expert_id   │ фильтр expert_id
  │ (partition key)     │ (WHERE clause)
  │                     │
  └────┬────────────────┘
       │
  ┌────▼────┐
  │   RRF   │  score(d) = Σ 1/(k + rank_i)
  │ k = 60  │  (стандарт Elasticsearch)
  └────┬────┘
       │
       ▼ ~200 постов → Map Phase
       (с Soft Freshness — строгий decay в Map Phase)
```

```python
from sqlite_vec import serialize_float32

class HybridRetrievalService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()  # singleton
        self.RRF_K = config.HYBRID_RRF_K  # 60

    async def search_posts(
        self,
        expert_id: str,
        query: str,             # Для vector search
        match_query: str,       # Для FTS5 (от Scout)
        cutoff_date=None,
    ) -> tuple[list[Post], dict]:
        """Hybrid retrieval: Vector + FTS5 + RRF merge.
        
        Returns:
            (posts, stats_dict) — posts in RRF-ranked order, stats for logging
        """
        vector_top_k = config.HYBRID_VECTOR_TOP_K  # 150
        fts5_top_k = config.HYBRID_FTS5_TOP_K      # 100

        # ══════════════════════════════════════════════
        # GRACEFUL DEGRADATION: если vec_posts пустая
        # (первый деплой, embeddings ещё не сгенерированы)
        # → fallback на Standard MapReduce (все посты)
        # ══════════════════════════════════════════════
        if not self._has_embeddings(expert_id):
            logger.warning(f"[Hybrid] No embeddings for {expert_id}, "
                          f"falling back to Standard MapReduce (all posts)")
            return self._get_all_posts(expert_id, cutoff_date), {
                "mode": "fallback_no_embeddings",
                "vector_count": 0, "fts5_count": 0
            }

        # 1. Vector Search (async, KNN с partition key)
        query_embedding = await self.embedding_service.embed_query(query)
        vector_results = self._vector_search(
            query_embedding, expert_id, cutoff_date, vector_top_k
        )
        # Returns: [(post_id, distance), ...] sorted by distance ASC

        # 2. FTS5 Search (reuses sanitization from FTS5RetrievalService)
        fts5_results = self._fts5_search(
            match_query, expert_id, cutoff_date, fts5_top_k
        )
        # Returns: [(post_id, bm25_rank), ...] sorted by rank

        # 3. Apply Soft Freshness Decay BEFORE RRF Merge
        # АРХИТЕКТУРНОЕ РЕШЕНИЕ (CTO Review, подтверждено):
        # Soft Freshness ЗАМЕНЯЕТ Gravity из старого FTS5RetrievalService.
        # Hybrid НЕ вызывает FTS5RetrievalService — использует собственный
        # мягкий linear decay (max penalty 0.7), а не жёсткий HN Gravity.
        # Строгий decay применяется позже в Map Phase.
        # Это НЕ double penalty — это осознанная замена.
        vector_candidates = [pid for pid, _ in vector_results]
        fts5_candidates = [pid for pid, _ in fts5_results]
        all_candidates = list(set(vector_candidates + fts5_candidates))
        
        post_dates = self._get_post_dates(all_candidates)
        
        # Re-score Vector: score = (1.0 - distance) * soft_freshness
        rescored_vector = []
        for pid, dist in vector_results:
            age_days = self._calculate_age_days(post_dates.get(pid))
            # Soft decay: linearly drops to 0.7 over 1 year. Never goes below 0.7.
            soft_freshness = max(0.7, 1.0 - (age_days / 365.0))
            sim = max(0.0, 1.0 - dist)
            rescored_vector.append((pid, sim * soft_freshness))
        rescored_vector.sort(key=lambda x: x[1], reverse=True)
        
        # Re-score FTS5
        rescored_fts5 = []
        max_rank = max((r for _, r in fts5_results), default=1)
        for pid, rank in fts5_results:
            age_days = self._calculate_age_days(post_dates.get(pid))
            soft_freshness = max(0.7, 1.0 - (age_days / 365.0))
            norm_rank = 1.0 - (rank / max_rank) if max_rank > 0 else 1.0
            base_score = (norm_rank * 0.7) + 0.3
            rescored_fts5.append((pid, base_score * soft_freshness))
        rescored_fts5.sort(key=lambda x: x[1], reverse=True)

        # 4. RRF Merge (now based on freshness-adjusted ranks)
        merged = self._rrf_merge(rescored_vector, rescored_fts5)

        # 5. Load Post objects preserving RRF order
        post_ids = [pid for pid, _ in merged]
        posts = self.db.query(Post).filter(Post.post_id.in_(post_ids)).all()
        posts_by_id = {p.post_id: p for p in posts}
        ordered = [posts_by_id[pid] for pid, _ in merged if pid in posts_by_id]

        stats = {
            "mode": "hybrid",
            "vector_count": len(vector_results),
            "fts5_count": len(fts5_results),
            "merged_count": len(merged),
            "final_count": len(ordered),
            "overlap": len(set(v[0] for v in vector_results) & set(f[0] for f in fts5_results)),
            "vector_only": len(set(v[0] for v in vector_results) - set(f[0] for f in fts5_results)),
            "fts5_only": len(set(f[0] for f in fts5_results) - set(v[0] for v in vector_results))
        }
        logger.info(f"[Hybrid Retrieval] {expert_id}: " + json.dumps(stats))

        return ordered, stats

    def _rrf_merge(self, vector_results, fts5_results):
        """Reciprocal Rank Fusion. Rank-based, no score normalization needed."""
        scores = {}
        for rank, (post_id, _) in enumerate(vector_results, 1):
            scores[post_id] = scores.get(post_id, 0) + 1.0 / (self.RRF_K + rank)
        for rank, (post_id, _) in enumerate(fts5_results, 1):
            scores[post_id] = scores.get(post_id, 0) + 1.0 / (self.RRF_K + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _get_post_dates(self, post_ids: list[int]) -> dict[int, datetime]:
        """Fetch created_at for a list of posts to compute freshness."""
        if not post_ids:
            return {}
        posts = self.db.query(Post.post_id, Post.created_at).filter(Post.post_id.in_(post_ids)).all()
        return {p.post_id: p.created_at for p in posts}

    def _calculate_age_days(self, created_at) -> int:
        """Calculate age of post in days for freshness decay."""
        if not created_at:
            return 365 # Default to old if no date
        
        # Handle string dates vs datetime objects
        if isinstance(created_at, str):
            try:
                clean_str = created_at.split('.')[0]
                created_at = datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return 365

        now = datetime.utcnow()
        age_days = (now - created_at).days
        return max(0, age_days)

    def _has_embeddings(self, expert_id: str) -> bool:
        """Check if vec_posts has any embeddings for this expert."""
        sql = "SELECT 1 FROM vec_posts WHERE expert_id = :eid LIMIT 1"
        result = self.db.execute(text(sql), {"eid": expert_id}).fetchone()
        return result is not None

    def _get_all_posts(self, expert_id, cutoff_date):
        """Fallback: Standard MapReduce (all posts, as in OLD pipeline)."""
        query = self.db.query(Post).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30
        )
        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)
        return query.order_by(Post.created_at.desc()).all()

    def _vector_search(self, embedding, expert_id, cutoff_date, top_k):
        """KNN via sqlite-vec with expert_id partition key pre-filter.
        
        CTO Review Fix: cutoff_date фильтруется через metadata column
        created_at в vec0 (pre-KNN), а НЕ через JOIN с posts (post-KNN).
        Без этого KNN возвращает top-k ДО фильтрации по дате, обрезая recall.
        """
        # vec0 metadata columns: expert_id (partition key) + created_at
        # Оба применяются ДО KNN-вычислений
        sql = """
        SELECT v.post_id, v.distance
        FROM vec_posts v
        WHERE v.expert_id = :expert_id
          AND v.embedding MATCH :embedding
          AND k = :top_k
        """
        params = {
            "expert_id": expert_id,
            "embedding": serialize_float32(embedding),
            "top_k": top_k,
        }
        if cutoff_date:
            sql += " AND v.created_at >= :cutoff_date"
            params["cutoff_date"] = cutoff_date.isoformat()

        result = self.db.execute(text(sql), params)
        return [(row[0], row[1]) for row in result.fetchall()]

    def _fts5_search(self, match_query, expert_id, cutoff_date, top_k):
        """FTS5 search (reuses sanitize_fts5_query from fts5_retrieval_service)."""
        from .fts5_retrieval_service import sanitize_fts5_query

        safe_query = sanitize_fts5_query(match_query)
        if not safe_query:
            return []

        sql = """
        SELECT f.rowid as post_id, f.rank as bm25_rank
        FROM posts_fts f
        JOIN posts p ON p.post_id = f.rowid
        WHERE posts_fts MATCH :match_query
          AND p.expert_id = :expert_id
        """
        params = {"match_query": safe_query, "expert_id": expert_id}
        if cutoff_date:
            sql += " AND p.created_at >= :cutoff_date"
            params["cutoff_date"] = cutoff_date.isoformat()

        sql += " ORDER BY f.rank LIMIT :top_k"
        params["top_k"] = top_k

        result = self.db.execute(text(sql), params)
        return [(row[0], row[1]) for row in result.fetchall()]
```

**Решения из CTO Review (v1 + v2):**

| Проблема | Решение |
|---|---|
| vec0 без expert_id filter | `expert_id TEXT PARTITION KEY` — pre-filter в KNN |
| Fallback при пустой vec_posts | `_has_embeddings()` → Standard MapReduce (все посты) |
| EmbeddingService per-expert | `get_embedding_service()` singleton |
| Freshness decay | **Soft Decay заменяет Gravity** — осознанная замена HN Gravity из FTS5RetrievalService. Мягкий пенальти (max 0.7) до RRF, строгий decay — в Map Phase |
| max_posts внутри hybrid | **Не нужен** — `top_k` уже ограничивает, Map Phase справится |
| **cutoff_date + KNN (🔴 v2)** | `created_at TEXT` metadata column в vec0 — pre-KNN фильтр. JOIN post-KNN обрезал recall |
| **serialize_float32 (🔴 v2)** | `from sqlite_vec import serialize_float32` — без этого NameError в runtime |
| **Media-only посты (🟡 v2)** | Фильтр `LENGTH(message_text) > 30` в `embed_posts.py` — не эмбеддим мусор |
| **embed_batch (🟢 v2)** | Native batch через `genai.embed_content(content=list)` — 26 calls vs 1300 |
| **Shadow testing (🟡 v2)** | Адаптировать `fts5_post_ids` → `hybrid_post_ids` или временно отключить |

**Почему RRF (k=60):**
- Rank-based — не зависит от масштабов (cosine vs BM25)
- Стандарт индустрии (Elasticsearch, OpenSearch, Weaviate)
- Для retrieval layer recall важнее precision ранжирования

---

### 5. Offline Embedding Script

#### [NEW] [embed_posts.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/embed_posts.py)

Паттерн — как [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py):
- `.env` из `backend/`, `DATABASE_URL` → absolute path
- `LEFT JOIN post_embeddings` — только посты без embedding
- **Фильтр media-only**: `WHERE LENGTH(COALESCE(p.message_text, '')) > 30` — не эмбеддим посты-коротыши ("🙏", "Фото" и т.д.), экономим API calls и не загрязняем KNN мусорными embeddings (CTO Review Fix #3)
- Batch + `asyncio.sleep(0.5)` между batch'ами (плюс retry logic для Gemini API rate limits)
- **Native batch**: использовать `embed_batch()` (1 API call на batch вместо N) — ~26 calls vs ~1300
- Rich progress bar, `--batch-size 50`, `--dry-run`, `--force`, `--continuous`
- Записывает в ОБЕИХ таблиц: `vec_posts` (vector + `created_at` metadata) + `post_embeddings` (metadata)
- **Идемпотентность**: `INSERT OR REPLACE INTO vec_posts` для безопасного перезапуска.
- **Транзакционность**: Обязательная обертка в `try...except` с `db.commit()` / `db.rollback()` чтобы избежать orphaned vectors (Schema Evolution Risk).
- `expert_id` и `created_at` берутся из `posts` и записываются в `vec_posts`

---

### 6. Configuration & Dependencies

#### [MODIFY] [config.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/config.py)

```python
# --- Embedding Configuration ---
MODEL_EMBEDDING: str = os.getenv("MODEL_EMBEDDING", "gemini-embedding-001")
EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

# --- Hybrid Retrieval ---
HYBRID_VECTOR_TOP_K: int = int(os.getenv("HYBRID_VECTOR_TOP_K", "150"))
HYBRID_FTS5_TOP_K: int = int(os.getenv("HYBRID_FTS5_TOP_K", "100"))
HYBRID_RRF_K: int = int(os.getenv("HYBRID_RRF_K", "60"))
```

#### [MODIFY] [requirements.txt](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/requirements.txt)

```diff
+# Vector Search (SQLite extension)
+sqlite-vec>=0.1.1
```

#### [MODIFY] [.env.example](file:///Users/andreysazonov/Documents/Projects/Experts_panel/.env.example)

```ini
# Embedding model for hybrid vector search
MODEL_EMBEDDING=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

---

### 7. Query Endpoint Integration

#### [MODIFY] [simplified_query_endpoint.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/api/simplified_query_endpoint.py)

Точка интеграции — `process_expert_pipeline()`, строки ~200-246:

```diff
-from ..services.fts5_retrieval_service import FTS5RetrievalService
+from ..services.hybrid_retrieval_service import HybridRetrievalService

 # Inside process_expert_pipeline():
 if scout_query and expert_id != "video_hub":
     if circuit_breaker and circuit_breaker.should_skip_fts5():
         # circuit breaker — НЕ МЕНЯЕТСЯ
     else:
-        fts5_service = FTS5RetrievalService(db)
-        posts, used_fts5 = fts5_service.search_posts(...)
+        hybrid_service = HybridRetrievalService(db)
+        posts, retrieval_stats = await hybrid_service.search_posts(
+            expert_id=expert_id,
+            query=request.query,
+            match_query=scout_query,
+            cutoff_date=cutoff_date
+        )
+        used_fts5 = bool(posts)  # Для совместимости с fallback/CB logic

-        if not used_fts5 or not posts:
+        if not posts:
             # Fallback — НЕ МЕНЯЕТСЯ (CB record + standard retrieval)
```

**Что НЕ меняется:**
- `FTS5CircuitBreaker` — fallback логика
- `AIScoutService` — Scout генерирует FTS5 MATCH
- Map → Score → Resolve → Reduce — **весь пайплайн без изменений**

**Что ТРЕБУЕТ адаптации (CTO Review Fix #4):**
- Shadow testing: `fts5_post_ids` → `hybrid_post_ids` (семантика изменилась). `used_fts5 = bool(posts)` теперь означает "есть результаты", а не "FTS5 сработал". Варианты: переименовать параметр или временно отключить shadow testing на время перехода.

---

### 8. Fly.io Deployment

| Аспект | Статус | Детали |
|---|---|---|
| Docker | ✅ | `python:3.11-slim` + `pip install sqlite-vec` (pre-compiled) |
| RAM | ✅ | 1GB, вектора ~4MB |
| Storage | ✅ | `vec_posts` в `experts.db` на Fly volume (`/app/data`) |
| Миграция | ⚠️ | `embed_posts.py` через `fly ssh console` после деплоя |
| sqlite-vec | ✅ | `event.listen` в `base.py` — автоматически |
| Graceful Start | ✅ | Нет embeddings → fallback на Standard MapReduce |

---

## Verification Plan

> [!IMPORTANT]
> **Каждый шаг имеет свой тест.** Имплементатор должен проверять работоспособность после КАЖДОГО шага, не откладывая до конца.

### Справочные материалы

Существующая тестовая инфраструктура (адаптируем, не переписываем с нуля):
- [ab-testing-super-passport.md](file:///Users/andreysazonov/Documents/Projects/Experts_panel/docs/guides/ab-testing-super-passport.md) — гайд по A/B тестированию через API
- [deep_compare_pipelines.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/deep_compare_pipelines.py) — **ключевой скрипт**, сравнивает выходы Map Phase напрямую (OLD vs NEW). Нужно адаптировать для `--mode hybrid`
- [ab_test_super_passport.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/ab_test_super_passport.py) — A/B тест через API endpoint
- [walkthrough.md](file:///Users/andreysazonov/Documents/Projects/Experts_panel/walkthrough.md) — результаты предыдущего deep compare (FTS5-only: **recall 28%** — это baseline, hybrid должен быть значительно лучше)

---

### Step 1 → Тест: sqlite-vec загрузка

**После:** Модификации `base.py` + `pip install sqlite-vec`

```bash
# 1. Установка
pip install sqlite-vec

# 2. Тест загрузки extension
python3 -c "
import sqlite_vec
import sqlite3
db = sqlite3.connect(':memory:')
db.enable_load_extension(True)
sqlite_vec.load(db)
db.enable_load_extension(False)
print('✅ sqlite-vec loaded:', db.execute('SELECT vec_version()').fetchone()[0])
"

# 3. Тест через SQLAlchemy (убедиться что event.listen работает)
cd backend
python3 -c "
from src.models.base import engine
with engine.connect() as conn:
    result = conn.execute(__import__('sqlalchemy').text('SELECT vec_version()'))
    print('✅ sqlite-vec via SQLAlchemy:', result.fetchone()[0])
"
```

**Ожидаемый результат:** Версия sqlite-vec (например `v0.1.6`)

---

### Step 2 → Тест: Embedding Service

**После:** Создание `embedding_service.py` + добавление конфигов в `config.py`

```bash
cd backend
python3 -c "
import asyncio
from src.services.embedding_service import get_embedding_service

async def test():
    svc = get_embedding_service()
    emb = await svc.embed_query('тестовый запрос')
    print(f'✅ Embedding dimensions: {len(emb)}')
    print(f'   First 5 values: {emb[:5]}')
    assert len(emb) == 768, f'Expected 768, got {len(emb)}'
    
    # Тест batch
    batch = await svc.embed_batch(['текст 1', 'текст 2'])
    print(f'✅ Batch: {len(batch)} embeddings, each {len(batch[0])} dims')
    assert len(batch) == 2

asyncio.run(test())
"
```

**Ожидаемый результат:** `768` dimensions, batch из 2 embeddings

---

### Step 3 → Тест: Миграция + Embedding Script

**После:** Создание миграции `021_vector_embeddings.sql` + скрипта `embed_posts.py`

```bash
# 1. Миграция
sqlite3 backend/data/experts.db < backend/migrations/021_vector_embeddings.sql

# 2. Проверка таблиц
sqlite3 backend/data/experts.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('vec_posts', 'post_embeddings');"
# Ожидание: vec_posts и post_embeddings

# 3. Smoke test embedding (10 постов)
cd backend
python3 scripts/embed_posts.py --batch-size 10 --dry-run
# Ожидание: показывает сколько постов будет обработано, без API вызовов

python3 scripts/embed_posts.py --batch-size 10
# Ожидание: 10 постов эмбеддинг, записаны в vec_posts + post_embeddings

# 4. Проверка данных
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM post_embeddings;"
# Ожидание: 10

sqlite3 backend/data/experts.db "SELECT post_id, expert_id, created_at FROM vec_posts LIMIT 3;"
# Ожидание: 3 строки с post_id, expert_id и created_at (не NULL!)

# 5. Full embedding
python3 scripts/embed_posts.py --continuous --batch-size 50
# ~1300 постов, ~5-10 мин, ~$0.01
# Ожидание: все посты с LENGTH(message_text) > 30 обработаны
```

---

### Step 4 → Тест: Hybrid Retrieval Service (unit)

**После:** Создание `hybrid_retrieval_service.py`

```bash
cd backend
python3 -c "
import asyncio
from src.models.base import SessionLocal
from src.services.hybrid_retrieval_service import HybridRetrievalService

async def test():
    db = SessionLocal()
    svc = HybridRetrievalService(db)
    
    # Тест с реальным экспертом
    posts, stats = await svc.search_posts(
        expert_id='doronin',
        query='Как работать со Skills?',
        match_query='skills OR навык*'
    )
    
    print(f'✅ Mode: {stats[\"mode\"]}')
    print(f'   Vector: {stats[\"vector_count\"]}')
    print(f'   FTS5: {stats[\"fts5_count\"]}')
    print(f'   Merged: {stats[\"merged_count\"]}')
    print(f'   Overlap: {stats[\"overlap\"]}')
    print(f'   Final posts: {len(posts)}')
    
    assert stats['mode'] == 'hybrid', f'Expected hybrid, got {stats[\"mode\"]}'
    assert len(posts) > 0, 'No posts returned!'
    
    db.close()

asyncio.run(test())
"
```

**Ожидаемый результат:** `mode=hybrid`, vector_count ~150, fts5_count ~100, overlap > 0

---

### Step 5 → Тест: Endpoint Integration

**После:** Модификация `simplified_query_endpoint.py`

```bash
# 1. Запустить бэкенд
cd backend
export $(grep -v '^#' .env | xargs) && python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 2. В другом терминале — одиночный запрос через API
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Как работать со Skills?",
    "use_super_passport": true,
    "experts": ["doronin"]
  }' | python3 -m json.tool | head -50

# 3. Проверить логи
tail -f backend/data/backend.log | grep -E "(Hybrid Retrieval|AI Scout)"
# Ожидание: "[Hybrid Retrieval] doronin: {\"mode\": \"hybrid\", \"vector_count\": ...}"
```

**Ожидаемый результат:** Ответ с `main_sources`, логи показывают hybrid mode

---

### Step 6 → ФИНАЛЬНЫЙ E2E ТЕСТ: Deep Compare (OLD vs HYBRID)

> [!CAUTION]
> **Это самый важный тест.** Он сравнивает выходы Map Phase при старом пайплайне (ВСЕ посты) vs при hybrid (Vector + FTS5 → pre-filter). Адаптация [deep_compare_pipelines.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/deep_compare_pipelines.py).

**Что нужно сделать:** Скопировать `deep_compare_pipelines.py` → `deep_compare_hybrid.py` и заменить NEW pipeline:

```python
# БЫЛО в deep_compare_pipelines.py (строки 151-175):
# NEW Pipeline: FTS5 + Scout → Map
fts5_service = FTS5RetrievalService(db)
fts5_posts, used_fts5 = fts5_service.search_posts(...)
# Map на fts5_posts

# СТАЛО в deep_compare_hybrid.py:
# NEW Pipeline: Hybrid (Vector + FTS5 + RRF) → Map
from src.services.hybrid_retrieval_service import HybridRetrievalService
hybrid_service = HybridRetrievalService(db)
hybrid_posts, hybrid_stats = await hybrid_service.search_posts(
    expert_id=expert_id,
    query=query,
    match_query=scout_query
)
# Map на hybrid_posts
# + логировать hybrid_stats (vector_count, fts5_count, overlap)
```

**Запуск:**
```bash
cd backend

# Тест 1: Основной (тот же запрос что давал 28% recall у FTS5-only)
python3 scripts/deep_compare_hybrid.py \
  --query "Как работать со Skills?" \
  --experts doronin akimov

# Тест 2: Другой запрос
python3 scripts/deep_compare_hybrid.py \
  --query "Как настраивать RAG pipeline?" \
  --experts doronin akimov

# Тест 3: Эксперт с большим количеством постов
python3 scripts/deep_compare_hybrid.py \
  --query "Лучшие практики промпт-инженерии" \
  --experts refat llm_under_hood
```

**Таблица результатов (заполнить):**

| Запрос | Эксперт | OLD relevant | HYBRID relevant | Overlap | **True Recall** | Latency OLD → HYBRID |
|---|---|---|---|---|---|---|
| Skills | doronin | ? | ? | ? | **≥80%?** | ? → ? |
| Skills | akimov | ? | ? | ? | **≥80%?** | ? → ? |
| RAG | doronin | ? | ? | ? | **≥80%?** | ? → ? |

**Критерии успеха:**

| Метрика | Порог | Комментарий |
|---|---|---|
| **True Recall** | **≥ 70%** на каждом эксперте | FTS5-only давал 28%. Hybrid должен быть значительно лучше |
| **Average True Recall** | **≥ 80%** | По всем экспертам и запросам |
| Latency | Не медленнее OLD ×1.5 | Допускаем небольшой overhead от embedding query |
| No errors | 0 crashes | Graceful degradation если нет embeddings |

> [!TIP]
> **Сравнение с предыдущим результатом:** FTS5-only давал [True Recall 28%](file:///Users/andreysazonov/Documents/Projects/Experts_panel/walkthrough.md). Если Hybrid даёт ≥70% — это улучшение в **2.5x+**. Цель плана — ~85%.

---

### Порядок отката при проблемах

```bash
# Если критическая проблема с sqlite-vec:
sqlite3 backend/data/experts.db < backend/migrations/022_rollback_vector.sql

# В endpoint: вернуть FTS5RetrievalService (git revert)
# Graceful degradation: нет embeddings → fallback на старый пайплайн (все посты)
```
