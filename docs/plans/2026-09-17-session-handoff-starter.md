# Session Handoff Starter (2026-09-17)

**Дата:** 2026-09-17
**Тема:** состояние проекта после VideoHub-ревью; что делать дальше
**Статус:** VideoHub review pass выкачен в прод, блокеров кода нет

> Handoff-промт для нового чата. Сначала прочитай `AGENTS.md`, затем
> `docs/DOCUMENTATION_MAP.md`, затем профильные доки из §3.

---

## 1. Где мы находимся (проверено 2026-09-17)

Experts Panel — мультиэкспертная AI-панель по Telegram-корпусам (backend
Map/Resolve/Reduce + SSE, Reddit-сайдкар, VideoHub, Панэкс, Expert Scout).

- **Последний коммит:** `614abc4` — VideoHub review pass: локализованный
  фолбэк «не найдено», дедуп Map-scores, именованные INSERT/UPDATE-параметры
  в импорте, `datetime.now(UTC)`, доки + тесты.
- **Выкат:** CI/CD и Deploy to Oracle — success; production `/health` здоров
  (`https://expa.beyondhorizon.dev/health`). Data release не требовался.
- **VideoHub** (SSOT: `docs/architecture/video-hub-service.md`):
  - operating mode: НЕ в панели и НЕ в Панэксе (query-time ветка dormant);
    поиск по видео — только через Expert Scout (deep-links с таймкодами);
  - корпус: 1 видео / 11 сегментов (Youri van Hofwegen, Seedance 2.5);
  - ingest автоматический: ASR + адаптивные кадры + LLM-пасс по чанкам
    (`ingest_video.py` → `import_video_json.py` → `embed_posts.py`).
- **Рабочее дерево:** чужие незакоммиченные изменения — admission-строка в
  `docs/DOCUMENTATION_MAP.md` (handoff-строка добавлена вместе с этим доком)
  и untracked `backend/scripts/benchmark_reddit_synthesis_models.py`. Их не
  трогать и не коммитить вместе со своими.

## 2. Открытые задачи (кандидаты на работу)

VideoHub (`docs/roadmap/video-hub-scaling.md`, таблица приоритетов):

- **N6**: citation verification для видео-ответа — включить, когда видео
  вернётся в панель (сейчас `[post:ID]` из видео-синтеза не верифицируется);
- **P3**: retry/backoff query-time (не делали сознательно — ветка dormant);
- **P2**: chunking в Video Map (актуально при ~100+ сегментах);
- N1 `context_bridge`, N3 Flash vs Pro, N4 Medium Scoring, N5 PostCard parsing.

Кросс-проектные (`docs/roadmap/2026-09-system-review.md`):

- **B.3 (владелец):** `reddit-search` с VM падает — `AGENT_CONTEXT_API_TOKEN
  is required`; `--doctor`: `token_configured: false`. Нужен Reddit-only токен
  для VM (или запуск с Мака, где Keychain-токен работает). Обратный туннель
  (127.0.0.1:2222) открыт, но VM→Mac SSH — `Permission denied (publickey)`.
- **A.3** golden-set eval harness — следующий кандидат по обзору;
  **A.4** demo corpus вернёт скипнутые тесты; **B.4** log-batch — час работы.

Возможная следующая VideoHub-тема: залить следующее видео. Кандидаты из
ресёрча каналов (2026-09-17): **Marin Method** (Seedance-консистентность,
тематически ближе всего), Theoretically Media, Curious Refuge. Playbook:
`docs/guides/video-hub-operator.md`, Phase 0.

## 3. Что читать (порядок)

1. `AGENTS.md` — правила проекта, owner-команды, запреты.
2. `docs/DOCUMENTATION_MAP.md` — навигация по всем докам.
3. `docs/architecture/video-hub-service.md` — VideoHub SSOT.
4. `docs/roadmap/video-hub-scaling.md` — статусы и N-пункты.
5. `docs/archive/2026-09-16-video-hub-starter.md` (§9–10 — история ревью).
6. `docs/guides/video-hub-operator.md` — ingest-playbook.

## 4. Среда и грабли

- Работай только в `/home/ubuntu/apps/experts-panel/dev` (VM). Production
  checkout `~/apps/experts-panel/app` не трогать.
- Секреты/БД/логи не читать и не коммитить; Expert Scout — единственное
  sanctioned read-only исключение по dev-корпусу.
- YouTube блокирует IP VM: медиа качается на Mac через обратный туннель
  (со стороны VM виден как `127.0.0.1:2222`); ASR запускать через
  `/usr/bin/python3.11` (в `backend/.venv` нет faster-whisper).
- Долгие операции (ASR, data release) — в `tmux`/`setsid`.
- Owner-команды: `выкатывай` (code release), `обнови базу` (data release),
  `обнови базу по визуалам` (scoped visual), `зафиксируй` (только commit).

## 5. Первые шаги нового агента

1. `git status` + `git log --oneline -5` — состояние и последние коммиты.
2. Убедись, что чужие изменения из §1 на месте и не тронуты.
3. `reddit-search --doctor` — если токен всё ещё не сконфигурирован, это
   техническая ошибка (exit 1), а не «ничего не найдено».
4. Спроси владельца, что делаем; варианты — в §2.
