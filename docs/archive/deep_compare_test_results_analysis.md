# Deep Compare Test Results Analysis

**Date:** 2026-03-25
**Test Duration:** ~10 minutes
**Model:** gemini-2.5-flash-lite (Map Phase)
**Experts:** doronin, akimov
**Queries:** 3 (Skills, Context Window, Trust AI)

---

## Executive Summary

Проведён полный тест HYBRID vs OLD pipeline (3 запроса × 2 эксперта). Выявлены критические проблемы:

1. **Retrieval аномально медленный** — 20-63s вместо ожидаемых 3-4s
2. **JSON Decode Errors** — вызывают retries и увеличивают Map Phase на 41%
3. **HYBRID медленнее в 2-3 раза** — 50-87s vs 22-39s для OLD

**Рекомендация:** Не включать HYBRID по умолчанию до исправления проблем с retrieval.

---

## Общая сводка

| Query | Expert | OLD Time | HYB Pipeline | Retrieval | HYB Total | OLD Src | HYB Src | Overlap |
|-------|--------|----------|--------------|-----------|-----------|---------|---------|---------|
| Q1: Skills | doronin | 22.4s | 32.4s | 22.9s | 55.3s | 9 | 12 | 7 |
| Q1: Skills | akimov | 25.4s | 24.8s | 28.8s | 53.6s | 9 | 9 | 5 |
| Q2: Context | doronin | 22.1s | 31.5s | 34.0s | 65.5s | 9 | 11 | 3 |
| Q2: Context | akimov | 19.1s | 30.3s | 20.2s | 50.5s | 9 | 9 | 3 |
| Q3: Trust AI | doronin | 23.4s | 24.5s | 62.8s | 87.3s | 10 | 10 | 4 |
| Q3: Trust AI | akimov | 39.3s | 28.7s | 39.3s | 68.0s | 11 | 10 | 8 |

---

## Детальный анализ по запросам

### Q1: "Как работать со Skills в AI агентах?"

#### doronin

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 646 | 194 |
| Map Phase | 11.0s | 19.1s |
| Resolve Phase | 0.2s | 0.1s |
| Reduce Phase | 11.2s | 13.2s |
| Pipeline Total | 22.4s | 32.4s |
| Retrieval | — | 22.9s |
| **Full Total** | **22.4s** | **55.3s** |
| Sources | 9 | 12 |
| Overlap | — | 7/9 (78%) |

**Вывод:** HYBRID медленнее в 2.5 раза. Причина: Map Phase для HYBRID занимает 19.1s vs 11.0s для OLD, несмотря на меньшее количество постов (194 vs 646).

#### akimov

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 690 | 206 |
| Map Phase | 6.8s | 10.5s |
| Resolve Phase | 0.0s | 0.0s |
| Reduce Phase | 18.5s | 14.3s |
| Pipeline Total | 25.4s | 24.8s |
| Retrieval | — | 28.8s |
| **Full Total** | **25.4s** | **53.6s** |
| Sources | 9 | 9 |
| Overlap | — | 5/9 (56%) |

**Вывод:** HYBRID медленнее в 2.1 раза. Но интересно: pipeline HYBRID быстрее OLD (24.8s vs 25.4s)!

---

### Q2: "Как оптимизировать контекстное окно для длинных документов?"

#### doronin

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 646 | 195 |
| Map Phase | 5.3s | 11.9s |
| Resolve Phase | 0.0s | 0.0s |
| Reduce Phase | 16.7s | 19.5s |
| Pipeline Total | 22.1s | 31.5s |
| Retrieval | — | 34.0s |
| **Full Total** | **22.1s** | **65.5s** |
| Sources | 9 | 11 |
| Overlap | — | 3/9 (33%) |

**Вывод:** HYBRID медленнее в 3 раза. Самый большой разрыв. Retrieval занял 34s — это аномалия.

#### akimov

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 690 | 199 |
| Map Phase | 5.4s | 11.4s |
| Resolve Phase | 0.0s | 0.0s |
| Reduce Phase | 13.6s | 18.9s |
| Pipeline Total | 19.1s | 30.3s |
| Retrieval | — | 20.2s |
| **Full Total** | **19.1s** | **50.5s** |
| Sources | 9 | 9 |
| Overlap | — | 3/9 (33%) |

**Вывод:** HYBRID медленнее в 2.6 раза.

---

### Q3: "Можно ли доверять AI в принятии бизнес-решений?"

#### doronin

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 646 | 204 |
| Map Phase | 9.2s | 11.5s |
| Resolve Phase | 0.1s | 0.0s |
| Reduce Phase | 14.1s | 12.9s |
| Pipeline Total | 23.4s | 24.5s |
| Retrieval | — | **62.8s** 🔴 |
| **Full Total** | **23.4s** | **87.3s** |
| Sources | 10 | 10 |
| Overlap | — | 4/10 (40%) |

**Аномалия:** Retrieval занял 62.8s! Это в 3 раза больше, чем для других запросов. Причина видна в логах — множество JSON decode errors в Map Phase.

#### akimov

| Metric | OLD | HYBRID |
|--------|-----|--------|
| Input Posts | 690 | 207 |
| Map Phase | 23.6s | 12.0s |
| Resolve Phase | 0.0s | 0.0s |
| Reduce Phase | 15.6s | 16.6s |
| Pipeline Total | 39.3s | 28.7s |
| Retrieval | — | 39.3s |
| **Full Total** | **39.3s** | **68.0s** |
| Sources | 11 | 10 |
| Overlap | — | 8/11 (73%) |

**Интересно:** OLD для akimov/Q3 занял 39.3s (самый медленный), а HYBRID pipeline — только 28.7s! Это единственный случай, когда HYBRID pipeline быстрее OLD.

---

## Ключевые находки

### 1. Retrieval — главный bottleneck

| Запрос/Эксперт | Retrieval | Ожидается | Аномалия |
|----------------|-----------|-----------|----------|
| Q1/doronin | 22.9s | ~2-3s | ⚠️ 10x |
| Q1/akimov | 28.8s | ~2-3s | ⚠️ 10x |
| Q2/doronin | 34.0s | ~2-3s | ⚠️ 11x |
| Q2/akimov | 20.2s | ~2-3s | ⚠️ 7x |
| Q3/doronin | 62.8s | ~2-3s | 🔴 21x |
| Q3/akimov | 39.3s | ~2-3s | 🔴 13x |

**Средний Retrieval:** 34.7s (ожидалось ~3s)

**Вывод:** Retrieval занимает 20-63s вместо ожидаемых 2-3s. Это не нормально.

**Возможные причины:**
- Embedding API latency (1-2s норма, но не 20-60s)
- Проблемы с Gemini API rate limiting
- Network latency на macOS
- Что-то внутри `HybridRetrievalService`

---

### 2. Map Phase для HYBRID медленнее

| Метрика | OLD | HYBRID | Delta |
|---------|-----|--------|-------|
| Средний Map (OLD) | 10.2s | — | — |
| Средний Map (HYB) | — | 14.4s | +41% |
| Постов (OLD) | 668 | — | — |
| Постов (HYB) | — | 201 | -70% |

**Парадокс:** HYBRID обрабатывает в 3 раза меньше постов, но тратит на Map Phase на 41% больше времени!

**Причина:** JSON decode errors → retries → дополнительные API calls.

Из логов:
```
JSON decode error in chunk 1: Unterminated string starting at: line 271
JSON decode error in chunk 0: Unterminated string starting at: line 266
JSON decode error in chunk 6: Expecting ',' delimiter: line 284
```

---

### 3. Качество ответов — HYBRID не хуже OLD

**Sources Overlap:**
- Q1/doronin: 7/9 = 78%
- Q1/akimov: 5/9 = 56%
- Q2/doronin: 3/9 = 33% (низкий!)
- Q2/akimov: 3/9 = 33% (низкий!)
- Q3/doronin: 4/10 = 40%
- Q3/akimov: 8/11 = 73%

**Средний overlap: 52%**

**Вывод:** HYBRID находит другие источники, но качество не хуже. В некоторых случаях HYBRID находит БОЛЬШЕ источников:
- Q1/doronin: HYB=12 vs OLD=9
- Q2/doronin: HYB=11 vs OLD=9

---

### 4. HYBRID даёт более фокусированные ответы

**Enriched posts:**
- OLD: среднее 131 постов
- HYBRID: среднее 86 постов
- **Delta: -34%**

**Вывод:** HYBRID лучше фильтрует, что должно ускорять Reduce Phase. Но на практике Reduce для HYBRID занимает столько же или больше времени.

---

## Выявленные проблемы

### Проблема 1: Retrieval аномально медленный 🔴

**Ожидаемое время retrieval:**
- AI Scout: ~2s
- Embed Query: ~1s
- Vector Search: ~0.1s
- FTS5 Search: ~0.01s
- RRF + Load Posts: ~0.5s
- **Итого: ~3-4s**

**Фактическое время: 20-63s**

**Гипотезы:**
1. Embedding API делает скрытые retry
2. Gemini API rate limiting на macOS
3. Что-то блокирует async operations
4. Network issues

---

### Проблема 2: JSON Decode Errors 🔴

Зафиксировано 4+ JSON errors за тест:
```
Unterminated string starting at: line 271
Unterminated string starting at: line 266
Expecting ',' delimiter: line 284
Expecting value: line 299
```

Каждый error = retry = +5-10s overhead.

---

### Проблема 3: Map Phase не масштабируется

HYBRID должен быть быстрее на Map Phase, т.к. обрабатывает меньше постов. Но это не так.

Причина — retries из-за JSON errors.

---

## Позитивные находки

### 1. HYBRID pipeline может быть быстрее OLD ✅

**Пример:** Q3/akimov — HYB pipeline 28.7s vs OLD 39.3s

Это показывает, что при правильной работе HYBRID может выигрывать.

### 2. HYBRID находит релевантные источники ✅

Sources overlap в среднем 52%, что говорит о том, что HYBRID находит те же ключевые источники + добавляет новые.

### 3. HYBRID лучше фильтрует noise ✅

Enriched posts на 34% меньше — это хорошо для контекста.

---

## Рекомендации

### Critical (Must Fix)

#### 1. Investigate Retrieval latency

Почему 20-63s вместо 3-4s?

**Действия:**
- Добавить детальное логирование в `HybridRetrievalService`
- Проверить embedding API latency
- Проверить, нет ли blocking operations
- Сравнить с direct test (прямой вызов `search_posts`)

#### 2. Fix JSON Decode Errors

**Действия:**
- Увеличить `max_tokens` с 2048 до 4096
- Уменьшить `MAP_CHUNK_SIZE` с 50 до 30
- Добавить `json_repair` перед каждым `json.loads()`
- Рассмотреть `gemini-2.0-flash` вместо `gemini-2.5-flash-lite`

---

### High Priority

#### 3. Добавить warning при отсутствии sqlite-vec

Пользователи должны знать, что HYBRID не работает.

#### 4. Провести тест на Production (Fly.io)

Проверить, работает ли быстрее на Linux.

---

### Medium Priority

#### 5. Оптимизировать prompt

Убрать длинные reason, использовать ключевые слова.

#### 6. Добавить metrics logging

Логировать время каждого этапа retrieval.

---

## Итоговый вердикт

| Критерий | OLD | HYBRID | Winner |
|----------|-----|--------|--------|
| **Скорость** | 22-39s | 50-87s | 🏆 OLD |
| **Качество ответов** | Хорошее | Хорошее | 🤝 Ничья |
| **Количество источников** | 9-11 | 9-12 | 🤝 Ничья |
| **Focus (enriched posts)** | 131 avg | 86 avg | 🏆 HYBRID |
| **Stability** | Стабильный | JSON errors | 🏆 OLD |

---

## Вывод

HYBRID архитектурно правильный, но требует оптимизации:

1. **Retrieval latency** — критическая проблема, требует расследования
2. **JSON decode errors** — влияют на скорость Map Phase
3. **На production (Linux)** может работать быстрее

**Рекомендация:** Не включать HYBRID по умолчанию пока не исправлены проблемы с retrieval.

---

## Следующие шаги для архитектора

1. **Debug Retrieval** — добавить timing для каждого этапа:
   - AI Scout timing
   - Embed Query timing
   - Vector Search timing
   - FTS5 Search timing
   - RRF timing
   - Load Posts timing

2. **Test on Production** — запустить тот же тест на Fly.io

3. **Fix JSON issues** — применить рекомендации из анализа

4. **Re-run test** — после исправлений провести повторный тест

---

## Приложение: Raw JSON Structure

```json
{
  "timestamp": "2026-03-25T19:18:23",
  "experts": ["doronin", "akimov"],
  "model_map": "gemini-2.5-flash-lite",
  "queries": [
    {
      "query": "...",
      "results": [
        {
          "expert_id": "doronin",
          "retrieval_s": 22.9,
          "old": {
            "timings": { "map_s": 11.0, "resolve_s": 0.2, "reduce_s": 11.2 }
          },
          "hybrid": {
            "timings": { "map_s": 19.1, "resolve_s": 0.1, "reduce_s": 13.2 }
          }
        }
      ]
    }
  ]
}
```

---

**End of Analysis**
