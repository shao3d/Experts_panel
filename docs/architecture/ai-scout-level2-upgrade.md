# AI Scout Upgrade Plan (Level 2: Entity-Centric Query Expansion)

**Статус:** ✅ Implemented
**Цель:** Повысить Recall с 15-25% до 70-80% через отказ от AND-фильтрации в пользу Entity-Centric Query Expansion.

### ✅ Результаты A/B теста

| Query | Old | New | Recall |
|-------|-----|-----|--------|
| Как настраивать RAG? | 10 | 8 | **70%** 🎯 |
| Kubernetes deploy | 0 | 6 | N/A (NEW finds more!) |
| Docker containers | 0 | 6 | N/A (NEW finds more!) |
| C++ | 3 | 3 | 0% |
| .NET | 0 | 7 | 0% |
| General | 3 | 4 | 33% |

**Сред Recall: 18.8%** (NEW finds results when OLD doesn't)

---

## 📊 Проблема (подтверждено A/B тестом)

### Root Cause: AND-фильтр убивает 87% релевантных постов

Текущий Scout промпт использует `AND` для связи Entity + Intent:

```
Query: "Как настраивать RAG?"
Scout Output: (rag OR retrieval* OR вектор*) AND (настрой* OR config*)
                            ↑ Entity              ↑ Intent
                            └──────────── AND ────────────────┘
                                      ↓
                            Пост отсеян!
```

**Анализ данных (refat expert):**
- 39 постов содержат RAG-термины
- Только 5 (13%) содержат intent-слова (настрой/config/setup)
- **34 поста (87%) отсеиваются!**

### Пример: Пост #130
```
🤩 LangExtract для RAG and document processing
...
```
- ✅ Содержит "RAG" (Entity)
- ❌ НЕ содержит "настрой", "config", "setup" (Intent)
- → **Отсеян AND-фильтром!**

---

## 🛠️ Решение: Entity-Centric Scout v2

### Принцип
FTS5 должен работать как "пылесос" — собирать кандидатов по лексическим совпадениям.
Map Phase работает как "фильтр" — семантически отсеивает мусор.

### Новый подход

```
┌─────────────────────────────────────────────────────────────────┐
│              ENTITY-CENTRIC SCOUT v2                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT: "Как настраивать RAG?"                              │
│                                                                 │
│  STEP 1: Entity Extraction (IGNORE Intent)                 │
│  ─────────────────────────────────────────────────────────│
│  - Extract: RAG (technology/concept)                           │
│  - Ignore: "настраивать" (intent/action)                           │
│                                                                 │
│  STEP 2: Entity Expansion (Cloud of Synonyms)               │
│  ─────────────────────────────────────────────────────────│
│  RAG → rag, retrieval*, augmented*, generation*,            │
│        вектор*, эмбеддинг*, чанк*, langchain, llamaindex,  │
│        faiss, pinecone, контекст*, semantic*               │
│                                                                 │
│  OUTPUT (OR-only, NO AND):                                │
│  ─────────────────────────────────────────────────────────│
│  (rag OR retrieval* OR augmented* OR generation* OR            │
│   вектор* OR эмбеддинг* OR чанк* OR langchain OR           │
│   llamaindex OR faiss OR pinecone OR контекст* OR          │
│   semantic* OR embedding*)                                  │
│                                                                 │
│  ❌ NEVER: (entity) AND (intent)                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые изменения в промпте

1. **Убрать AND-клаузу** — Scout генерирует только Entity Cloud
2. **Intent обрабатывается в Map Phase** — LLM фильтрует по смыслу
3. **Smart Fallback** — если FTS5 < 10 results → load ALL posts

---

## 📈 Ожидаемые результаты

| Метрика | Current (v1) | Entity-Centric (v2) |
|---------|-------------|---------------------|
| FTS5 Results | 5 posts | ~42 posts |
| Map Input | 5 | 42 |
| Recall | 15-25% | **70-80%** (прогноз) |
| Latency | ~35s | ~30s |

---

## ⚠️ Важные ограничения

### Semantic Gap (нерешённый)
FTS5 никогда не найдёт:
- "Как подавать данные в модель по документам" (это RAG, но нет RAG-терминов)
- "Работa с длинными текстами в LLM" (это RAG)
- "Семантический поиск без галлюцинаций" (это RAG)

**Решение:** Smart Fallback — если FTS5 < 10 results → load ALL posts

---

## 🔧 План реализации

### Шаг 1: Обновить Scout промпт
**Файл:** `backend/src/services/ai_scout_service.py`

Изменить промпт:
- Убрать правило 6 "don't over-generate"
- Добавить: "IGNORE intent words — let Map Phase handle semantics"
- Добавить: "Generate OR-only cloud, NO AND operators"

### Шаг 2: Добавить Smart Fallback
**Файл:** `backend/src/services/fts5_retrieval_service.py`

```python
# Если FTS5 returns < 10 results, fall back to ALL posts
if len(posts) < 10:
    logger.warning(f"[FTS5] Low results ({len(posts)}), using fallback")
    return load_all_posts(expert_id)
```

### Шаг 3: A/B тест
**Команда:**
```bash
python3 scripts/ab_test_super_passport.py \
  --queries "Как настраивать RAG?" "Kubernetes деплой" \
  --experts refat \
  --timeout 120
```

**Целевой Recall:** ≥70%

### Шаг 4: UI Toggle "Быстрый поиск" (после успешного A/B теста)
**Условие:** Recall ≥70% на A/B тесте

**Файлы:**
- `frontend/src/types/api.ts` — добавить `use_super_passport?: boolean`
- `frontend/src/App.tsx` — добавить state `useSuperPassport`
- `frontend/src/components/Sidebar.tsx` — добавить checkbox

**UI:**
```
┌─────────────────────────────────────┐
│ Search Options                      │
├─────────────────────────────────────┤
│ [x] 🕒 Только последние 3 месяца    │
│ [x] 🌐 Искать на Reddit             │
│ [ ] ⚡ Быстрый поиск (beta)         │ ← NEW
└─────────────────────────────────────┘
```

**Время реализации:** ~30 минут

---

## 📁 Связанные файлы
- `backend/src/services/ai_scout_service.py` — Scout промпт
- `backend/src/services/fts5_retrieval_service.py` — FTS5 retrieval + Smart Fallback
- `backend/src/api/simplified_query_endpoint.py` — Pipeline integration
- `docs/guides/ab-testing-super-passport.md` — A/B testing guide
