# Expert Scout (agentic read-only поиск по корпусу)

Status: Active (owner-approved read-only contour)
Last updated: 2026-09-13

Expert Scout — «сырой» канал поиска по корпусу Telegram-экспертов. В отличие
от Панэкса (готовый дайджест) и `reddit-search` (сообщество), скаут сам
итеративно ищет по локальному dev-корпусу, читает первоисточники и приносит
находки с `source_key`, датами и честными пробелами.

## Запуск с Мака

```bash
expert-scout "Какие приёмы сохраняют камеру при video edit? Дай 3-5 источников."
```

Команда глобальная (`~/.local/bin/expert-scout`), работает из любого каталога.
Владелец может вызвать её сам или попросить Codex выполнить её как обычную
bash-команду.

## Как это устроено

```
Mac: ~/.local/bin/expert-scout "вопрос"
  -> SSH (ubuntu@82.70.251.73)
  -> VM: scripts/expert_scout.sh
  -> opencode run --agent expert-scout
  -> backend/scripts/expert_scout.py   (read-only: experts / search / show)
  -> backend/data/experts.db           (mode=ro, query_only=ON)
```

- Агент — `.opencode/agents/expert-scout.md` (модель
  `opencode-go/deepseek-v4.1-flash`, `variant: max`).
- Хелпер — `backend/scripts/expert_scout.py`: гибрид FTS5 + vector (RRF) и
  точное раскрытие источника по `source_key`.
- Ответ возвращается без промежуточных прогресс-нот
  (`scripts/expert_scout_filter.py`).

## Хелпер: команды

```bash
backend/.venv/bin/python backend/scripts/expert_scout.py experts
backend/.venv/bin/python backend/scripts/expert_scout.py search "<запрос>" [--experts a,b] [--recent-days N] [--limit N] [--no-vector] [--json]
backend/.venv/bin/python backend/scripts/expert_scout.py show <expert:message_id> [...] [--comments-limit N] [--json]
```

## Границы и безопасность

- **Только чтение**: `mode=ro` + `PRAGMA query_only=ON`; скаут не пишет в
  корпус и не меняет репозиторий.
- **Только dev-корпус** `backend/data/experts.db`; production DB не трогается.
- Изоляция по `expert_id` сохраняется; возвращаются только реальные материалы
  экспертов.
- Секреты, `.env`, токены не печатаются; `.env` читается только приложением для
  эмбеддингов.
- Медиа не открывается. Это разрешение — узкое исключение к правилу
  «не читать базы данных» (см. `AGENTS.md`).

## Сравнение с Panex (n=1, 2026-09-13)

На вопросе «Kling элементы/Reference» (acidcrunch + doronin):

| | Panex `expert_digest` | Expert Scout |
|---|---|---|
| Время | 32 с | 35 с |
| Форма | артефакт ~1 МБ, 117 source_keys | компактный текст, 4+ источника |
| Релевантность | на узком эксперте ок; на широком — 61 сигнал, 2–3 по делу | по делу, с цитатами |
| Пробелы | частично | явный блок + список запросов |

Вывод: для точной техники/цитаты — скаут; для быстрого структурированного
обзора по узкому эксперту — Panex. Это одно наблюдение, не статистика.

## Когда использовать

| Канал | Что даёт |
|---|---|
| `expert-scout` | Сырые первоисточники с цитатами, итеративный поиск по корпусу |
| `reddit-search` | Мнение сообщества, свежие обсуждения |
| Панэкс (`panex ask`) | Готовый сжатый дайджест по выбранным экспертам |

Scout не заменяет два других канала и не выдаёт мнение практиков за истину.

## Восстановление Mac-shim

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/expert-scout <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 || -z "${1// }" ]]; then
  echo "usage: expert-scout \"<question>\"" >&2
  exit 2
fi
REMOTE="${EXPERT_SCOUT_REMOTE:-ubuntu@82.70.251.73}"
REPO="${EXPERT_SCOUT_REPO:-/home/ubuntu/apps/experts-panel/dev}"
Q=$(printf '%s' "$*" | base64 | tr -d '\n')
exec ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=10 \
  "$REMOTE" \
  "cd '$REPO' && ./scripts/expert_scout.sh \"\$(printf '%s' '$Q' | base64 -d)\""
EOF
chmod +x ~/.local/bin/expert-scout
```

## Диагностика

- «opencode not found» / «backend python not found» — проверить
  `~/.opencode/bin/opencode` и `backend/.venv` на VM.
- «Permission denied» — проверить SSH-ключ Mac → VM.
- Пустой ответ — агент не нашёл сигнала; вывод всё равно содержит список
  запросов и пробелы.
