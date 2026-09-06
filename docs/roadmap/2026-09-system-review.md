# Обзор системы и roadmap: ценностные фичи + техздоровье (2026-09)

Status: Active roadmap
Last updated: 2026-09-06
Origin: большой обзор системы в Mac-сессии 05–06.09.2026 (птичий полёт по докам,
код-dig backend/frontend/reddit-proxy, 4 живых Reddit-поиска через `reddit-search`,
2 веб-поиска). Документ фиксирует выводы обзора и текущий статус каждого пункта.
Это roadmap, а не архитектурная спецификация: текущее поведение системы — в
`docs/architecture/*`.

---

## Метод и источники

- Полный обход документации (`docs/DOCUMENTATION_MAP.md` как навигация), ключевых
  SSOT-доков и кода (оркестратор, retrieval, reddit-сайдкар, тесты, CI).
- Четыре Reddit-поиска официальным `reddit-search` (3 `completed`, 1 честный
  `abstained`) + два веб-поиска для триангуляции.
- Ключевой вывод ресёрча: главная рыночная боль ИИ-поисковиков —
  **«post-hoc citation architecture»** (модель сначала отвечает, потом
  подбирает ссылки; источники выдумываются или не содержат утверждения), и
  сообщество советует «перепроверяй всё вручную». Вторая боль — отсутствие
  честного отказа («I don't know paradox»: бенчмарки награждают уверенный
  неправильный ответ сильнее честного «не знаю»).

Ключевые источники:

- [I tested every Reddit marketing tool in 2026 (r/microsaas)](https://reddit.com/r/microsaas/comments/1qw6hpw/i_tested_every_reddit_marketing_tool_in_2026_so/) — рынок
  инструментов мониторинга Reddit после закрытия GummySearch: intent scoring,
  LLM-ready вывод, алерты.
- [I'm perplexed by perplexity citation (r/perplexity_ai)](https://www.reddit.com/r/perplexity_ai/comments/1tk8f9b/im_perplexed_by_perplexity_citation/) и
  [References incorrect (r/perplexity_ai)](https://www.reddit.com/r/perplexity_ai/comments/1dh3es0/references_incorrect/) — выдуманные
  цитаты и несоответствие источников утверждениям.
- [Built 6 SaaS and got 0 customers (r/indiehackers)](https://reddit.com/r/indiehackers/comments/1rw64vw/built_6_saas_and_got_0_customers_heres_how/) и
  [Validate in 15 minutes (r/SaaS)](https://reddit.com/r/SaaS/comments/1rpqs6t/how_to_validate_your_startup_idea_in_15_minutes/) —
  агентные ресёрч-workflow, валидация = готовность платить.
- [Open-source company at $14.2k MRR (r/indiehackers)](https://reddit.com/r/indiehackers/comments/1p2x3gf/i_did_it_my_opensource_company_now_makes_142k/) —
  OSS как дистрибуция для соло-разработчика.
- Синтез по жалобам на Perplexity/ChatGPT (получен `reddit-search`): post-hoc
  citations, «synthetic loop», benchmarks против честного abstain.

---

## A. Ценностные фичи (по убыванию ценности для портфолио)

| # | Фича | Статус |
|---|------|--------|
| 1 | Verified Citations (бейдж «цитаты проверены») | ✅ Сделано (03b1e4f) |
| 2 | Evidence Viewer (подсветка улики в посте) | ✅ Сделано (03b1e4f) |
| 3 | Golden-set eval harness с LLM-судьёй и baseline-diff | ⬜ Не начато |
| 4 | Демо-корпус: `scripts/seed_demo.py` | ⬜ Не начато |
| 5 | README-упаковка: скриншоты/GIF, диаграммы, example-запросы | 🟡 Частично |
| 6 | Feedback 👍/👎 → eval-сет | ⬜ Не начато |
| 7 | Saved Searches + Telegram-дайджест | ⬜ Не начато |
| 8 | Hacker News сайдкар (Algolia API) | ⬜ Не начато |
| 9 | Рефакторинг оркестратора | ⬜ По остаточному принципу |

### 1–2. Verified Citations + Evidence Viewer — ✅ сделано

Раньше: пользователь должен был верить, что `[post:ID]` подтверждает утверждение.
Теперь каждая экспертная карточка несёт серверную проверку:

- `CitationVerificationService` разбивает ответ на утверждения с цитатами,
  лексический слой (RU/EN стоп-слова, лёгкий стемминг, числа как улики) считает
  поддержку, дешёвый LLM-судья (`MODEL_ANALYSIS`, один батч) уточняет по смыслу.
- Слабейший вердикт побеждает на пост — отчёт не приукрашивает. Fail-open:
  любая ошибка → бейджа просто нет.
- Отчёт несёт **word-level evidence**: плотнейший кластер слов автора в тексте
  поста (офсеты + фрагмент + совпавшие формы). Клик по цитате открывает пост с
  подсвеченной уликой (substring-якорь, на переводах тихо деградирует).
- Проверка запускается параллельно пост-фазам пайплайна и валидирует
  до-переводной ответ; вердикты ключуются по `telegram_message_id`, поэтому
  валидны для переведённого текста.

Код: `backend/src/services/citation_verification_service.py`,
`backend/tests/test_citation_verification.py`, фаза 5b в
`docs/architecture/pipeline.md`.

### 3. Golden-set eval harness — ⬜ следующий кандидат

Уже есть половинки: `eval_reddit_search_v2.py` (12 фиксированных запросов без
суждений о релевантности), `panex_quality_eval.py` (сценарии + рубрика),
несмерженные `compare_map_models.py` и `benchmark_reddit_synthesis_models.py`.
Цель: золотой набор вопросов → релевант-суждения → LLM-as-judge по рубрикам из
`docs/quality/` → сохранённые baseline → `--diff` «стало лучше/хуже». Превращает
«мне кажется лучше» в «score вырос с X до Y».

### 4. Демо-корпус — ⬜

Главный барьер для ревьюера репозитория: «import your own source data» = почти
никто не запустит. `seed_demo.py` с 2–3 синтетическими экспертами — и запуск за
5 минут. (Заодно вернёт в CI скипы `test_experts_api` и
`test_agent_context_custom_accepts_database_expert_outside_static_groups`, которые
сейчас пропускаются на пустой CI-БД.)

### 5. README-упаковка — 🟡

Фичевые bullets актуализированы (verified citations описаны). Осталось:
скриншоты UI, GIF «вопрос → SSE-прогресс → ответ с бейджем → клик → подсветка»,
рендер диаграмм (заготовки лежат в локальной `review/`, в git не входят), кнопки
«Try example query», реплеящие сохранённые `query_results/*.json`.

### 6. Feedback-петля 👍/👎 — ⬜

Две кнопки + таблица + экспорт в golden set из п.3. Реальный сигнал качества
вместо догфуда.

### 7. Saved Searches + Telegram-дайджест — ⬜

Спрос подтверждён рынком (волна GummySearch-альтернатив): людям нужен
мониторинг, не разовый поиск. Инфраструктура уже есть: telegram_fetcher,
systemd-таймеры, поиск V2. «Сохранённый запрос → дайджест новых обсуждений в
TG-боте».

### 8. HN-сайдкар — ⬜

Algolia HN Search API: бесплатный, без auth. Обобщает Reddit-сайдкар до паттерна
«community evidence router» — демонстрирует приём, а не интеграцию.

### 9. Оркестратор — ⬜

`simplified_query_endpoint.py` ~2300 строк. Полезно для поддерживаемости,
портфолио-эффект минимальный. Делать маленькими шагами в последнюю очередь.

---

## B. Технические болячки (по убыванию критичности)

| # | Болячка | Статус |
|---|---------|--------|
| 1 | Публичный `/api/v1/query` без rate-limit/budget | ✅ Исправлено (9932db5) |
| 2 | CI не гоняет тесты, type-check глотался | ✅ Исправлено (9932db5, cc9db68) |
| 3 | Токен в логах чат-агентов на VM; Mac без токена | 🟡 Открыто (владелец) |
| 4 | `POST /api/v1/log-batch` без auth и лимитов | ⬜ Открыто |
| 5 | fly.dev-остатки в операционных скриптах | ⬜ Открыто |
| 6 | Core-пайплайн без unit-тестов | 🟡 Частично |
| 7 | Монолитные модули | ⬜ Открыто (низкий) |
| 8 | Локальный мусор на Mac | ⬜ Косметика |

### 1. Rate-limit + бюджет-гард — ✅ исправлено

Per-IP sliding-window (12/час, `QUERY_RATE_LIMIT_PER_HOUR`) + глобальный дневной
бюджет (200/сутки UTC, `DAILY_QUERY_BUDGET`), in-process, 429 c `Retry-After`
(глобальный обработчик больше не теряет заголовки исключений). X-Forwarded-For
доверяется только от loopback/private пиров — прямой пир не может ротировать
личность. Код: `src/services/query_rate_limit_service.py`. Счётчики сбрасываются
при рестарте.

### 2. Честный CI — ✅ исправлено

`ci.yml` теперь реально гоняет backend pytest (336+) и frontend vitest (62+),
type-check больше не глотается через `|| echo`. Попутно вылечены 9 устаревших
тестов (fly.dev-ассерты после миграции на `expa.beyondhorizon.dev`,
переименованная `parse_posts_and_comments`, герметичные health-тесты) и 3
теста, неявно требовавших наполненную БД/venv, переведены на явный `pytest.skip`
— они снова включатся, когда появится демо-корпус (см. A.4).

### 3. Секрет-гигиена — 🟡 открыто (владелец)

`AGENT_CONTEXT_API_TOKEN` засветился в логах чат-агентов на VM
(`~/.config/manicode/projects/dev/chats/*`); ротация требует действий владельца
(env на VM + перевыдача). Отдельно: на Mac `reddit-search` нерабочий (токен не
сконфигурирован; `--doctor` → `token_configured: false`) — настройка по
`docs/guides/reddit-search-mac-setup.md`. После перехода на VM-first workflow
(см. ниже) мак-токен стал менее актуальным.

### 4. `/api/v1/log-batch` — ⬜

Принимает произвольные логи с `data: Any` без auth и лимитов — спам-вектор на
диск. Лечение: кап на размер батча/message, per-IP throttle. Час работы.

### 5. fly.dev-остатки — ⬜

Runtime-код чист, но операционные скрипты стучатся в мёртвый эндпоинт:
`backend/scripts/panex_quality_eval.py`, `backend/scripts/agent_context_live_smoke.py`,
`backend/scripts/benchmark_hybrid_e2e.py` (+ их тесты). Поправить заодно с A.3 —
эти скрипты станут основой eval-харнесса.

### 6. Покрытие core-пайплайна — 🟡

Тесты теперь гоняются в CI (главный шаг), но map/reduce/оркестратор и
RRF/freshness без прямых unit-тестов. Наращивать по одному на баг/фичу.

### 7–8. Монолиты и локальный мусор — ⬜

`simplified_query_endpoint.py` (~2.3k), `reddit_enhanced_service.py` (~1.9k),
`agent_context_service.py` (~1.7k). На Mac: `backend/backup_flyio_*.db`,
`*.log`, `telegram_fetcher.session`, `README.md.bak` — git-игнорируется,
просто почистить для порядка.

---

## C. Смена workflow (2026-09-06)

Разработка переехала на **ZCode Remote Development**: агентский чат живёт на VM
(`/home/ubuntu/apps/experts-panel/dev`, сервер в `~/.zcode/server`), Mac-приложение
остаётся пультом, Mac-checkout — read-only. Handoff между сессиями — только через
GitHub `main` (источник истины по AGENTS.md). VM совмещает прод и агентскую
работу — тяжёлые прогоны делить бережно.

## D. Порядок работ (рекомендация)

1. A.3 eval harness (заодно закрывает B.5 — починка fly.dev-скриптов как первый шаг).
2. A.4 seed-демо (вернёт в CI скипнутые тесты) + A.5 README-упаковка — дёшево, множит ценность.
3. B.4 log-batch — час работы.
4. A.6 feedback-петля → кормит A.3.
5. A.7 TG-дайджест, A.8 HN-сайдкар — по настроению.
