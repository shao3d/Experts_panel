# 🔍 Аудит Pipeline: Документация vs Код

> Проверено: [pipeline.md](file:///Users/andreysazonov/Documents/Projects/Experts_panel/docs/architecture/pipeline.md) vs реализация в коде.
> Фокус: FTS5 + AI Scout, Smart Ranking, Cron Metadata.
> Дата: 2026-03-15

---

## 🔴 Критические баги

### 1. FTS5 UPDATE Trigger: нет WHEN-guard → «Зомби-посты» в индексе

**Файл:** [019_fts5_metadata_rebuild.sql](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/019_fts5_metadata_rebuild.sql#L48-L59)

INSERT-триггер корректно проверяет `WHEN LENGTH(COALESCE(new.message_text, '')) > 30`. Но UPDATE-триггер **не имеет** такой проверки:

```diff
 CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text, post_metadata ON posts
+WHEN LENGTH(COALESCE(new.message_text, '')) > 30
 BEGIN
     DELETE FROM posts_fts WHERE rowid = old.post_id;
     INSERT INTO posts_fts(rowid, content)
     SELECT new.post_id, new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), '')
-    WHERE LENGTH(COALESCE(new.message_text, '')) > 30;
+    ;
 END;
```

> [!CAUTION]
> **Сценарий поломки:** Cron-скрипт [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py) обновляет `post_metadata` для ВСЕХ постов, включая те, у которых `message_text ≤ 30 символов`. Триггер срабатывает, **удаляет** старую запись из FTS, а INSERT с WHERE-фильтром **не вставляет новую**. Но DELETE уже произошёл. Итог: если пост был в FTS (от INSERT-триггера), он **теряется навсегда** при обновлении metadata.
>
> **Реальный сценарий:** Маловероятный, т.к. INSERT-триггер тоже фильтрует по >30. Но если текст поста был отредактирован (укорочен), и потом метаданные обновились — пост исчезнет из FTS. **Рекомендация:** Добавить `WHEN` guard для consistency и safety.

**Severity:** 🟡 Medium (edge case, но принципиальный дефект)

---

### 2. Cron-скрипт: нет фильтрации коротких постов → Бесполезные LLM-вызовы

**Файл:** [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py#L58-L60)

```python
posts = db.query(Post).filter(
    Post.post_metadata.is_(None)
).limit(batch).all()
```

> [!WARNING]
> Скрипт обогащает **все** посты БЕЗ metadata, **включая media-only** (пустой `message_text` или `<= 30` символов). Для таких постов:
> 1. LLM получает пустую строку → генерирует мусорные ключевые слова → тратит токены впустую.
> 2. Мусорные keywords попадают в FTS5 индекс (если INSERT trigger позволит).
>
> **Fix:** Добавить фильтр `func.length(Post.message_text) > 30` в запрос.

**Severity:** 🔴 High (деньги на ветер + загрязнение индекса)

---

### 3. [_force_or_only](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/ai_scout_service.py#118-129) уничтожает AND внутри кавычек → Ломает фразовый поиск

**Файл:** [ai_scout_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/ai_scout_service.py#L118-L128)

```python
def _force_or_only(self, query: str) -> str:
    result = re.sub(r'\bAND\b', 'OR', query, flags=re.IGNORECASE)
    return result
```

Комментарий в коде говорит: *"preserve AND inside quotes (phrase search)"* — но реализация **не делает этого**!

> [!CAUTION]
> Если AI Scout сгенерирует запрос типа `"search AND replace" OR grep`, `\bAND\b` regex заменит AND внутри кавычек на OR → `"search OR replace" OR grep`.
>
> FTS5 фразовый поиск `"search AND replace"` станет `"search OR replace"` — совсем другой результат.

**Практический риск:** 🟡 Medium — AI Scout prompt требует OR-only, и фразы типа "AND" в кавычках маловероятны. Но комментарий обещает защиту, которой нет.

---

## 🟡 Логические дыры и несоответствия

### 4. BM25 нормализация: деление на ноль при одном результате

**Файл:** [fts5_retrieval_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#L200-L220)

```python
ranks = [row[1] for row in raw_results]
min_rank = min(ranks) if ranks else 0
max_rank = max(ranks) if ranks else 0
rank_range = max_rank - min_rank if max_rank != min_rank else 1
# ...
normalized_bm25 = (max_rank - raw_rank) / rank_range
```

Когда FTS5 возвращает **один результат**: `min_rank == max_rank` → `rank_range = 1` → `normalized_bm25 = 0 / 1 = 0.0`.

Единственный найденный пост получает BM25 = 0, и его финальный score = [(0 * 0.7 + 0.3) * freshness = 0.3 * freshness](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/models/post.py#12-66).

> [!NOTE]
> Это не crash, но **логически неверно**: единственный найденный пост по запросу должен получить score = 1.0 (лучший из лучших). Вместо этого он получает minimal score (0.3 * freshness).
>
> **Fix:** Присваивать `normalized_bm25 = 1.0` когда только один результат.

```diff
- rank_range = max_rank - min_rank if max_rank != min_rank else 1
+ # Single result = best match in set, normalize to 1.0
+ if max_rank == min_rank:
+     normalized_bm25 = 1.0
+ else:
+     normalized_bm25 = (max_rank - raw_rank) / (max_rank - min_rank)
```

**Severity:** 🟡 Medium (влияет на порядок сортировки в edge case)

---

### 5. FTS5 SQL: `f.rowid` vs `p.post_id` — скрытая зависимость

**Файл:** [fts5_retrieval_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py#L298-L310)

```sql
SELECT f.rowid as post_id, f.rank as bm25_rank, p.created_at
FROM posts_fts f
JOIN posts p ON p.post_id = f.rowid
WHERE posts_fts MATCH :match_query
  AND p.expert_id = :expert_id
```

Запрос предполагает `f.rowid == p.post_id`. Это работает **только потому что** миграция делает `INSERT INTO posts_fts(rowid, content) SELECT post_id, ...`.

> [!NOTE]
> Это не баг сейчас, но **хрупкая архитектура**. Если кто-то случайно перестроит FTS5 без `rowid = post_id`, вся система сломается молча (возвращаются чужие посты). Стоит добавить комментарий-предупреждение в миграцию.

**Severity:** 🟢 Low (работает, но хрупко)

---

### 6. Cron-скрипт: `db.commit()` внутри цикла на каждый пост

**Файл:** [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py#L69-L90)

```python
for post in posts:
    metadata = await generate_metadata(client, post.message_text or "")
    post.post_metadata = json.dumps(metadata, ensure_ascii=False)
    post.metadata_generated_at = datetime.utcnow()
    db.commit()  # ← Каждый пост = отдельный COMMIT
```

> [!NOTE]
> Per-post commit — это и плюс (при ошибке уже обработанные посты сохраняются), и минус:
> 1. **Каждый commit триггерит UPDATE trigger → FTS5 перестройка записи**. При batch_size=50, это 50 trigger-вызовов.
> 2. Нет `db.flush()` перед commit → SQLAlchemy может не увидеть изменения ORM до commit.
>
> На практике это работает (SQLAlchemy auto-flush перед commit), но лучше быть явным.

**Severity:** 🟢 Low (работает, но неоптимально)

---

### 7. Cron: пустой `message_text` → LLM генерирует мусор

**Файл:** [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py#L76)

```python
metadata = await generate_metadata(client, post.message_text or "")  # ← "" для media-only постов
```

Связано с багом #2. Когда `message_text` is None, скрипт передаёт пустую строку в LLM. Промпт [metadata_prompt.txt](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/prompts/metadata_prompt.txt) не обрабатывает пустой текст → LLM галлюцинирует ключевые слова из ничего.

**Severity:** 🔴 High (дублирует и усиливает баг #2)

---

### 8. Документация [pipeline.md](file:///Users/andreysazonov/Documents/Projects/Experts_panel/docs/architecture/pipeline.md) vs Код: `MAP_CHUNK_SIZE`

**Документация** (pipeline.md, line 29): `50 posts per chunk (MAP_CHUNK_SIZE)`
**Код** (config.py): `MAP_CHUNK_SIZE = int(os.getenv("MAP_CHUNK_SIZE", "50"))` ✅
**Код** (map_service.py, line 33): `DEFAULT_CHUNK_SIZE = 100` ← **мёртвый код!**

> [!NOTE]
> `MapService.DEFAULT_CHUNK_SIZE = 100` — это **мёртвый default**, т.к. endpoint ВСЕГДА передаёт `config.MAP_CHUNK_SIZE (50)`. Если кто-то создаст [MapService()](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/map_service.py#26-510) без аргументов (в тестах) — получит 100, а не 50.
>
> **Fix:** Синхронизировать `DEFAULT_CHUNK_SIZE = 50` или убрать его и сделать `chunk_size` обязательным.

**Severity:** 🟢 Low (мёртвый код, но потенциальный surprize в тестах)

---

### 9. AI Scout: KNOWN_SLANG Fallback — двойные wildcard-ы

**Файл:** [ai_scout_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/ai_scout_service.py#L224-L228)

```python
expanded_terms.append(f"{word}*")       # "кубер*"
expanded_terms.append(f"{en}")           # "kubernetes OR k8s"
```

Для `"кубер"` fallback генерирует: `кубер* OR kubernetes OR k8s`.

Но если `en = "kubernetes OR k8s"` — это вставляется **как строка** в OR-цепочку: `кубер* OR kubernetes OR k8s`.

FTS5 итерпретирует `kubernetes OR k8s` как **два отдельных токена с OR** — это ОК.

> [!NOTE]
> **Но:** если [en](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py#50-96) содержит кавычки (e.g., `"си плюс плюс"`), результат: `слово* OR cpp OR cplusplus OR "си плюс плюс"`. В контексте `OR "-joined"` строки это корректно. **Нет бага.** ✅

---

## ✅ Что работает правильно (Подтверждено)

| Область | Статус | Детали |
|---|---|---|
| FTS5 + AI Scout интеграция в endpoint | ✅ | Scout → FTS5 → Map pipeline корректно проводит |
| Circuit Breaker для FTS5 fallback | ✅ | Threshold=3, корректная asyncio-безопасность |
| Smart Ranking формула | ✅ | BM25 * 0.7 + 0.3 floor → Time Decay (90d half-life) |
| Hybrid Mode (20% random sample) | ✅ | Кodе соответствует документации |
| Smart Fallback (MIN_FTS5_RESULTS=10) | ✅ | При <10 результатах → all posts |
| FTS5 table indexes metadata keywords | ✅ | Migration 019 объединяет `message_text + keywords` |
| Trigger на UPDATE `post_metadata` | ✅ | Обновление metadata пересоздаёт FTS запись |
| Config: MODEL_SCOUT = gemini-3.1-flash-lite-preview | ✅ | Соответствует pipeline.md |
| Config: METADATA_MODEL = gemini-3.1-flash-lite-preview | ✅ | Соответствует pipeline.md |
| Date filtering (use_recent_only) | ✅ | Применяется в Map, Resolve, Comments |
| Expert isolation by expert_id | ✅ | В FTS5 SQL есть `AND p.expert_id = :expert_id` |

---

## 📋 Приоритизированный план фиксов

| # | Приоритет | Что исправить | Файл |
|---|---|---|---|
| 1 | 🔴 High | Фильтр `LENGTH(message_text) > 30` в cron-запросе | [enrich_post_metadata.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/enrich_post_metadata.py) |
| 2 | 🟡 Medium | BM25 = 1.0 для единственного результата | [fts5_retrieval_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py) |
| 3 | 🟡 Medium | WHEN guard на UPDATE trigger | [019_fts5_metadata_rebuild.sql](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/019_fts5_metadata_rebuild.sql) |
| 4 | 🟢 Low | `DEFAULT_CHUNK_SIZE = 50` или удалить | [map_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/map_service.py) |
| 5 | 🟢 Info | Комментарий в [_force_or_only](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/ai_scout_service.py#118-129) об ограничении | [ai_scout_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/ai_scout_service.py) |
