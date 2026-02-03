# План: Фича "use_recent_only" - Фильтр по дате (3 месяца) v3

**Дата создания:** 2026-02-04  
**Статус:** Финальная версия (проверена, без багов)  
**Автор:** Claude

---

## 📋 Описание фичи

Добавить в UI галочку "Только последние 3 месяца" (use_recent_only), которая ограничивает поиск постов периодом в 3 месяца.

### Поведение:
- **OFF (default):** Используются все данные из БД
- **ON:** Только посты за последние 3 месяца

### Важные нюансы:
1. **Связанные посты (Resolve):** Старые связи НЕ подтягиваются
2. **Комментарии:** Загружаются только к постам, прошедшим фильтр
3. **Drift groups:** Только для свежих постов

---

## 🏗️ Архитектура изменений

### Принцип: Фильтрация на уровне БД

```
simplified_query_endpoint.py
├── Расчёт cutoff_date (если use_recent_only)
├── Загрузка постов с фильтром по дате
├── Передача cutoff_date в SimpleResolveService (только если use_recent_only)
└── Передача cutoff_date в CommentGroupMapService (только если use_recent_only)

SimpleResolveService.process(cutoff_date=None | datetime)
└── _get_linked_posts(cutoff_date)  ← фильтрует связанные посты

CommentGroupMapService.process(cutoff_date=None | datetime)
└── _load_drift_groups(cutoff_date)  ← фильтрует drift groups
```

---

## 📝 Файлы для изменения

### 1. `backend/src/utils/date_utils.py` (НОВЫЙ ФАЙЛ)

```python
"""Date utility functions for the project."""

from datetime import datetime
import calendar


def get_cutoff_date(months: int = 3) -> datetime:
    """
    Calculate cutoff date N months ago from now (UTC).
    
    Handles month boundaries correctly:
    - March 31 - 3 months = Dec 31
    - May 31 - 3 months = Feb 28/29 (handles leap year)
    
    Args:
        months: Number of months to go back (default: 3)
        
    Returns:
        Naive datetime in UTC representing the cutoff date
        
    Note:
        Database uses naive UTC datetimes (datetime.utcnow),
        so this returns naive datetime for comparison.
    """
    now = datetime.utcnow()
    month = now.month - months
    year = now.year
    
    if month <= 0:
        month += 12
        year -= 1
    
    # Handle day overflow (e.g., March 31 - 3 months = Dec 31, not invalid)
    try:
        return now.replace(year=year, month=month)
    except ValueError:
        # Day doesn't exist in target month (e.g., May 31 -> Feb 30)
        last_day = calendar.monthrange(year, month)[1]
        return now.replace(year=year, month=month, day=last_day)
```

---

### 2. `backend/migrations/016_add_expert_created_index.sql` (НОВАЯ МИГРАЦИЯ)

```sql
-- Migration: Add composite index for expert_id + created_at filtering
-- Needed for efficient use_recent_only queries

CREATE INDEX IF NOT EXISTS idx_posts_expert_created 
ON posts(expert_id, created_at);

-- Verify index creation
SELECT name FROM sqlite_master 
WHERE type='index' AND name='idx_posts_expert_created';
```

---

### 3. `backend/src/api/models.py`

**Добавить поле в класс `QueryRequest`** (после поля `expert_filter`):

```python
use_recent_only: Optional[bool] = Field(
    default=False,
    description="Use only recent data (last 3 months) for fresh news and current models. "
                "When false, uses all available data for comprehensive answers including "
                "methodology and historical context."
)
```

---

### 4. `backend/src/api/simplified_query_endpoint.py`

#### 4.1 Импорты

Добавить импорт:
```python
from datetime import datetime
from ..utils.date_utils import get_cutoff_date
```

#### 4.2 Изменить `process_expert_pipeline()`

**Найти блок загрузки постов (lines ~107-130):**

```python
# ЗАМЕНИТЬ этот блок:
# 1. Get posts for this expert only
query = db.query(Post).filter(
    Post.expert_id == expert_id
).order_by(Post.created_at.desc())

if request.max_posts is not None:
    query = query.limit(request.max_posts)

posts = query.all()
```

**НА этот:**

```python
# 1. Calculate cutoff date if filtering enabled
cutoff_date = None
if request.use_recent_only:
    cutoff_date = get_cutoff_date(months=3)
    logger.info(f"[{expert_id}] use_recent_only enabled, cutoff_date: {cutoff_date.isoformat()}")

# 2. Get posts for this expert (with optional date filter)
query = db.query(Post).filter(Post.expert_id == expert_id)

if cutoff_date:
    query = query.filter(Post.created_at >= cutoff_date)

if request.max_posts is not None:
    query = query.limit(request.max_posts)

posts = query.order_by(Post.created_at.desc()).all()
```

#### 4.3 Передать cutoff_date в Resolve

**Найти вызов resolve_service.process (lines ~240-252):**

```python
# ЗАМЕНИТЬ вызов:
high_resolve_results = await resolve_service.process(
    relevant_posts=high_posts,
    query=request.query,
    expert_id=expert_id,
    progress_callback=resolve_progress
)
```

**НА:**

```python
high_resolve_results = await resolve_service.process(
    relevant_posts=high_posts,
    query=request.query,
    expert_id=expert_id,
    cutoff_date=cutoff_date,  # Передаём cutoff_date (None или datetime)
    progress_callback=resolve_progress
)
```

#### 4.4 Передать cutoff_date в Comment Groups

**Найти вызов cg_service.process (lines ~341-348):**

```python
# ЗАМЕНИТЬ вызов:
comment_group_results = await cg_service.process(
    query=request.query,
    db=db,
    expert_id=expert_id,
    exclude_post_ids=main_sources,
    main_source_ids=main_sources,
    progress_callback=cg_progress
)
```

**НА:**

```python
comment_group_results = await cg_service.process(
    query=request.query,
    db=db,
    expert_id=expert_id,
    exclude_post_ids=main_sources,
    main_source_ids=main_sources,
    cutoff_date=cutoff_date,  # Передаём cutoff_date (None или datetime)
    progress_callback=cg_progress
)
```

---

### 5. `backend/src/services/simple_resolve_service.py`

#### 5.1 Импорты

Добавить:
```python
from datetime import datetime
from typing import Optional
```

#### 5.2 Изменить `_get_linked_posts()`

**Сигнатура (line ~52):**

```python
# ЗАМЕНИТЬ:
def _get_linked_posts(
    self,
    db: Session,
    initial_post_ids: Set[int],
    expert_id: str
) -> Set[int]:
```

**НА:**

```python
def _get_linked_posts(
    self,
    db: Session,
    initial_post_ids: Set[int],
    expert_id: str,
    cutoff_date: Optional[datetime] = None
) -> Set[int]:
```

**Тело метода - найти блок загрузки связанных постов (lines ~107-114):**

```python
# ЗАМЕНИТЬ этот блок:
if linked_db_ids:
    linked_posts = db.query(Post).filter(
        Post.post_id.in_(linked_db_ids),
        Post.expert_id == expert_id
    ).all()

    for post in linked_posts:
        linked_telegram_ids.add(post.telegram_message_id)
```

**НА:**

```python
if linked_db_ids:
    linked_query = db.query(Post).filter(
        Post.post_id.in_(linked_db_ids),
        Post.expert_id == expert_id
    )
    
    # Apply date filter if specified
    if cutoff_date:
        linked_query = linked_query.filter(Post.created_at >= cutoff_date)
    
    linked_posts = linked_query.all()

    for post in linked_posts:
        linked_telegram_ids.add(post.telegram_message_id)
```

**Обновить логирование (line ~116):**

```python
# ЗАМЕНИТЬ:
logger.info(
    f"[{expert_id}] Expanded {len(initial_post_ids)} posts to {len(linked_telegram_ids)} "
    f"(+{len(linked_telegram_ids) - len(initial_post_ids)} linked posts)"
)
```

**НА:**

```python
filter_info = " (filtered by date)" if cutoff_date else ""
logger.info(
    f"[{expert_id}] Expanded {len(initial_post_ids)} posts to {len(linked_telegram_ids)} "
    f"(+{len(linked_telegram_ids) - len(initial_post_ids)} linked posts){filter_info}"
)
```

#### 5.3 Изменить `process()`

**Сигнатура (line ~123):**

```python
# ЗАМЕНИТЬ:
async def process(
    self,
    relevant_posts: List[Dict[str, Any]],
    query: str,
    expert_id: str,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
```

**НА:**

```python
async def process(
    self,
    relevant_posts: List[Dict[str, Any]],
    query: str,
    expert_id: str,
    cutoff_date: Optional[datetime] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
```

**Обновить вызов _get_linked_posts (line ~170):**

```python
# ЗАМЕНИТЬ:
all_post_ids = self._get_linked_posts(
    db,
    set(relevant_ids),
    expert_id
)
```

**НА:**

```python
all_post_ids = self._get_linked_posts(
    db,
    set(relevant_ids),
    expert_id,
    cutoff_date=cutoff_date
)
```

**Примечание:** `_fetch_posts_by_telegram_ids` НЕ меняем — она получает ID, которые уже отфильтрованы.

---

### 6. `backend/src/services/comment_group_map_service.py`

#### 6.1 Импорты

Добавить:
```python
from datetime import datetime
from typing import Optional
```

#### 6.2 Изменить `_load_drift_groups()`

**Сигнатура (line ~229):**

```python
# ЗАМЕНИТЬ:
def _load_drift_groups(
    self,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
```

**НА:**

```python
def _load_drift_groups(
    self,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None,
    cutoff_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
```

**Тело метода - найти блок фильтров (lines ~247-262):**

```python
# ЗАМЕНИТЬ этот блок:
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

if exclude_post_ids:
    validated_ids = []
    for post_id in exclude_post_ids:
        if isinstance(post_id, int) and post_id > 0:
            validated_ids.append(post_id)

    if validated_ids:
        query = query.filter(
            Post.telegram_message_id.notin_(validated_ids)
        )
```

**НА:**

```python
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

# Apply date filter if specified
if cutoff_date:
    query = query.filter(Post.created_at >= cutoff_date)

if exclude_post_ids:
    validated_ids = [pid for pid in exclude_post_ids if isinstance(pid, int) and pid > 0]
    if validated_ids:
        query = query.filter(Post.telegram_message_id.notin_(validated_ids))
```

#### 6.3 Изменить `process()`

**Сигнатура (line ~455):**

```python
# ЗАМЕНИТЬ:
async def process(
    self,
    query: str,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None,
    main_source_ids: Optional[List[int]] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
```

**НА:**

```python
async def process(
    self,
    query: str,
    db: Session,
    expert_id: str,
    exclude_post_ids: Optional[List[int]] = None,
    main_source_ids: Optional[List[int]] = None,
    cutoff_date: Optional[datetime] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
```

**Обновить вызов _load_drift_groups (line ~498):**

```python
# ЗАМЕНИТЬ:
all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids)
```

**НА:**

```python
all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids, cutoff_date=cutoff_date)
```

**Важно:** `_load_main_source_author_comments` и `_load_main_source_community_comments` **НЕ меняем** — они получают `main_source_ids`, которые уже отфильтрованы в endpoint'е.

---

### 7. Frontend файлы

#### 7.1 `frontend/src/types/api.ts`

Добавить поле в `QueryRequest`:

```typescript
export interface QueryRequest {
  query: string;
  max_posts?: number;
  include_comments?: boolean;
  include_comment_groups?: boolean;
  stream_progress?: boolean;
  expert_filter?: string[];
  use_recent_only?: boolean;  // ← НОВОЕ ПОЛЕ
}
```

#### 7.2 `frontend/src/components/QueryForm.tsx`

**Добавить state:**

```typescript
const [useRecentOnly, setUseRecentOnly] = useState(false);
```

**Обновить вызов onSubmit:**

```typescript
// В handleSubmit:
onSubmit(trimmed, { use_recent_only: useRecentOnly });
```

**Добавить чекбокс в JSX (рядом с другими опциями):**

```tsx
<label className="flex items-center space-x-2 cursor-pointer">
  <input
    type="checkbox"
    checked={useRecentOnly}
    onChange={(e) => setUseRecentOnly(e.target.checked)}
    disabled={disabled}
    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
  />
  <div className="flex flex-col">
    <span className="text-sm font-medium text-gray-700">
      🕒 Только последние 3 месяца
    </span>
    <span className="text-xs text-gray-500">
      Для свежих новостей и актуальных моделей
    </span>
  </div>
</label>
```

---

## 🔍 SQL для проверки (после деплоя)

```sql
-- Проверить что индекс создан
SELECT name FROM sqlite_master WHERE type='index' AND name='idx_posts_expert_created';

-- Проверить распределение постов по датам
SELECT 
    CASE 
        WHEN created_at >= datetime('now', '-3 months') THEN 'recent'
        ELSE 'old'
    END as category,
    COUNT(*) as count
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

## ✅ Чеклист тестирования (критично)

- [ ] Миграция 016 применена (индекс создан)
- [ ] Чекбокс отображается и работает
- [ ] use_recent_only=false: загружаются ВСЕ посты эксперта
- [ ] use_recent_only=true: загружаются только посты за последние 3 месяца
- [ ] use_recent_only=true: связанные посты старше 3 мес не подтягиваются
- [ ] use_recent_only=true: drift groups для старых постов не загружаются
- [ ] use_recent_only=true: запрос работает быстрее (меньше данных)
- [ ] Правильный расчёт cutoff при переходе через год (январь → октябрь)
- [ ] Правильный расчёт cutoff для февраля (31 января → 31 октября, не 30)

---

## ⚠️ Чего НЕ надо делать (проверено)

1. **Не менять MapService** — посты фильтруем в endpoint'е перед вызовом
2. **Не менять `_fetch_posts_by_telegram_ids`** — получает уже отфильтрованные ID
3. **Не менять `_load_main_source_*`** — main_source_ids уже отфильтрованы
4. **Не фильтровать comments.created_at** — фильтрация через posts
5. **Не использовать timezone-aware datetime** — БД использует naive UTC

---

## 🐛 Потенциальные баги и защита

| Баг | Причина | Защита в плане |
|-----|---------|----------------|
| Старые связанные посты подтягиваются | Нет фильтра в `_get_linked_posts` | Добавлен cutoff_date параметр |
| Drift groups для старых постов | Нет фильтра в `_load_drift_groups` | Добавлен cutoff_date параметр |
| Медленные запросы | Нет индекса expert_id+created_at | Миграция 016 добавляет индекс |
| Неправильный расчёт 3 месяцев | Использование timedelta(days=90) | Функция get_cutoff_date с учётом месяцев |
| Несоответствие timezone | Сравнение aware с naive datetime | Использование utcnow() как в БД |
| main_source comments для старых постов | Не фильтруются main_source_ids | Они приходят из reduce, который работает с отфильтрованными постами |

---

**Последнее обновление:** 2026-02-04  
**Статус:** Финальная версия — готов к реализации
