# Experts Panel: правила для ИИ-агентов

Андрей всегда запускает агента из корня проекта. Не проси его выполнять Git,
Docker, SSH или диагностические команды: технические проверки делает агент.

## Язык общения: только русский или английский

Вся коммуникация агента — ответы пользователю, прогресс-ноты между вызовами
инструментов, комментарии в коде, commit message и документация — пишется
**только на русском или на английском**. Китайский, японский, корейский и
любые другие языки запрещены, включая короткие технические заметки и
автоматические сообщения о прогрессе. Если заметил, что написал на другом
языке, немедленно исправь текст и продолжай на русском или английском.

(Language rule: All agent communication — user-facing replies, progress notes
between tool calls, code comments, commit messages and documentation — must
be written **only in Russian or English**. Chinese, Japanese, Korean and any
other language are forbidden, including short technical notes and automatic
progress messages. If you notice you wrote in another language, fix the text
immediately and continue in Russian or English.)

## Reddit Search (обязательный механизм)

Когда пользователь просит поискать что-то на Reddit, узнать мнение
практикующего сообщества или проверить обсуждения — используй ТОЛЬКО
официальный механизм Experts Panel, команду:

```bash
reddit-search "<вопрос пользователя>"          # обычный поиск
reddit-search "<вопрос>" --recent              # свежие данные (последние темы)
reddit-search --json "<вопрос>"                # машиночитаемый вывод
reddit-search --doctor                         # проверка доступности API
```

Команда глобальная (`~/.local/bin/reddit-search`), работает из любой
dиректории. Правила интерпретации:

- `status: completed` — покажи синтез и 2–5 реальных Reddit-ссылок из вывода;
- `status: abstained` — честно скажи, что надёжных обсуждений не найдено;
  НЕ дополняй ответ выдумками или общими знаниями;
- exit code 1 — техническая ошибка (нет токена, API недоступен, таймаут);
  сообщи о ней как о технической проблеме, не выдавай за отсутствие
  результатов.

Запрещено: вызывать `reddit-proxy` напрямую, запускать pipeline локально,
читать/печатать/копировать токен `AGENT_CONTEXT_API_TOKEN`. SSOT:
`docs/architecture/reddit-service.md` (разделы "Agent-facing API",
"CLI-граница").

(Reddit Search rule: when the user asks to search Reddit or gather community
sentiment, always run the global `reddit-search` command above — never call
`reddit-proxy` directly, never run the pipeline locally, never print the
`AGENT_CONTEXT_API_TOKEN` token. Report `completed` with real links, report
`abstained` honestly without inventing content, and report exit code 1 as a
technical failure.)

## Expert Scout (agentic read-only поиск по корпусу)

Владелец явно разрешил отдельный контур: агент-«скаут» может **только читать**
локальный dev-корпус `backend/data/experts.db` через
`backend/scripts/expert_scout.py` (открытие `mode=ro`, `PRAGMA query_only=ON`,
изоляция по `expert_id`, без записи, копирования и печати секретов). Это узкое
исключение к запрету на чтение баз данных из раздела ниже — только для скаута.

Запуск с Мака одной командой:

```bash
expert-scout "<вопрос>"
```

Фраза «задействуй Скаута …» маршрутизируется на неё глобальным скиллом
`.codex/skills/expert-scout/` (установка: `scripts/install_expert_scout_skill.sh`,
на Маке — с `--with-shim`).

Под капотом: Mac-shim (`~/.local/bin/expert-scout`) → SSH на VM →
`scripts/expert_scout.sh` → агент `expert-scout` в opencode → read-only хелпер.
У агента нет shell (bash запрещён полностью): единственный инструмент —
read-only `scout` из плагина `.opencode/plugins/expert-scout-tools.ts`,
который запускает хелпер argv-массивом без shell, поэтому инъекции команд
через аргументы невозможны. Агент сам перебирает фасеты и anti-pattern
формулировки, читает первоисточники через `show` и возвращает находки с
`source_key` и честные пробелы. Полное описание и границы —
`docs/guides/expert-scout.md`.

Запрещено: писать в корпус, трогать production DB, копировать/выгружать БД,
выводить секреты. Scout не заменяет `reddit-search` (сообщество) и Панэкс
(готовый дайджест); это третий, «сырой» канал.

(Expert Scout rule: the owner authorized a narrow read-only exception — the
scout agent may read the local dev corpus through `backend/scripts/expert_scout.py`
only. The agent has no shell access: its single tool is the read-only `scout`
plugin tool (`.opencode/plugins/expert-scout-tools.ts`) which spawns the
helper with an argv array, no shell. Never write to the corpus, never touch
the production DB, never copy or dump the database, never print secrets. Run
it from the Mac as `expert-scout "<question>"`.)

## Единственное рабочее место

- На VM работай только в `/home/ubuntu/apps/experts-panel/dev`.
- На Mac запасной checkout:
  `/Users/andreysazonov/Documents/Projects/Experts_panel`.
- `/home/ubuntu/apps/experts-panel/app` — production checkout GitHub Actions.
  Не редактируй его и не запускай там ИИ-кодеров или maintenance-команды.
- GitHub `shao3d/Experts_panel`, ветка `main` — источник истины для commits.
- В один момент времени пишет только один checkout: VM `dev` или Mac.

Перед работой сам проверь Git-состояние. Не трогай незнакомые изменения и не
используй `reset --hard`, `clean`, rebase общей `main` или force-push.

## Операции владельца

### `выкатывай`

Это code release: проверки → commit → push `main` → GitHub Actions → `/health`.
В него автоматически входит backend, frontend и Reddit search. Обычный push не
обновляет production DB. Перед push требуется явная команда владельца.

### `обнови базу`

Это отдельный data release. Только после явной команды владельца следуй
`docs/operations.md` и запускай `scripts/update_production_db.sh` из VM `dev`.
Не объединяй data release с обычным code release и не запускай его для проверки.

### `обнови базу по визуалам`

Это scoped data release: обновляются только эксперты группы `visual`
(`strangedalle`, `acidcrunch`, `cgevent`, `neyrograph`, `iideyalogiya`) плюс
промоутится всё новое, что уже залито в VideoHub в staging. Запускай только
после явной команды владельца:

```bash
./scripts/update_production_db.sh --scope visual
```

Sync и drift идут только по этой группе; миграции, эмбеддинги и промоушен БД
остаются глобальными, поэтому новые видео-сегменты VideoHub попадают в
production автоматически. Детали — `docs/operations.md`.

Команды `проверь`, `разберись`, `подготовь` не разрешают commit, push, deploy,
restart или изменение production DB. `зафиксируй` разрешает только commit.

## Проектные ограничения

- Не читай, не печатай, не копируй и не коммить секреты, `.env`, ключи, токены,
  базы данных, backups, логи и временные результаты. Единственное исключение —
  read-only Expert Scout по dev-корпусу (см. раздел «Expert Scout» выше).
- Все запросы к данным эксперта сохраняют изоляцию по `expert_id`.
- Синтез модели не является источником; ответы должны опираться на реальные
  материалы экспертов.
- Для документации действуй по разделу «Документация» ниже.
- Для UI соблюдай `docs/design-system/refero-say-briefly/UX_INVARIANTS.md`.

## Документация

Навигация: начинай с `docs/DOCUMENTATION_MAP.md` — там таблица маршрутов
«вопрос → документ», семантика папок и Update Checklist «изменение → что
править». Читай только профильный SSOT из маршрута, не весь `docs/`.

Конвенции ведения документации:

- **SSOT-принцип**: один факт живёт в одном документе. Остальные ссылаются на
  него, а не дублируют содержимое. Меняешь факт — правишь его SSOT и
  проходишься по Update Checklist карты.
- **Шапка**: у каждого активного документа — `Status` и `Last updated`
  (YYYY-MM-DD). Обновил документ — обнови дату.
- **Папки**: `architecture/` — текущее системное поведение (SSOT);
  `guides/` — операторские процедуры; `operations.md` — релизные операции;
  `plans/` — только активные handoff/starter с датой в имени; `roadmap/` —
  активные планы и обзоры; `quality/` — рубрики и датированные
  dogfood-снапшоты; `concepts/` — черновики идей (не runtime);
  `research/`, `session-logs/` — evidence, не SSOT; `archive/` — история.
- **Архив вместо удаления**: устаревшее не удаляй — переноси в
  `docs/archive/` через `git mv`, обнови все ссылки (`rg` по имени файла по
  всему репо, включая тесты и agent-файлы) и маршрут в карте. Завершённый
  или вытесненный starter из `plans/` сразу уезжает в архив.
- **Журнал ≠ текущее состояние**: записи вида AND-*, датированные dogfood и
  «Done»-логи внутри документов — история. Факты об инфраструктуре (где прод,
  как деплоится, где лежит БД) сверяй с кодом, `.github/workflows/` и
  `docs/operations.md`, а не с журнальными записями.
- **Новый документ** без строки в карте считается потерянным: добавляй
  маршрут или строку индекса в `docs/DOCUMENTATION_MAP.md` сразу.

## Проверки и отчёт

Запускай минимальные проверки по изменённому scope. Backend-тесты находятся в
`backend/tests/`; frontend-команды — в `frontend/package.json`; Reddit search —
в `services/reddit-proxy/README.md`. Не запускай весь тяжёлый набор автоматически.

В финале сообщи простыми словами: что сделано, что проверено, что не проверено
и требуется ли `выкатывай` или `обнови базу`. Не перекладывай инфраструктурные
шаги на Андрея.
