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

## Глобальный скилл (Codex + opencode)

Чтобы фраза «задействуй Скаута ...» работала в любой сессии, установлен скилл
`expert-scout`, который маршрутизирует такие запросы на команду:
триггеры — «Скаут», «expert-scout», «задействуй Скаута», «сырой поиск по
экспертам». «По визуалам» скилл передаёт как `группа visual` внутри вопроса:
группы резолвятся из канонической карты `backend/src/expert_groups.py`, поэтому
при добавлении эксперта в группу скилл править не нужно.

Установка (на Маке — для Codex, на VM — для opencode):

```bash
scripts/install_expert_scout_skill.sh              # только скиллы
scripts/install_expert_scout_skill.sh --with-shim  # + Mac-мостик
```

Исходник скилла — `.codex/skills/expert-scout/`; глобально ставится в
`~/.codex/skills/expert-scout/` (Codex) и
`~/.config/opencode/skills/expert-scout/` (opencode).

## Как это устроено

```
Mac: ~/.local/bin/expert-scout "вопрос"
  -> SSH (ubuntu@82.70.251.73)
  -> VM: scripts/expert_scout.sh
  -> opencode run --agent expert-scout
  -> plugin tool `scout` (argv-массив, без shell)
  -> backend/scripts/expert_scout.py   (read-only: experts / search / show)
  -> backend/data/experts.db           (mode=ro, query_only=ON)
```

- Агент — `.opencode/agents/expert-scout.md` (модель
  `opencode-go/deepseek-v4.1-flash`, `variant: max`). Shell ему недоступен
  (bash запрещён полностью): единственный инструмент — read-only `scout` из
  плагина `.opencode/plugins/expert-scout-tools.ts`, который запускает хелпер
  через argv-массив без shell, поэтому подстановки `$( )`/backticks в
  аргументах инертны (проверено пробой 2026-09-13).
- Хелпер — `backend/scripts/expert_scout.py`: гибрид FTS5 + vector
  (soft-freshness + RRF, как в `HybridRetrievalService`) и точное раскрытие
  источника по `source_key` с раздельной выборкой авторских комментариев.
- Ответ возвращается без промежуточных прогресс-нот
  (`scripts/expert_scout_filter.py`); если агент не выдал финальный ответ,
  fallback-нарратив помечается явным `# WARNING`.

## Прогон: таймаут и артефакты

Обёртка `scripts/expert_scout.sh`:

- hard-timeout на весь агентный прогон: переменная `EXPERT_SCOUT_TIMEOUT`
  (секунд, по умолчанию 300);
- артефакты каждого прогона в `output/scout_runs/<timestamp>/`:
  `question.txt`, `events.jsonl` (сырой поток opencode), `answer.md`
  (финальный ответ), `meta.txt` (вопрос, длительность, exit-код, число
  tool-вызовов);
- в stderr печатается строка `# scout-run: ...` с длительностью и числом
  вызовов.

Каталог `output/` игнорируется git; старые прогоны можно удалять вручную.

## Окружение плагина

`scout`-инструмент — плагин opencode, который импортирует `@opencode-ai/plugin`
(версия зафиксирована в `.opencode/package.json` и `package-lock.json`). Если
`.opencode/node_modules` отсутствует или пересобран, плагин не загрузится и
`scout` исчезнет. Восстановление:

```bash
cd .opencode && npm ci
```

## Хелпер: команды

```bash
backend/.venv/bin/python backend/scripts/expert_scout.py experts
backend/.venv/bin/python backend/scripts/expert_scout.py search "<запрос>" [--experts a,b | --group visual] [--recent-days N] [--limit N] [--no-vector] [--json]
backend/.venv/bin/python backend/scripts/expert_scout.py show <expert:message_id> [...] [--comments-limit N] [--json]
```

`--group` (`tech`, `tech_business`, `visual`) резолвится через
`backend/src/expert_groups.py` — ту же карту, что использует Панэкс.

## Границы и безопасность

- **Только чтение**: `mode=ro` + `PRAGMA query_only=ON`; скаут не пишет в
  корпус и не меняет репозиторий.
- **Без shell**: у агента нет bash; `scout`-инструмент вызывает хелпер напрямую
  через argv-массив, инъекция команд через аргументы невозможна.
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
Второй замер (review-прогон того же дня, другой вопрос): 77 с — латентность
сильно зависит от вопроса; считайте таблицу иллюстрацией, а не паритетом.

## Когда использовать

| Канал | Что даёт |
|---|---|
| `expert-scout` | Сырые первоисточники с цитатами, итеративный поиск по корпусу |
| `reddit-search` | Мнение сообщества, свежие обсуждения |
| Панэкс (`panex ask`) | Готовый сжатый дайджест по выбранным экспертам |

Scout не заменяет два других канала и не выдаёт мнение практиков за истину.
Область поиска: названный эксперт (`acidcrunch`) ограничивает поиск только им;
группа («визуалы») — составом группы из канонической карты; без уточнения
ищется по всем экспертам.

## Восстановление Mac-shim

На Маке из checkout репозитория:

```bash
scripts/install_expert_scout_skill.sh --with-shim
```

Установщик — источник истины для содержимого мостика: он же переустанавливает
скиллы и перезаписывает `~/.local/bin/expert-scout`. Мостик форвардит
`EXPERT_SCOUT_TIMEOUT` с Мака на VM (по умолчанию 300 секунд).

## Диагностика

- «opencode not found» / «backend python not found» — проверить
  `~/.opencode/bin/opencode` и `backend/.venv` на VM.
- «Permission denied» — проверить SSH-ключ Mac → VM.
- «scout: opencode failed (exit 124)» — сработал hard-timeout обёртки
  (`EXPERT_SCOUT_TIMEOUT`); частичный поток смотреть в `events.jsonl`
  артефактов прогона.
- `# WARNING` в начале ответа — агент не выдал финальный ответ после
  последнего tool-вызова; ниже идёт промежуточный нарратив, ему нельзя
  доверять как ответу.
- Пустой ответ (exit 3) — агент не выдал ни одной текстовой части; смотреть
  `events.jsonl` артефактов прогона. Это аномалия, а не «нет сигнала»:
  честный ответ «в корпусе нет сигнала» приходит текстом и даёт exit 0.
