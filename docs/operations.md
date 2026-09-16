# Experts Panel operations

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

## Data release: `обнови базу`

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

Безопасная read-only проверка готовности:

```bash
./scripts/update_production_db.sh --check
```

Режим продвижения уже подготовленной staging-БД:

```bash
DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh
```

Он тоже является production data release и требует явной команды владельца.

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
