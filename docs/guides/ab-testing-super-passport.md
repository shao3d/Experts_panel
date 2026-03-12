# A/B Testing Guide: Super-Passport Search

Руководство по сравнению старого пайплайна (MapReduce) и нового (FTS5 + AI Scout).

## 📖 Что сравниваем?

| Pipeline | Описание | Параметр API |
|----------|----------|--------------|
| **OLD** | MapReduce — все посты через LLM | `use_super_passport: false` |
| **NEW** | FTS5 + AI Scout — pre-filter через полнотекстовый поиск | `use_super_passport: true` |

## 📦 Требования

- Python 3.9+
- aiohttp: `pip install aiohttp`
- Работающий бэкенд с настроенными API ключами в `.env`

## 📁 Участвующие файлы

| Файл | Назначение |
|------|------------|
| `backend/scripts/ab_test_super_passport.py` | **A/B тест скрипт** |
| `backend/src/services/ai_scout_service.py` | AI Scout — генерация FTS5 запросов |
| `backend/src/services/fts5_retrieval_service.py` | FTS5 retrieval + санитайзер |
| `backend/src/api/simplified_query_endpoint.py` | Main API endpoint |
| `backend/.env` | API ключи (GOOGLE_AI_STUDIO_API_KEY) |

## 🚀 Быстрый старт

```bash
# 1. Запустить бэкенд с API ключами (из корня проекта!)
cd /path/to/Experts_panel/backend
export $(grep -v '^#' .env | xargs) && python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 2. В другом терминале запустить A/B тест (из директории backend!)
cd /path/to/Experts_panel/backend
python3 scripts/ab_test_super_passport.py --queries "Как настраивать RAG?"
```

## 📺 Пример вывода

```
Checking backend at http://localhost:8000...
✓ Backend is healthy

============================================================
A/B Testing: Super-Passport Search
============================================================
Tests: 1
Expert filter: All experts

▶ Test: custom_1
  Query: Как настраивать RAG?
  Running OLD pipeline...
  Running NEW pipeline (FTS5 + Scout)...
  ✓ Recall: 85.0%
  ↓ Latency: -15.0% (5000ms)
  Sources: 12 (old) → 10 (new)

============================================================
Summary
============================================================
Total tests: 1
Successful: 1
Average Recall: 85.0%
Avg Latency Improvement: -15.0%
Good recall (≥80%): 1
Poor recall (<70%): 0

Results exported to: ab_test_results.json
```

## 📋 Опции скрипта

| Опция | Описание | По умолчанию |
|-------|----------|--------------|
| `--url` | URL бэкенда | `http://localhost:8000` |
| `--timeout` | Таймаут запроса (сек) | `120` |
| `--experts` | Фильтр по экспертам (через пробел) | Все эксперты |
| `--queries` | Кастомные запросы (через пробел) | Встроенные тесты |
| `--output` | Выходной JSON файл | `ab_test_results.json` |
| `--list-experts` | Список экспертов и выход | — |

> **Примечание:** Для всех 17 экспертов нужен `--timeout 180` или больше.

## 📊 Примеры использования

### Тест с одним запросом
```bash
python3 scripts/ab_test_super_passport.py --queries "Docker контейнеры"
```

### Тест с несколькими запросами
```bash
python3 scripts/ab_test_super_passport.py \
  --queries "Как настраивать RAG?" "Kubernetes деплой" "C++ best practices"
```

### Тест с фильтром по экспертам
```bash
python3 scripts/ab_test_super_passport.py \
  --queries "LLM промпты" \
  --experts refat llm_under_hood ai_architect
```

### Увеличенный таймаут для больших тестов
```bash
python3 scripts/ab_test_super_passport.py \
  --queries "сложный запрос" \
  --timeout 300
```

### Список доступных экспертов
```bash
python3 scripts/ab_test_super_passport.py --list-experts
```

## 📈 Метрики

| Метрика | Описание | Интерпретация |
|---------|----------|---------------|
| **Recall** | % совпадения `main_sources` между OLD и NEW | ≥80% ✅ | 70-80% △ | <70% 🔴 |
| **Latency** | Время выполнения запроса | Отрицательное = NEW быстрее |
| **Sources** | Количество найденных постов | OLD vs NEW |

### ⚠️ Важно про Recall

**Recall показывает сколько релевантных постов OLD pipeline нашёл NEW pipeline.**

```
OLD нашёл: [post_1, post_2, post_3, post_4, post_5]
NEW нашёл: [post_1, post_3]

Recall = 2/5 = 40%
```

**Низкий Recall (<70%) означает:** FTS5 отсекает релевантные посты из-за ключевых слов.

## 📄 Выходной формат

Результаты сохраняются в `ab_test_results.json`:

```json
{
  "summary": {
    "total_tests": 1,
    "successful_tests": 1,
    "avg_recall": 0.85,
    "avg_latency_improvement_pct": -15.2
  },
  "results": [
    {
      "test_id": "custom_1",
      "query": "Как настраивать RAG?",
      "old": { "latency_ms": 45000 },
      "new": { "latency_ms": 38000 },
      "metrics": {
        "overall_recall": 0.85,
        "latency_improvement_pct": -15.6
      }
    }
  ]
}
```

## 🔧 Встроенные тестовые запросы

Если не указать `--queries`, используются встроенные:

| # | Query | Описание |
|---|-------|----------|
| 1 | `как работать с C++` | Спецсимволы |
| 2 | `настройка кубера в продакшен` | Русский сленг |
| 3 | `как сделать раскатку через пайплайн` | Русский сленг |
| 4 | `C# и .NET разработка` | Множественные спецсимволы |
| 5 | `как использовать Docker контейнеры` | Baseline |

## ⚠️ Траблшутинг

### Backend not responding
```bash
# Проверить health
curl http://localhost:8000/health

# Должен вернуть api_key_configured: true
```

### API keys not configured
```bash
# Перезапустить с env vars
export $(grep -v '^#' .env | xargs) && python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### Timeout
```bash
# Увеличить timeout
python3 scripts/ab_test_super_passport.py --queries "..." --timeout 300
```

### Низкий Recall (<70%)
- Проверить логи: `tail -f backend/data/backend.log | grep -E "(AI Scout|FTS5)"`
- Scout запрос может быть слишком узким
- FTS5 индекс может не содержать нужных терминов

## 📝 Интерпретация результатов

### Хороший результат
```
✓ Recall: 85.0%
↓ Latency: -15.0% (5000ms)
```
→ NEW pipeline работает корректно

### Проблемный результат
```
✗ Recall: 7.7%
↑ Latency: +33.4% (8000ms)
```
→ Scout запрос слишком узкий, нужно улучшить промпт

### Timeout
```
old=True, new=False
new: "Timeout after 180s"
```
→ NEW pipeline медленнее, увеличить timeout или использовать меньше экспертов

## 🏗️ Архитектура A/B теста

```
┌─────────────────────────────────────────────────────────────┐
│                    A/B Test Script                          │
│                                                             │
│  1. OLD: POST /api/v1/query {use_super_passport: false}    │
│     → Все посты эксперта → Map Phase → main_sources        │
│                                                             │
│  2. NEW: POST /api/v1/query {use_super_passport: true}     │
│     → FTS5 pre-filter → Map Phase → main_sources           │
│                                                             │
│  3. Сравнение:                                              │
│     Recall = len(NEW ∩ OLD) / len(OLD)                     │
└─────────────────────────────────────────────────────────────┘
```

### 📊 Data Flow

```
OLD Pipeline (212 posts):
  Load ALL posts → Map (LLM) → 60 relevant → 8 sources

NEW Pipeline (5 posts):
  FTS5 query → 5 posts → Map (LLM) → 2 sources

Recall = 2/8 = 25%
```

## 🔄 Workflow для улучшения Scout

1. **Запустить A/B тест** с целевыми запросами
2. **Проверить Recall** — если <80%, анализировать логи
3. **Найти Scout запрос** в логах: `grep "AI Scout" backend.log`
4. **Улучшить промпт** в `ai_scout_service.py`
5. **Перезапустить бэкенд** и повторить тест
