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

## Две операции владельца

### `выкатывай`

Это code release: проверки → commit → push `main` → GitHub Actions → `/health`.
В него автоматически входит backend, frontend и Reddit search. Обычный push не
обновляет production DB. Перед push требуется явная команда владельца.

### `обнови базу`

Это отдельный data release. Только после явной команды владельца следуй
`docs/operations.md` и запускай `scripts/update_production_db.sh` из VM `dev`.
Не объединяй data release с обычным code release и не запускай его для проверки.

Команды `проверь`, `разберись`, `подготовь` не разрешают commit, push, deploy,
restart или изменение production DB. `зафиксируй` разрешает только commit.

## Проектные ограничения

- Не читай, не печатай, не копируй и не коммить секреты, `.env`, ключи, токены,
  базы данных, backups, логи и временные результаты.
- Все запросы к данным эксперта сохраняют изоляцию по `expert_id`.
- Синтез модели не является источником; ответы должны опираться на реальные
  материалы экспертов.
- Для документации начни с `docs/DOCUMENTATION_MAP.md`, затем читай только
  указанный там профильный документ.
- Для UI соблюдай `docs/design-system/refero-say-briefly/UX_INVARIANTS.md`.

## Проверки и отчёт

Запускай минимальные проверки по изменённому scope. Backend-тесты находятся в
`backend/tests/`; frontend-команды — в `frontend/package.json`; Reddit search —
в `services/reddit-proxy/README.md`. Не запускай весь тяжёлый набор автоматически.

В финале сообщи простыми словами: что сделано, что проверено, что не проверено
и требуется ли `выкатывай` или `обнови базу`. Не перекладывай инфраструктурные
шаги на Андрея.
