# CTO Review v2: Hybrid Retrieval Plan — Перепроверено

**Date:** 2026-03-24 (revised)
**Метод:** Каждый пункт сверен с кодом + документация sqlite-vec

---

## Перепроверка первого ревью

| Первоначальный вердикт | Ревизия | Почему |
|---|---|---|
| 🔴 Баг: JOIN + cutoff_date | ✅ **Подтверждён** | Задокументировано в sqlite-vec: KNN выполняется ДО JOIN-условий. Metadata columns — официальное решение. |
| 🟡 Edge #1: Double Freshness | ⬇️ **Понижен до NOTE** | Hybrid **заменяет** FTS5RetrievalService, а не вызывает его. Gravity из старого кода больше не используется — Soft Freshness единственный decay. Не баг, а осознанная замена. Но стоит задокументировать. |
| 🟡 Edge #2: Sequential embed_batch | ✅ **Подтверждён** | `genai.embed_content` поддерживает `list[str]` как `content` — нативный batch. Текущий код делает 1 API call на текст. |
| 🟡 Edge #3: COUNT(*) на vec_posts | ❌ **Снят** | При 1300 строках и одном вызове на запрос — пренебрежимо. Не стоит усложнять план. |

---

## Новые находки (при глубокой перепроверке)

### 🔴 Находка #1: `serialize_float32` — не существует

В плане, строка 335:
```python
"embedding": serialize_float32(embedding),
```

Эта функция **нигде не определена** в кодовой базе и **не импортирована** в плане. `sqlite-vec` предоставляет свою сериализацию:

```python
from sqlite_vec import serialize_float32
```

Без этого импорта `_vector_search` упадёт с `NameError` в runtime.

> [!IMPORTANT]
> Нужно добавить `from sqlite_vec import serialize_float32` в импорты `hybrid_retrieval_service.py`.

---

### 🟡 Находка #2: Media-only посты в Vector Search

Текущий [FTS5RetrievalService](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#76-396) (строки 299-300) фильтрует media-only посты:
```python
# Существующий код — FTS5:
AND LENGTH(COALESCE(p.message_text, '')) > 30
```

А `_vector_search` в плане **не содержит этого фильтра**. Если `embed_posts.py` эмбеддит все посты (включая коротыши ≤30 символов), то:
1. Вектора для "🙏" или "Фото" попадут в `vec_posts`
2. KNN вернёт их как "похожие" (маленькие тексты → непредсказуемые embedding)
3. Map Phase получит мусорные посты

**Два места для фикса** (выбери одно):
- **В `embed_posts.py`**: фильтровать `WHERE LENGTH(message_text) > 30` при выборе постов для эмбеддинга (предпочтительно — не тратим деньги на garbage)
- **В `_vector_search`**: добавить `AND LENGTH(p.message_text) > 30` в SQL (но тут та же проблема JOIN — см. баг #1)

---

### 🟡 Находка #3: Shadow Testing сломается

Текущий endpoint (строка 264):
```python
fts5_post_ids = [p.post_id for p in posts]
shadow_service.compare_retrieval(
    expert_id=expert_id,
    fts5_post_ids=fts5_post_ids,  # ← имя параметра "fts5_post_ids"
    ...
    latency_fts5_ms=latency_fts5_ms,
)
```

После замены на Hybrid:
- `used_fts5 = bool(posts)` — **семантика изменилась**: раньше `False` означало "FTS5 fallback", теперь `False` = "0 posts" (fallback уже внутри Hybrid)
- Shadow testing вызывает `compare_retrieval(fts5_post_ids=...)` — логически это теперь `hybrid_post_ids`, но параметр не переименован
- Лог `"FTS5: {used_fts5}"` теперь вводит в заблуждение

**Не блокер**, но нужно обновить shadow testing section в плане, либо отключить shadow testing на время перехода (раз hybrid заменяет FTS5, shadow для сравнения hybrid vs standard имеет другой смысл).

---

## ✅ Перепроверенные "не-баги"

| Подозрение | Результат | Почему не баг |
|---|---|---|
| `genai.configure` — будет ли работать? | ✅ OK | `genai.configure(api_key=...)` вызывается на **module level** в [google_ai_studio_client.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/google_ai_studio_client.py) (строка 33). `EmbeddingService` использует тот же `genai` — конфигурация глобальная. |
| sync→async ломает endpoint? | ✅ OK | [process_expert_pipeline](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/api/simplified_query_endpoint.py#169-613) уже `async def` (строка 169). Старый `fts5_service.search_posts()` — sync. Новый `hybrid_service.search_posts()` — async. Добавление `await` корректно. |
| [FTS5RetrievalService](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#76-396) импорт удаляется? | ✅ OK | Hybrid импортирует [sanitize_fts5_query](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#22-74) напрямую из модуля (`from .fts5_retrieval_service import sanitize_fts5_query`). Класс [FTS5RetrievalService](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#76-396) больше не нужен в endpoint. Но сам файл остаётся (используется в fallback внутри hybrid). |
| Video Hub получит вектора? | ✅ OK | `expert_id != "video_hub"` проверка сохранена в плане (строка 448). Video Hub идёт по своей ветке. |
| Overengineering | ✅ Нет | План чистый MVPб ез лишних абстракций. |

---

## 📋 Итоговый чеклист (ревизованный)

| # | Действие | Severity | Статус |
|---|---|---|---|
| 1 | `_vector_search`: добавить `created_at` как metadata column в `vec0` для корректной фильтрации `cutoff_date` | 🔴 Блокер | Подтверждён |
| 2 | Добавить `from sqlite_vec import serialize_float32` в hybrid service | 🔴 Build blocker | **Новый** |
| 3 | `embed_posts.py`: фильтровать `LENGTH(message_text) > 30` при выборе постов | 🟡 Quality | **Новый** |
| 4 | Shadow testing: обновить или временно отключить | 🟡 Logging | **Новый** |
| 5 | `embed_batch`: сделать настоящим batch через `genai.embed_content(content=list)` | 🟢 Оптимизация | Подтверждён |
| 6 | Добавить комментарий: "Soft Freshness заменяет Gravity из FTS5RetrievalService" | 🟢 Документация | Понижен |
