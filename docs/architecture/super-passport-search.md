# Super-Passport Search Architecture (Experts Panel v2.0)

> [!NOTE]
> **Эволюция Фичи:** Данная архитектура эволюционировала. Текущая реализация (Embs&Keys Search) объединяет описанный здесь Entity-Centric FTS5 подход с **векторным поиском (`sqlite-vec`)** и сливает их через алгоритм *Reciprocal Rank Fusion (RRF)*. См. `hybrid_retrieval_plan.md` и исходный код `hybrid_retrieval_service.py` как актуальный SSOT.

**Статус:** ✅ Эволюционировало в Hybrid Retrieval (Updated 2026-03-26)
**Feature Flag:** `use_super_passport: true` (доступно через UI чекбокс "Embs&Keys")
**Цель:** Масштабирование предфильтрации постов для Map Phase через гибридный сплит (Vector + FTS5), предотвращение OOM/CPU spikes.

---

## 📊 Текущая архитектура (из кода и БД)

Решение базируется на трёх столпах:
1. **Паттерн Bulkhead:** Глобальное ограничение параллельности (`MAX_CONCURRENT_EXPERTS=5`) → спасти сервер от OOM.
2. **Двухэтапная воронка (FTS5 + Vector KNN):** Pre-filter постов через SQLite FTS5 + Vector KNN (sqlite-vec) с RRF → снижение входа в Map Phase на 70–90%.
3. **AI Scout (Entity-Centric v2):** LLM генерирует OR-only облака сущностей (например, `rag OR retrieval OR vector`), игнорируя глаголы, чтобы не забивать BM25 мусором.

### Полный пайплайн (6+ фаз)

FTS5 влияет ТОЛЬКО на шаг 1. Все остальные фазы работают с результатом Map, не с исходными постами.

```
1. AI Scout генерирует FTS5 MATCH-запрос (OR-only Entity Cloud).
2. Загрузка постов:
   - FTS5 ищет совпадения по тексту и сгенерированным метаданным.
   - Если результатов < 10, включается Smart Fallback (загрузка всех постов эксперта).
   - [Временно] Hybrid Mode: добавляется 20% случайных постов для страховки от семантического разрыва (Semantic Gap).
3. Map Phase (LLM-чанки по 50 постов)
4. HIGH/MEDIUM split → Medium Scoring (второй LLM)
5. Resolve (link expansion из links table)
6. Reduce (финальный синтез)
7. Language Validation
8. Comment Groups (drift analysis)
```

---

## 🔬 Эволюция пайплайна (A/B тесты)

### Проблема v1: AND-фильтр убивал Recall
Первая версия Скаута генерировала запросы с `AND` (например: `(rag OR вектор*) AND (настрой* OR config*)`). 
Это отсеивало 87% релевантных постов, потому что эксперты редко используют оба типа слов в одном посте. **Recall падал до 15%**.

### Решение v2: Entity-Centric Scout
Сделан переход на OR-only запросы. AI Scout теперь выделяет только технические сущности и разворачивает их в широкое облако (`rag OR retrieval* OR вектор* OR эмбеддинг*`).
*Результат:* Recall вырос до **70%**. FTS5 работает как широкий "пылесос", а Map Phase семантически фильтрует мусор.

### Проблема v2: Semantic Gap
FTS5 — это лексический поиск. Пост эксперта: *"Отличный гайд по подаче данных в модель по документам"* семантически относится к RAG, но FTS5 его никогда не найдет, так как там нет слова "RAG" или "вектор".

### Финальное решение: Hybrid Retrieval (Vector KNN + FTS5 + RRF)

> **Примечание:** Промежуточное решение через Pre-computed Metadata (`enrich_post_metadata.py`) было удалено в марте 2026. AI Scout v3 с билингвальными OR-запросами и вайлдкартами полностью закрывает Semantic Gap на стороне FTS5, а Vector KNN (`sqlite-vec`) добавляет семантический поиск по эмбеддингам.

Текущая архитектура:
1. **AI Scout v3** генерирует OR-only Entity Cloud (`rag OR retrieval* OR вектор* OR эмбеддинг*`) с билингвальным расширением.
2. **FTS5** ищет по чистому `message_text` (без LLM-метаданных, миграция 023).
3. **Vector KNN** (`sqlite-vec`) ищет по предвычисленным эмбеддингам (`embed_posts.py`).
4. **RRF** сливает результаты FTS5 и Vector KNN с Soft Freshness Decay.

---

## 🛡️ Защиты и Edge Cases

| # | Edge Case | Серьёзность | Решение |
|---|-----------|-------------|---------|
| 1 | FTS5 Syntax Error на спецсимволах | 🔴 | Скаут переводит `C++` в `cpp OR "си плюс плюс"`. Запрет `*` после спецсимволов. |
| 2 | BM25 Pollution (мусор в выдаче) | 🔴 | Промпт Скаута строго запрещает использование глаголов и общих слов (настройка, опыт). |
| 3 | Низкий FTS5 результат | 🟡 | Smart Fallback: если найдено < 10 постов, возвращаемся к загрузке ВСЕХ постов (OLD Pipeline). |
| 4 | Semantic Gap | 🟡 | Решено через Vector KNN (sqlite-vec) + AI Scout v3 билингвальное расширение. |
| 5 | Video Hub несовместим | 🟡 | Явное исключение `if expert_id == "video_hub"`. Видео-сайдкар работает независимо. |
| 6 | I/O взрыв Map Phase | 🟡 | Глобальный `Semaphore(MAX_CONCURRENT_EXPERTS=5)`. |
| 7 | Ошибки JSON в Map Phase | 🟡 | `MAP_CHUNK_SIZE` снижен со 100 до 50 для стабильности генерации длинных JSON ответов. |

---

## 🚀 Планы на будущее

Semantic Gap полностью закрыт через Hybrid Retrieval (Vector KNN + FTS5 + RRF). Metadata enrichment и Hybrid Mode (рандомное подмешивание) удалены как избыточные.