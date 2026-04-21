# Backend Runtime Cleanup & Diagnostics Plan

**Статус:** Completed Initiative  
**Дата:** 21.04.2026  
**Завершено:** 21.04.2026  
**Контекст:** после миграции runtime с Google AI Studio API key на Vertex AI service account JSON  
**Цель:** убрать legacy-хвосты, усилить health/diagnostics и привести standalone CLI к одному стандарту

---

## Итог выполнения

Инициатива завершена.

Что в итоге сделано:

- введён canonical Vertex runtime client (`vertex_llm_client.py`) и оставлен compatibility shim для legacy imports;
- вычищены stale runtime naming, misleading defaults и legacy test/manual entrypoints;
- `/health` и `/health/live` теперь отдают реальные diagnostics по auth, generation, embeddings и availability;
- standalone CLI scripts переведены на единый bootstrap со стабильной загрузкой `backend/.env`, логированием и нормализацией SQLite/Postgres путей;
- финальный аудит закрыл последние regressions:
  - API startup больше не зависит от `cwd`;
  - health warmup теперь действительно прогревает diagnostics cache.

Этот файл остаётся в репозитории как:

- исторический audit trail;
- карта выполненных работ;
- reference для похожих cleanup-инициатив в будущем.

---

## Зачем это нужно сейчас

После перехода на Vertex AI система уже работает, но кодовая база всё ещё живёт в смешанном состоянии:

- runtime фактически уже Vertex AI;
- названия файлов, классов, логов и части тестов всё ещё говорят "Google AI Studio";
- `/health` проверяет только наличие конфига, а не реальную способность вызвать Gemini/embeddings;
- standalone-скрипты живут в разном стиле: часть грузит `backend/.env`, часть нет; часть настраивает логирование, часть печатает напрямую; retry/backoff для API вызовов не стандартизирован на уровне CLI entrypoints.

Если это не почистить, система будет и дальше работать, но:

- диагнозы будут запаздывать;
- новые изменения будут делать дороже;
- в свежем чате AI-агенту будет труднее понять, что является текущей правдой, а что уже исторический хвост.

---

## Важная граница работ

### Что **нужно** чистить

- runtime / backend terminology, где код уже давно Vertex AI;
- health / diagnostics;
- standalone operational scripts;
- stale tests и ручные legacy-скрипты, которые больше не соответствуют текущей архитектуре.

### Что **не нужно** чистить бездумно

Не все упоминания `AI Studio` — legacy runtime.

Есть документы и operator flows, где AI Studio по-прежнему используется **осознанно как UI-инструмент**, а не как runtime API:

- `docs/guides/video-hub-operator.md`
- `docs/guides/semantic-chunking.md`
- часть research/roadmap материалов по видео

Их не надо “исправлять на Vertex” просто по совпадению слов.  
Сначала проверять: это runtime backend path или внешний операторский UI workflow?

---

## Текущее состояние системы

### 1. Legacy Vertex / AI Studio слой

Фактический runtime уже Vertex AI, но основная совместимая обёртка всё ещё называется:

- `backend/src/services/google_ai_studio_client.py`
- `create_google_ai_studio_client()`
- `GoogleAIStudioError`

И вокруг неё много следов старой терминологии:

- сервисные логи `MapService`, `MediumScoringService`, `TranslationService`, `CommentGroupMapService`, `ReduceService`, `CommentSynthesisService`, `DriftSchedulerService`
- `llm_monitor.py` всё ещё мыслит провайдером `google_ai_studio`
- `backend/src/config.py` держит legacy env `GOOGLE_AI_STUDIO_API_KEY` и legacy printout
- `backend/src/api/main.py:/health` возвращает поля `api_key_configured` и `google_ai_keys_count`, хотя теперь auth — это service account / ADC

Отдельные stale defaults тоже ещё висят:

- `backend/src/services/reddit_synthesis_service.py` содержит `DEFAULT_SYNTHESIS_MODEL = "gemini-2.0-flash"`
- `backend/tests/test_hybrid_llm.py` тестирует старый hybrid/OpenRouter + AI Studio сценарий и ссылается на отсутствующие модули

### 2. Health / Diagnostics

Текущий `/health` в `backend/src/api/main.py`:

- проверяет БД через `SELECT 1`
- проверяет, что auth “вроде настроен”
- **не** делает generation probe
- **не** делает embedding probe
- **не** даёт нормальный status по model availability

То есть сейчас `/health` может быть зелёным даже в ситуации, когда:

- Vertex auth сломан логически, а не конфигурационно;
- generation path не проходит;
- embeddings отдают `429`, `403` или `404 model unavailable`;
- часть моделей из `MODEL_*` недоступна проекту.

Дополнительный operational nuance: текущий `/health` уже используется как контракт не только человеком, но и инфраструктурой/клиентами:

- `backend/Dockerfile`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `frontend/src/services/api.ts`
- `backend/scripts/ab_test_super_passport.py`
- `backend/scripts/benchmark_hybrid_e2e.py`

Поэтому усиление диагностики нельзя делать ценой:

- дорогих live-вызовов на каждый `/health`;
- медленных ответов и flapping health checks;
- несовместимого JSON-формата без синхронного обновления клиентов.

### 3. Standalone CLI scripts

Скрипты уже заметно разрослись и работают в нескольких стилях.

Хорошие примеры:

- `backend/run_drift_service.py`
- `backend/analyze_specific_drift.py`
- `backend/scripts/embed_posts.py`
- `backend/scripts/deep_compare_pipelines.py`
- `backend/scripts/deep_compare_hybrid.py`
- `backend/scripts/eval_reddit_search_v2.py`

Но одновременно есть много entrypoints без общего стандарта:

- не грузят `backend/.env` явно:
  - `backend/apply_postgres_migrations.py`
  - `backend/run_import.py`
  - `backend/sync_to_postgres.py`
  - `backend/scripts/import_video_json.py`
  - большинство `backend/scripts/maintenance/*.py`
  - `backend/scripts/clean_old_posts.py`, `prune_old_posts.py`, `cleanup_orphaned.py`
  - `backend/tools/add_expert.py`
- используют разнобой в логировании:
  - `logging.basicConfig(...)`
  - прямые `print(...)`
  - вообще без настройки логгера
- используют разнобой в bootstrap/runtime:
  - `sys.path.insert(...)` / `sys.path.append(...)`
  - `os.chdir(...)`
  - `load_dotenv()` без явного пути
  - service-level `logging.basicConfig(...)`, который создаёт import-time side effects
- содержат явный legacy/experimental хвост:
  - `backend/test_reddit.py`
  - `backend/test_user_query.py`
  - `backend/test_user_query2.py`
  - `backend/test_reddit_round2.py`
  - `backend/test_reddit_api.py`
  - `backend/test_reddit_api2.py`
  - `backend/test_reddit_comprehensive.py`
  - `backend/tests/test_hybrid_llm.py`

Есть и outlier-скрипты с другим LLM-провайдером:

- `backend/analyze_drift.py` -> OpenRouter path, при этом ждёт `OPENAI_API_KEY`
- `backend/scripts/maintenance/refill_drift_topics.py` -> OpenRouter + `anthropic/claude-sonnet-4.5`

Их нельзя “автоматически считать частью Vertex cleanup”. Для них нужен отдельный выбор:

- переписать на Vertex;
- архивировать как one-off legacy tool;
- или оставить как явно provider-specific script с честной маркировкой.

---

## Workstream 1: Добить Legacy Cleanup

### Цель

Сделать так, чтобы код, логи, env-названия и документация говорили одну правду:

- runtime = Vertex AI
- auth = service account JSON / ADC
- unified client = Vertex-backed compatibility layer

### 1.1. Зафиксировать новый canonical client layer

**Проблема:** runtime уже Vertex AI, но canonical модуль называется `google_ai_studio_client.py`, а экспортируемые типы/фабрики продолжают плодить ложную ментальную модель.

**Что сделать:**

1. Ввести новый canonical модуль, например:
   - `backend/src/services/vertex_llm_client.py`
   или
   - `backend/src/services/gemini_vertex_client.py`
2. Перенести туда:
   - основной клиент
   - error type
   - singleton factory
3. Оставить `google_ai_studio_client.py` как **compatibility shim** на переходный период:
   - с коротким docstring, что модуль deprecated;
   - без собственной логики.
4. В новом слое зафиксировать терминологию:
   - `VertexLLMClient`
   - `VertexLLMError`
   - `get_vertex_llm_client()`

**Какие файлы затронет:**

- `backend/src/services/google_ai_studio_client.py`
- новый `backend/src/services/vertex_llm_client.py`
- все сервисы, которые импортируют `create_google_ai_studio_client`
- `backend/src/services/monitored_client.py`
- `backend/src/services/llm_monitor.py`
- `backend/src/api/simplified_query_endpoint.py`
- `backend/CLAUDE.md`
- `CLAUDE.md`
- `docs/architecture/retry-strategy.md`
- `docs/architecture/pipeline.md`

**Критерий готовности:**

- новые сервисы и docs используют `vertex_llm_client` как каноническое имя;
- старый модуль остаётся только как shim;
- новые логи больше не называют runtime “Google AI Studio”.

### 1.2. Убрать stale defaults и stale comments

**Проблема:** часть default values и docstrings больше не соответствует доступным моделям и текущему runtime.

**Минимум сделать:**

1. Исправить stale defaults:
   - `backend/src/services/reddit_synthesis_service.py`
2. Пройтись по сервисам и убрать misleading comments/logs:
   - `Google AI Studio client initialized`
   - `Calling Google AI Studio`
   - `Google AI Studio API call successful`
3. Обновить provider naming в мониторинге:
   - `google_ai_studio` -> `vertex_ai`
   - убрать мёртвые поля мониторинга, если они больше не участвуют в runtime (`fallback_count` и т.п.)
4. Перестать считать legacy key полноценным runtime path в конфиге:
   - решить, оставляем ли `GOOGLE_AI_STUDIO_API_KEY` только как migration fallback
   - либо удаляем из runtime entirely
5. Синхронизировать terminology и health contract во frontend/backend:
   - `frontend/src/types/api.ts` всё ещё ждёт `openai_configured`
   - backend сейчас возвращает `api_key_configured`
   - финальная схема должна использовать одно честное название (`vertex_auth_configured` / `auth_configured`)
6. Почистить stale API/package metadata:
   - `backend/src/api/main.py:/api/info` всё ещё говорит `GPT-4o-mini powered synthesis`
   - `backend/src/__init__.py` держит старое описание интеграции
   - такие строки не ломают runtime, но ломают ментальную модель системы

**Критерий готовности:**

- grep по `Google AI Studio` в backend-коде показывает только:
  - compatibility shim
  - исторические комментарии, где это явно помечено как legacy
  - осознанные operator/UI docs, не относящиеся к runtime

### 1.3. Почистить stale tests / manual experiments

**Проблема:** часть тестов и ручных скриптов больше не соответствует текущей архитектуре и только вводит в заблуждение.

**Кандидаты на cleanup / archive / rewrite:**

- `backend/tests/test_hybrid_llm.py`
- `backend/test_reddit.py`
- `backend/test_user_query.py`
- `backend/test_user_query2.py`
- `backend/test_reddit_round2.py`
- `backend/test_reddit_api.py`
- `backend/test_reddit_api2.py`
- `backend/test_reddit_comprehensive.py`

**Что сделать:**

1. Разделить файлы на 3 корзины:
   - **переписать** под текущий Vertex runtime
   - **перенести в archive/manual**
   - **удалить**, если дублируют новый harness
2. Базовым replacement считать:
   - `backend/scripts/eval_reddit_search_v2.py`
   - будущие Vertex smoke tests
3. Отдельно инвентаризировать outlier-скрипты на чужом провайдере:
   - `backend/analyze_drift.py`
   - `backend/scripts/maintenance/refill_drift_topics.py`
   и явно решить их судьбу, а не оставлять в полу-рабочем состоянии
4. Не оставлять “тесты”, которые:
   - используют сломанные импорты;
   - хардкодят `os.chdir(...)`;
   - тестируют уже удалённый hybrid/OpenRouter слой.

**Критерий готовности:**

- в `backend/tests/` нет тестов на отсутствующие модули и старый AI Studio/OpenRouter path;
- ручные eval/debug scripts либо переименованы как manual tools, либо убраны.

### 1.4. Свести auth/runtime terminology к одной правде

**Что нужно выровнять:**

- `Vertex auth configured`
- `Vertex runtime`
- `Vertex LLM client`
- `service account / ADC`
- `generation model`
- `embedding model`

**Что перестаём использовать как current truth:**

- `api key configured`
- `google_ai_keys_count`
- `Google AI Studio client`
- `Google AI Studio provider`

**Особая заметка про `config.py`:**

Сейчас `backend/src/config.py` печатает конфиг при импорте модуля.  
Это стоит вынести из import-time side effects в явный runtime/bootstrap слой.

**Критерий готовности:**

- auth/runtime vocabulary одинаковый в:
  - `config.py`
  - `main.py`
  - client layer
  - monitor layer
  - backend docs

---

## Workstream 2: Усилить Health / Diagnostics

### Цель

Получить дешёвую, понятную и правдивую диагностику:

- отдельно быстрый `/health`
- отдельно лёгкий live probe
- понятный status по generation / embeddings / configured models

### 2.1. Ввести отдельный probe service

**Создать:**

- `backend/src/services/health_probe_service.py`

**Роль сервиса:**

- generation probe
- embedding probe
- model availability summary
- TTL-кэш результатов, чтобы не бить Vertex на каждый health-check
- учёт `auth_source` / `project_id` / `location` для diagnostics summary

**Почему отдельный сервис:**

- не размазывать health-логику по `main.py`
- переиспользовать и в API endpoint, и в будущих maintenance CLI

### 2.2. Разделить cheap health и live health

**Предлагаемая схема:**

1. `GET /health`
   - DB check
   - auth config presence
   - cached probe summary
   - быстрый ответ без дорогих сетевых вызовов

2. `GET /health/live`
   - generation probe
   - embedding probe
   - model availability refresh
   - при необходимости ограничить через admin/deployment usage pattern

**Важно:**

Не надо превращать обычный `/health` в дорогой endpoint, который ELB / Fly / Railway будут долбить каждую секунду.

Отдельно важно:

- не ломать существующие Docker/Compose/frontend/benchmark health-потребители;
- если live endpoint раскрывает внутренние причины деградации, auth source и model availability,
  лучше привязать его к уже существующему admin secret pattern.

### 2.3. Добавить generation probe

**Идея:**

- использовать дешёвую generation model:
  - либо `MODEL_MAP`
  - либо отдельный env `HEALTH_GENERATION_MODEL`
- короткий deterministic prompt:
  - `"Respond with OK only."`
- `temperature=0`
- маленький `max_tokens`

**Нужно вернуть в probe result:**

- `ok: true/false`
- `model`
- `latency_ms`
- `error_type`
- `message`

**Важно:**

- generation probe должен использовать ту же runtime-логику маршрутизации модели, что и основной client;
- для `Gemini 3*` это означает `global`, а не `us-central1`, иначе probe даст ложный `404`.

### 2.4. Добавить embedding probe

**Идея:**

- использовать `MODEL_EMBEDDING`
- текст вроде `"health probe"`
- проверить, что:
  - запрос проходит
  - размерность совпадает с `EMBEDDING_DIMENSIONS`

**Нужно вернуть:**

- `ok: true/false`
- `model`
- `dimensions`
- `latency_ms`
- `error_type`
- `message`

### 2.5. Дать понятный status по model availability

**Проблема:** сейчас система не показывает, доступны ли реально configured `MODEL_*`.

**Что сделать:**

1. Собрать список unique generation models из `config.py`
2. Проверять их availability отдельным дешёвым механизмом
3. Возвращать карту вида:

```json
{
  "model_availability": {
    "gemini-2.5-flash-lite": "available",
    "gemini-3-flash-preview": "available",
    "gemini-3.1-pro-preview": "unknown",
    "gemini-embedding-001": "available"
  }
}
```

**Важно:**

- не бить всеми моделями на каждый `/health`;
- availability check должен быть refreshable и кэшируемым.
- в summary должны входить:
  - `project_id`
  - `location`
  - `auth_source`
  - route type модели (`global` vs regional) там, где это влияет на диагностику

### 2.6. Нормализовать health vocabulary

**Нужно заменить поля в API-ответе:**

- `api_key_configured` -> `vertex_auth_configured`
- `google_ai_keys_count` -> убрать или заменить на что-то честное

**Нужны уровни статуса:**

- `healthy`
- `degraded`
- `unhealthy`

И нормальные вложенные секции:

- `database`
- `vertex_auth`
- `generation_probe`
- `embedding_probe`
- `model_availability`

**Совместимость:**

На миграционном этапе может понадобиться временно отдавать и старые поля,
пока не обновлены frontend-типы и вспомогательные скрипты, которые читают `/health`.

### 2.7. Использовать единый error classification

У нас уже есть:

- `backend/src/utils/api_error_detector.py`

Его надо использовать не только для UI-ошибок, но и для diagnostics summary:

- auth error
- model unavailable
- rate limit
- payment/billing
- network/server

### 2.8. Не сломать текущий health contract

Перед внедрением нового health-слоя нужно синхронно обновить и проверить:

- `backend/Dockerfile`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `frontend/src/types/api.ts`
- `frontend/src/services/api.ts`
- `backend/scripts/ab_test_super_passport.py`
- `backend/scripts/benchmark_hybrid_e2e.py`

Нельзя делать так, чтобы после “улучшения диагностики”:

- старые health-check-и начали падать из-за новой схемы ответа;
- фронт стал ожидать одно поле, а backend отдавать другое;
- бенчмарки стали считать backend “unhealthy” из-за live-probe timeout.

### 2.9. Покрыть тестами

**Минимум:**

- unit tests на probe service
- smoke test `/health`
- smoke test `/health/live` с mocked clients

**Критерий готовности Workstream 2:**

- `/health` перестаёт врать про “здоровье” только по наличию env;
- есть отдельный live probe;
- по health ответу видно, что именно сломалось: auth, generation, embeddings, конкретная модель.

---

## Workstream 3: Навести Порядок в Standalone CLI Scripts

### Цель

Сделать единый стандарт для всех standalone entrypoints:

- всегда грузить `backend/.env`
- одинаково настраивать логирование
- одинаково использовать runtime clients
- одинаково переживать transient LLM/embedding сбои

### 3.1. Ввести общий CLI bootstrap слой

**Создать модуль вроде:**

- `backend/src/cli/bootstrap.py`
  или
- `backend/src/utils/cli_runtime.py`

**Что он должен уметь:**

1. `load_backend_env()`
   - всегда грузит `backend/.env` по явному пути
   - не полагается на текущую рабочую директорию
2. `setup_backend_path()`
   - чтобы не было `sys.path.insert('src')` и `os.chdir(...)`
3. `configure_cli_logging(name, level=None, verbose=False)`
4. `require_vertex_runtime()` / `assert_runtime_configured()`
5. helper для `asyncio.run(...)` и uniform exit codes
6. helper для режима запуска:
   - script
   - module
   - cron/manual

### 3.2. Зафиксировать правила для всех новых CLI

Каждый standalone script должен:

1. Явно определить `BACKEND_DIR`
2. Вызвать `load_backend_env(BACKEND_DIR / ".env")`
3. Подключить backend imports единым способом
4. Настроить логирование через общий bootstrap helper
5. Не писать runtime-параметры напрямую в коде, если их можно брать из config / args
6. Не перенастраивать глобальный логгер из service layer при обычном импорте

### 3.3. Мигрировать приоритетные operational scripts

**P0 — operational / production-adjacent:**

- `backend/run_drift_service.py`
- `backend/analyze_specific_drift.py`
- `backend/scripts/embed_posts.py`
- `backend/scripts/import_video_json.py`
- `backend/apply_postgres_migrations.py`
- `backend/sync_to_postgres.py`
- `backend/tools/add_expert.py`

**P1 — engineering / eval scripts:**

- `backend/scripts/deep_compare_pipelines.py`
- `backend/scripts/deep_compare_hybrid.py`
- `backend/scripts/eval_reddit_search_v2.py`
- `backend/scripts/benchmark_hybrid_e2e.py`
- `backend/scripts/profile_hybrid_retrieval.py`
- `backend/scripts/ab_test_super_passport.py`

**P2 — maintenance scripts:**

- `backend/scripts/maintenance/*.py`
- `backend/scripts/clean_old_posts.py`
- `backend/scripts/prune_old_posts.py`
- `backend/scripts/cleanup_orphaned.py`

**Legacy external-provider tools — отдельная корзина:**

- `backend/analyze_drift.py`
- `backend/scripts/maintenance/refill_drift_topics.py`

Для них сначала нужно принять решение:

- `rewrite`
- `archive`
- `leave clearly marked`

### 3.4. Нормализовать логирование CLI

Сейчас у нас смесь:

- `print(...)`
- `logging.basicConfig(...)`
- вообще без настройки

**Нужен один стандарт:**

- общий формат timestamp + level + message
- уважение к `LOG_LEVEL`
- понятные operator-facing summary строки
- без emoji-шума там, где скрипт запускается из cron/CI
- `print(...)` остаётся только там, где это часть явного user-facing или machine-output контракта

**Идея стандарта:**

- machine-readable enough for logs
- human-readable enough for local operator

### 3.5. Не дублировать retry/backoff в каждом скрипте

**Принцип:**

Если скрипт делает LLM / embedding вызовы, он должен по возможности использовать service layer:

- `vertex_llm_client` / compatibility client
- `EmbeddingService`

А не тащить свои raw `requests.post(...)` и свои ad hoc retries.

**Что сделать:**

1. Выделить общий transient-error policy
2. Использовать единый error classification
3. Проверить, что batch/loop scripts:
   - не падают сразу на одном transient `429`
   - не считают retryable attempt как “финальную бизнес-ошибку”
4. Не строить retry поверх retry:
   - если service layer уже ретраит Vertex call,
   - CLI слой должен ретраить только orchestration-step, где это действительно оправдано

**Отдельно про outliers:**

`backend/scripts/maintenance/refill_drift_topics.py` сейчас ходит в OpenRouter напрямую.  
Надо решить отдельно:

- либо оставить его как отдельный provider-specific script, но всё равно привести к bootstrap/logging standard;
- либо убрать / архивировать, если он больше не часть рабочей операционки.

### 3.6. Убрать / архивировать manual debug scripts без статуса

Скрипты, которые не являются ни production tool, ни нормальным тестом, должны перестать жить как “полулегитимные entrypoints”.

**Для каждого такого файла нужен выбор:**

- archive
- delete
- rewrite into proper eval harness

Примеры:

- `backend/test_reddit.py`
- `backend/test_user_query.py`
- `backend/test_user_query2.py`
- `backend/test_reddit_round2.py`
- `backend/test_reddit_api.py`
- `backend/test_reddit_api2.py`
- `backend/test_reddit_comprehensive.py`

### 3.7. Привести import/runtime стиль к одному стандарту

Сейчас в кодовой базе одновременно встречаются:

- `sys.path.insert(0, 'src')`
- `sys.path.append(str(BACKEND_DIR))`
- `sys.path.append(str(Path(...)/'src'))`
- `os.chdir(...)`
- `load_dotenv()` без пути

Нужно выбрать один стандарт:

- либо запуск через `python -m ...` для package-aware CLI;
- либо единый bootstrap helper с минимальным `sys.path` patch;
- но не смесь обоих подходов.

И отдельно убрать import-time logging side effects из:

- `backend/src/services/drift_scheduler_service.py`
- `backend/src/services/sync_orchestrator.py`

### 3.8. Definition of Done для CLI стандарта

Считаем Workstream 3 завершённым, когда:

- у всех production-adjacent CLI есть единый bootstrap;
- все они явно грузят `backend/.env`;
- формат логов одинаковый;
- LLM/embedding scripts используют общий runtime layer;
- “сиротские” manual debug scripts либо архивированы, либо переписаны.

---

## Рекомендуемый порядок выполнения

### Этап A — Terminology / Legacy safety

1. Canonical Vertex client layer
2. Rename/log cleanup
3. Удаление stale defaults
4. Решение по stale tests/manual scripts

### Этап B — Diagnostics

1. `health_probe_service.py`
2. `/health` vs `/health/live`
3. generation probe
4. embedding probe
5. model availability
6. tests

### Этап C — CLI standard

1. bootstrap helper
2. migration P0 scripts
3. migration P1/P2 scripts
4. archive/delete stale manual scripts

---

## Критерий успеха всей инициативы

Инициатива считается завершённой, когда выполнены все три условия:

1. В backend-коде больше нет путаницы между Vertex runtime и старым AI Studio terminology.
2. `/health` и live diagnostics показывают реальную, а не декоративную картину состояния Gemini runtime.
3. Standalone CLI scripts больше не живут как набор разрозненных entrypoints с разным env/logging/retry поведением.

---

## Где искать этот план

Этот файл лежит здесь:

- `docs/roadmap/backend-runtime-cleanup.md`

При возвращении к этой теме в новом чате:

1. сначала перечитать этот roadmap;
2. потом открыть `docs/DOCUMENTATION_MAP.md`;
3. затем идти по workstreams в порядке `Legacy -> Diagnostics -> CLI`.

Итог: это не “список хотелок”, а рабочий план наведения порядка вокруг Vertex runtime, health/diagnostics и standalone CLI после миграции на новый Google path.
