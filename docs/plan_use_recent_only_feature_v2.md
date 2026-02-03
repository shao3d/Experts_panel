# План: Фича "use_recent_only" - Фильтр по дате (3 месяца) v2

**Дата создания:** 2026-02-04  
**Статус:** Исправленный план (готов к реализации)  
**Автор:** Claude (исправленная версия)

---

## 📋 Описание фичи

Добавить в UI галочку "Только последние 3 месяца" (use_recent_only), которая ограничивает поиск постов и комментариев периодом в 3 месяца.

### Поведение:
- **OFF (default):** Используются все данные из БД (для методологии, истории, полного контекста)
- **ON:** Только посты и комментарии за последние 3 месяца (для свежих новостей, актуальных моделей)

### ⚠️ Важные нюансы:
1. **Связанные посты (Resolve):** Если включен фильтр, связанные посты старше 3 месяцев НЕ подтягиваются
2. **Ссылки [post:ID] в ответе:** LLM не будет ссылаться на старые посты, т.к. они отсутствуют в контексте
3. **Комментарии:** Загружаются только к постам, прошедшим фильтр (т.е. свежим)
4. **Drift groups:** Анализируются только для свежих постов

---

## 🏗️ Упрощённая архитектура

**Ключевое изменение:** Вместо прокидывания `use_recent_only` через все сервисы, фильтрация выполняется:

1. **На уровне endpoint** — основная фильтрация постов
2. **В resolve-сервисе** — фильтрация связанных постов (передаём `cutoff_date`)
3. **В comment-сервисе** — фильтрация drift groups (передаём `cutoff_date`)

```
┌─────────────────────────────────────────────────────────────┐
│  simplified_query_endpoint.py                               │
│  ├─ Расчёт cutoff_date = now - 3 months                     │
│  ├─ Фильтрация постов: WHERE created_at >= cutoff_date      │
│  ├─ Передача cutoff_date в resolve (если use_recent_only)   │
│  └─ Передача cutoff_date в comment groups (если нужно)      │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ↓                               ↓
┌──────────────────────────┐      ┌──────────────────────────┐
│  SimpleResolveService    │      │  CommentGroupMapService  │
│  ├─ _get_linked_posts    │      │  ├─ _load_drift_groups   │
│  └─ _fetch_posts_by_ids  │      │  └─ cutoff_date filter   │
└──────────────────────────┘      └──────────────────────────┘
```

---

## 📝 Файлы для изменения

### 1. `backend/src/api/models.py`

Добавить поле в `QueryRequest`:

```python
use_recent_only: Optional[bool] = Field(
    default=False,
    description="Use only recent data (last 3 months) for fresh news and current models. "
                "When false, uses all available data for comprehensive answers including "
                "methodology and historical context."
)
```

---

### 2. `backend/src/api/simplified_query_endpoint.py`

**Основная фильтрация постов** (lines ~108-115):

```python
# Расчёт cutoff_date
from datetime import datetime, timedelta

def get_cutoff_date():
    """Get cutoff date for 'recent only' filter (3 months ago, UTC)."""
    now = datetime.utcnow()
    # Subtract 3 months (accounting for different month lengths)
    month = now.month - 3
    year = now.year
    if month <= 0:
        month += 12
        year -= 1
    # Handle day overflow (e.g., March 31 - 3 months = Dec 31, not Dec 31->invalid)
    try:
        return now.replace(year=year, month=month)
    except ValueError:
        # For days that don't exist in target month (e.g., March 31 -> Feb 30)
        # Use last day of target month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return now.replace(year=year, month=month, day=last_day)

# В process_expert_pipeline():
cutoff_date = None
if request.use_recent_only:
    cutoff_date = get_cutoff_date()
    logger.info(f"[{expert_id}] use_recent_only enabled, cutoff_date: {cutoff_date.isoformat()}")

# Фильтрация постов
query = db.query(Post).filter(Post.expert_id == expert_id)

if cutoff_date:
    query = query.filter(Post.created_at >= cutoff_date)

if request.max_posts is not None:
    query = query.limit(request.max_posts)

posts = query.order_by(Post.created_at.desc()).all()

# Передача cutoff_date в resolve (только если use_recent_only)
if high_posts:
    resolve_service = SimpleResolveService()
    high_resolve_results = await resolve_service.process(
        relevant_posts=high_posts,
        query=request.query,
        expert_id=expert_id,
        cutoff_date=cutoff_date,  # <-- ПЕРЕДАЁМ cutoff_date
        progress_callback=resolve_progress
    )

# Передача cutoff_date в comment groups
cg_service = CommentGroupMapService(model=config.MODEL_COMMENT_GROUPS)
comment_group_results = await cg_service.process(
    query=request.query,
    db=db,
    expert_id=expert_id,
    exclude_post_ids=main_sources,
    main_source_ids=main_sources,
    cutoff_date=cutoff_date,  # <-- ПЕРЕДАЁМ cutoff_date
    progress_callback=cg_progress
)
```

---

### 3. `backend/src/services/simple_resolve_service.py`

**Изменить сигнатуру `process()`:**

```python
async def process(
    self,
    relevant_posts: List[Dict[str, Any]],
    query: str,
    expert_id: str,
    cutoff_date: Optional[datetime] = None,  # <-- НОВЫЙ ПАРАМЕТР
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
```

**Изменить `_get_linked_posts()`:**

```python
def _get_linked_posts(
    self,
    db: Session,
    initial_post_ids: Set[int],
    expert_id: str,
    cutoff_date: Optional[datetime] = None  # <-- НОВЫЙ ПАРАМЕТР
) -> Set[int]:
    # ... existing code ...
    
    # Convert database IDs back to telegram_message_ids с фильтром по дате
    if linked_db_ids:
        linked_posts_query = db.query(Post).filter(
            Post.post_id.in_(linked_db_ids),
            Post.expert_id == expert_id
        )
        
        # Фильтр по дате если задан
        if cutoff_date:
            linked_posts_query = linked_posts_query.filter(
                Post.created_at >= cutoff_date
            )
        
        linked_posts = linked_posts_query.all()
        
        for post in linked_posts:
            linked_telegram_ids.add(post.telegram_message_id)
    
    logger.info(
        f"[{expert_id}] Expanded {len(initial_post_ids)} posts to {len(linked_telegram_ids)} "
        f"(+{len(linked_telegram_ids) - len(initial_post_ids)} linked posts)"
        f"{' (filtered by date)' if cutoff_date else ''}"
    )
    
    return linked_telegram_ids
```

**Изменить `_fetch_posts_by_telegram_ids()`:**

```python
def _fetch_posts_by_telegram_ids(
    self,
    db: Session,
    telegram_message_ids: List[int],
    expert_id: str,
    cutoff_date: Optional[datetime] = None  # <-- НОВЫЙ ПАРАМЕТР
) -> Dict[int, Post]:
    if not telegram_message_ids:
        return {}
    
    query = db.query(Post).filter(
        Post.telegram_message_id.in_(telegram_message_ids),
        Post.expert_id == expert_id
    )
    
    # Фильтр по дате если задан
    if cutoff_date:
        query = query.filter(Post.created_at >= cutoff_date)
    
    posts = query.all()
    
    return {post.telegram_message_id: post for post in posts}
```

**Обновить вызовы в `process()`:**

```python
# Get all linked posts at depth 1
all_post_ids = self._get_linked_posts(
    db,
    set(relevant_ids),
    expert_id,
    cutoff_date=cutoff_date  # <-- Передаём
)

# Fetch all posts (original + linked)
posts_map = self._fetch_posts_by_telegram_ids(
    db, list(all_post_ids), expert_id,
    cutoff_date=cutoff_date  # <-- Передаём
)
```

---

### 4. `backend/src/services/comment_group_map_service.py`

**Изменить сигнатуру `process()`:**

```python
async def process(
    self,
    query: str,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None,
    main_source_ids: Optional[List[int]] = None,
    cutoff_date: Optional[datetime] = None,  # <-- НОВЫЙ ПАРАМЕТР
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
```

**Изменить `_load_drift_groups()`:**

```python
def _load_drift_groups(
    self,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None,
    cutoff_date: Optional[datetime] = None  # <-- НОВЫЙ ПАРАМЕТР
) -> List[Dict[str, Any]]:
    
    # Query drift groups with anchor posts
    query = db.query(
        comment_group_drift.c.post_id,
        comment_group_drift.c.drift_topics,
        Post.telegram_message_id,
        Post.message_text,
        Post.created_at,
        Post.author_name
    ).join(
        Post, comment_group_drift.c.post_id == Post.post_id
    ).filter(
        comment_group_drift.c.has_drift == True,
        comment_group_drift.c.expert_id == expert_id
    )
    
    # Фильтр по дате если задан
    if cutoff_date:
        query = query.filter(Post.created_at >= cutoff_date)
    
    if exclude_post_ids:
        validated_ids = [pid for pid in exclude_post_ids if isinstance(pid, int) and pid > 0]
        if validated_ids:
            query = query.filter(Post.telegram_message_id.notin_(validated_ids))
    
    results = query.all()
    # ... rest of method
```

**Обновить вызов в `process()`:**

```python
# Load drift groups from database (excluding main_sources as before)
all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids, cutoff_date=cutoff_date)
```

---

### 5. `frontend/src/types/api.ts`

Добавить поле в интерфейс `QueryRequest`:

```typescript
export interface QueryRequest {
  query: string;
  max_posts?: number;
  include_comments?: boolean;
  include_comment_groups?: boolean;
  stream_progress?: boolean;
  expert_filter?: string[];
  
  // НОВОЕ ПОЛЕ:
  use_recent_only?: boolean;
}
```

---

### 6. `frontend/src/components/QueryForm.tsx`

Добавить чекбокс и state:

```typescript
// State
const [useRecentOnly, setUseRecentOnly] = useState(false);

// При отправке
onSubmit(trimmed, { use_recent_only: useRecentOnly });

// JSX
<label className="recent-only-checkbox">
  <input
    type="checkbox"
    checked={useRecentOnly}
    onChange={(e) => setUseRecentOnly(e.target.checked)}
    disabled={disabled}
  />
  <span>🕒 Только последние 3 месяца</span>
  <small>Свежие новости и актуальные модели</small>
</label>
```

---

## 🔧 Технические детали

### Расчёт "3 месяцев назад":

```python
from datetime import datetime
import calendar

def get_cutoff_date():
    """Get cutoff date for 'recent only' filter (3 months ago, UTC).
    
    Handles month boundary correctly:
    - March 31 - 3 months = Dec 31
    - May 31 - 3 months = Feb 28/29
    """
    now = datetime.utcnow()
    month = now.month - 3
    year = now.year
    
    if month <= 0:
        month += 12
        year -= 1
    
    # Handle day overflow (e.g., March 31 -> Dec 31, not invalid)
    try:
        return now.replace(year=year, month=month)
    except ValueError:
        # Day doesn't exist in target month (e.g., May 31 -> Feb 30)
        last_day = calendar.monthrange(year, month)[1]
        return now.replace(year=year, month=month, day=last_day)
```

### SQL для проверки:

```sql
-- Проверить распределение постов по датам
SELECT 
    CASE 
        WHEN created_at >= datetime('now', '-3 months') THEN 'Свежие (3 мес)'
        ELSE 'Старые'
    END as category,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percent
FROM posts
GROUP BY category;

-- Проверить для конкретного эксперта
SELECT 
    CASE 
        WHEN created_at >= datetime('now', '-3 months') THEN 'recent'
        ELSE 'old'
    END as category,
    COUNT(*) as count
FROM posts 
WHERE expert_id = 'akimov'
GROUP BY category;
```

---

## ✅ Чеклист тестирования

- [ ] Чекбокс отображается в UI
- [ ] Состояние передаётся в API запросе
- [ ] Backend корректно фильтрует посты (проверить логи)
- [ ] Связанные посты старше 3 мес не подтягиваются
- [ ] Drift groups для старых постов не загружаются
- [ ] При OFF используются все данные
- [ ] Скорость запроса с фильтром выше (меньше данных)
- [ ] Правильный расчёт "3 месяцев" (переход через год)

---

## 🎨 UI/UX Рекомендации

### Текст чекбокса:
- **Заголовок:** "🕒 Только последние 3 месяца"
- **Подсказка:** "Для свежих новостей и актуальных моделей. Выключите для методологии и исторического контекста."

### Поведение:
- По умолчанию: **OFF** (все данные)
- Состояние сохранять в localStorage (опционально)
- При наведении показывать tooltip с пояснением

---

## 📁 Связанные файлы

- `backend/src/api/models.py` — API модели
- `backend/src/api/simplified_query_endpoint.py` — основная фильтрация
- `backend/src/services/simple_resolve_service.py` — фильтрация связанных постов
- `backend/src/services/comment_group_map_service.py` — фильтрация drift groups
- `frontend/src/types/api.ts` — TypeScript интерфейсы
- `frontend/src/components/QueryForm.tsx` — UI компонент

---

## ⚠️ Чего НЕ надо делать

1. **Не добавлять** `use_recent_only` в `MapService.process()` — посты уже отфильтрованы в endpoint'е
2. **Не фильтровать** `comments.created_at` напрямую — фильтрация через посты
3. **Не менять** ReduceService, CommentSynthesisService, LanguageValidationService — они работают с уже отфильтрованными данными

---

**Последнее обновление:** 2026-02-04  
**Статус:** Исправленный план (готов к реализации)
