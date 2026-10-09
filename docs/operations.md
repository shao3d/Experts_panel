# Experts Panel operations

Status: Active
Last updated: 2026-10-09

Актуальная операторская схема для ИИ-агента. Все команды разработки и
maintenance выполняются из VM checkout `/home/ubuntu/apps/experts-panel/dev`.
Production checkout `app` вручную не редактируется.

## Code release: `выкатывай`

1. В `dev` проверь Git-состояние и нужные тесты.
2. Убедись, что commit содержит только файлы задачи и не содержит секретов,
   SQLite, backups, логов или локальных артефактов.
3. Push `main` запускает `.github/workflows/deploy-oracle.yml`.
4. Workflow обновляет production checkout `app`, собирает `panel` и
   `reddit-proxy`, затем проверяет `/health`.
5. Дождись успешного workflow и проверь production health. Обычный code release
   не меняет production DB.

## Общий CI

Общий CI (`.github/workflows/ci.yml`) независим от deploy workflow. Backend
проверяется на чистом runner с фиктивными ключами и пустой тестовой БД:
`python -m pytest tests -q --tb=short` из `backend`. Обычные Scout-тесты
используют искусственные данные; проверка настоящих fixture keys и поисковых
метрик требует отдельного `SEARCH_PROBE=1` и рабочего dev-корпуса
([поисковый стенд](guides/expert-scout.md)). Не копируй рабочую БД в CI.

Для MCP contract test CI устанавливает Bun 1.4.2 и зависимости `.opencode`
через `npm ci --prefix .opencode --ignore-scripts`. В CI отсутствие Bun —
ошибка, а не незаметный пропуск проверки. Итоговое задание CI завершается
успешно только при успехе всех пяти проверочных заданий.

## Веб-Скаут

Отдельная статическая страница и API публикуются по
[процедуре Веб-Скаута](guides/scout-web.md). Обычный workflow Панели
не перезапускает `scout-web.service` и не публикует GitHub Pages.
Это code release, без обновления production DB.

## Data release: `обнови базу`

Для агентской работы текущий режим анализа задаёт
[drift guide](guides/drift-analysis.md#режим-работы-агента-codex). Полный скрипт
ниже включает вызов OpenCode; в режиме Codex подготовку и смысловую проверку
выполняй под контролем агента, а завершённую staging-БД публикуй upload-only.
Этот режим не повторяет sync, migrations, embeddings и анализ: они должны быть
завершены и проверены до продвижения базы.

Запускай только после явной команды владельца и только на `oracle-work`:

```bash
cd /home/ubuntu/apps/experts-panel/dev
./scripts/update_production_db.sh
```

Для долгой операции используй tmux. Скрипт работает со staging-БД
`dev/backend/data/experts.db`, выполняет sync, migrations, embeddings и drift,
проверяет SQLite, создаёт production backup, атомарно заменяет
`/home/ubuntu/apps/experts-panel/data/experts.db`, перезапускает `panel` и ждёт
успешный `/health`.

Не запускай pipeline из `app`, с Mac или как тест. Не совмещай его с code
release. Перед стартом проверь наличие `dev/backend/.env`, Python 3.11 venv,
staging-БД, свободное место и отсутствие второго DB update процесса. Не выводи
содержимое `.env`.

Перед каждым data release сверь весь staging-каталог VideoHub через read-only
`backend/.venv/bin/python backend/scripts/expert_scout.py videos --json` с
предыдущим выпущенным составом. Проверь приёмку новых или отремонтированных
роликов и соответствие их финальных файлов receipt. Даже scoped visual и
upload-only переносят всю staging-БД: незавершённый соседний онбординг также
попадёт в production. `searchable` подтверждает индексы, но не заменяет
содержательную приёмку.

Безопасная read-only проверка готовности:

```bash
./scripts/update_production_db.sh --check
```

`--check` запускается отдельной командой, без `--scope`. Текущий скрипт
выбирает режим по первому аргументу: `--scope visual --check` запустит
настоящее scoped-обновление, а не проверку.

Режим продвижения уже подготовленной staging-БД:

```bash
DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh
```

Он тоже является production data release и требует явной команды владельца.

Старый wrapper `scripts/deploy_video.sh <json>` импортирует готовый JSON в
staging и затем вызывает этот upload-only режим. Он тоже меняет production DB;
поручение онбордировать видео не разрешает его запуск. Основной VideoHub
workflow разделяет staging-онбординг и data release; описание wrapper — в
[коротком руководстве](guides/add-video.md#legacy-wrapper-production-data-release).

## Scoped data release: `обнови базу по визуалам`

Обновление только группы `visual` (`strangedalle`, `acidcrunch`, `cgevent`,
`neyrograph`, `iideyalogiya`) плюс всё новое, что уже залито в VideoHub staging:

```bash
cd /home/ubuntu/apps/experts-panel/dev
./scripts/update_production_db.sh --scope visual
```

- **Scoped:** Telegram-синк и drift-анализ ограничены этой группой (шаги 2 и 7);
  глобальные шаги 5–6 (drift backfill/cleanup) пропускаются.
- **Глобально:** миграции, эмбеддинги (шаг 4) и промоушен всей staging-БД
  (шаги 8–12). Поэтому новые видео-сегменты VideoHub, уже импортированные в
  staging, попадают в production автоматически — отдельного шага для них нет.
- Группы резолвятся из `backend/src/expert_groups.py` (та же карта, что у
  Панэкса и Скаута); неизвестная группа — ошибка (до изменений в production).
- Это production data release: те же правила, что у `обнови базу` — только по
  явной команде владельца, из VM `dev`, не совмещать с code release.

## Health и rollback

Проверка runtime:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Rollback последнего DB release выполняется только после явной команды владельца:

```bash
cd /home/ubuntu/apps/experts-panel/dev
./scripts/update_production_db.sh --rollback
```

Скрипт сохраняет снимок текущей production DB перед восстановлением backup,
перезапускает `panel` и проверяет health. При любой ошибке остановись, сохрани
логи и доложи владельцу; не импровизируй с ручным копированием SQLite.
