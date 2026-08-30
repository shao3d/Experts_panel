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
