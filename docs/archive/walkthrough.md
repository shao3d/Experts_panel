# 🔬 Deep Pipeline Comparison: Результаты

## Что сделано

1. **Пофиксил баг** в [fts5_retrieval_service.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/services/fts5_retrieval_service.py): `HYBRID_MIN_SAMPLE=0` + guard `if RATIO > 0`.
2. **Написал** [deep_compare_pipelines.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/deep_compare_pipelines.py) — корректный тест, сравнивающий выходы Map Phase.
3. **Запустил тест**: query "Как правильно сейчас настраивать и работать со Skills?", эксперты doronin + akimov.

## Результаты

> [!CAUTION]
> **Overall True Recall: 28%** — NEW pipeline теряет **72%** релевантных постов, найденных OLD.

| Метрика | doronin | akimov | Total |
|---------|---------|--------|-------|
| OLD input (все посты) | 631 | 657 | 1288 |
| **NEW input (FTS5)** | **179** | **139** | **318** |
| OLD relevant (H+M) | 165 | 28 | **193** |
| NEW relevant (H+M) | 66 | 54 | **120** |
| **Overlap** | **39** | **15** | **54** |
| **True Recall** | **23.6%** 🔴 | **53.6%** 🔴 | **28.0%** 🔴 |
| Lost by FTS5 | 165 | 25 | **190** |
| Lost by Map | 0 | 2 | 2 |
| NEW-only wins | 27 | 39 | **66** |
| Latency | 124s → 44s ✅ | 14s → 46s ❌ | — |

## Диагностика: Почему FTS5 теряет 190 постов?

### Корневая проблема: Scout генерирует слишком узкий запрос

Scout query для "Skills":
```
skills OR навык* OR компетенции OR competency OR "soft skills" OR "hard skills" 
OR обучение OR training OR development OR развитие OR профиль OR profile 
OR квалификация OR qualification OR аттестация OR assessment
```

Это ищет **буквальное слово "skills"** и его прямые синонимы. Но OLD pipeline (Map Phase на ВСЕХ постах) классифицировал как релевантные посты про:
- Cursor IDE, AI-агенты, промпт-инженерию ← нет слова "skills"
- Agentic AI, vibe-coding ← нет слова "skills"
- Claude Skills, AgentKit ← есть, но разные контексты

> [!IMPORTANT]
> **Map Phase понимает СЕМАНТИКУ запроса** — "Skills" в контексте AI-разработки означает "инструменты, методы, навыки работы с AI". FTS5 ищет только по **лексическому совпадению** ключевых слов.

### Это фундаментальный Semantic Gap

FTS5 + metadata enrichment **не может** закрыть разрыв между лексическим поиском и семантическим пониманием. Metadata keywords расширяют охват, но только для терминов, явно упомянутых в тексте, а не для связанных по смыслу тем.

### Интересный парадокс: 66 NEW-only wins

NEW pipeline нашёл 66 постов, которые OLD пропустил! Это потому что:
- FTS5 "сфокусировал" Map Phase на меньшем наборе более релевантных постов
- Map Phase с меньшим контекстом (179 vs 631 постов) может быть более точным — меньше "разбавление внимания" LLM

## Выводы

| # | Вывод |
|---|-------|
| 1 | **FTS5 Super-Passport НЕ готов к production** в текущем виде. Recall 28% неприемлем. |
| 2 | **OLD pipeline (Map на всех постах) надёжнее**, но дороже (3-10x больше токенов + latency). |
| 3 | **Bug Hybrid досыпки пофикшен**, но это не решает корневую проблему. |
| 4 | **A/B тест скрипт** подтверждён как невалидный — измерял не тот уровень. |
| 5 | **Новый тест-скрипт** [deep_compare_pipelines.py](file:///Users/andreysazonov/Documents/Projects/Experts_panel/backend/scripts/deep_compare_pipelines.py) даёт достоверные результаты. |

## Следующие шаги (на обсуждение)

1. **Отключить Super-Passport по умолчанию** (`USE_SUPER_PASSPORT_DEFAULT = false` — уже так) ✅
2. **Рассмотреть embedding-based retrieval** вместо FTS5 — закрывает Semantic Gap
3. **Или**: Расширить Scout prompt чтобы генерировал **все возможные** связанные термины, не только прямые синонимы
4. **Или**: Увеличить `MAX_FTS_RESULTS` и добавить semantic re-ranking поверх FTS5
