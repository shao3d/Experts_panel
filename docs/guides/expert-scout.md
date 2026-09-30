# Expert Scout (agentic read-only поиск по корпусу)

Status: Active (owner-approved read-only contour)
Last updated: 2026-09-30

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
  -> backend/scripts/expert_scout.py   (read-only: experts / search / digest / show)
  -> backend/data/experts.db           (mode=ro, query_only=ON)
  -> scripts/expert_scout_filter.py    (сборка финального ответа)
  -> backend/scripts/verify_citations.py (целостность: ключи/цитаты/повторы)
```

- Агент — `.opencode/agents/expert-scout.md` (модель
  `opencode/space-bunny-free`, `variant: max`, `temperature: 0.2`; до
  2026-09-30 была `opencode-go/deepseek-v4.1-flash` — подписка OpenCode Go
  исчерпана, поэтому переключились на free-модель; при смене модели правь
  и эту строку, и `docs/roadmap/2026-09-system-review.md`). Shell агенту
  недоступен
  (bash запрещён полностью): единственный инструмент — read-only `scout` из
  плагина `.opencode/plugins/expert-scout-tools.ts`, который запускает хелпер
  через argv-массив без shell, поэтому подстановки `$( )`/backticks в
  аргументах инертны (проверено пробой 2026-09-13).
- Хелпер — `backend/scripts/expert_scout.py`: гибрид FTS5 + vector
  (soft-freshness + RRF, как в `HybridRetrievalService`), точное раскрытие
  источника по `source_key` с раздельной выборкой авторских комментариев и
  постраничная вычитка скоупа без поиска (`digest`).
- Ответ возвращается без промежуточных прогресс-нот
  (`scripts/expert_scout_filter.py`); если агент не выдал финальный ответ,
  fallback-нарратив помечается явным `# WARNING`.

## Прогон: таймаут и артефакты

Обёртка `scripts/expert_scout.sh`:

- hard-timeout на весь агентный прогон: переменная `EXPERT_SCOUT_TIMEOUT`
  (секунд, по умолчанию 300);
- артефакты каждого прогона в `output/scout_runs/<timestamp>/`:
  `question.txt`, `events.jsonl` (сырой поток opencode), `answer.md`
  (финальный ответ), `integrity.json` (отчёт проверки целостности),
  `integrity.log` (одна строка-сводка), `meta.txt` (вопрос, длительность,
  exit-код, число tool-вызовов, `integrity_exit` и сводка проверки);
- в stderr печатается строка `# scout-run: <s>s, exit=…, tool_calls=…,
  integrity_exit=… # integrity: keys=… missing=… quotes=… unverified=…
  loops=…` — по ней прогон виден сразу, без открытия артефактов.

Каталог `output/` игнорируется git; старые прогоны можно удалять вручную.

## Проверка целостности ответа

`backend/scripts/verify_citations.py` (вызывается обёрткой автоматически):

- каждый `source_key` из ответа должен существовать в корпусе; несуществующие
  → `# WARNING: unverified source_keys: ...` в начале `answer.md`, exit 1;
- дословные цитаты (≥25 символов) сверяются с текстом источника и его
  комментариями (устойчиво к многоточиям) — несовпадения попадают в
  `integrity.json` как `quotes_unverified`, но не валят прогон: модель часто
  пересказывает цитату своими словами (в т.ч. переводит), и это не выдумка;
- ≥3 одинаковых `scout`-вызова за прогон (не обязательно соседних; считаются
  запросы `tool_use` с одинаковыми аргументами) → `tool_loops` в отчёте и
  warning (типовой провал агента: зацикливание);
- отчёт: `integrity.json` рядом с `answer.md`; проверка вручную:
  `backend/.venv/bin/python backend/scripts/verify_citations.py --answer <answer.md> [--events <events.jsonl>]`.

Правило для оператора: `# WARNING: unverified source_keys` в ответе — это
сигнал, что какой-то источник выдуман или не найден; такой ответ нельзя
передавать как есть, ключ проверяется вручную через `show`.

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
backend/.venv/bin/python backend/scripts/expert_scout.py search "<запрос>" [--experts a,b | --group visual] [--recent-days N] [--limit N] [--no-vector] [--freshness tool|craft|any] [--diversity] [--now ISO] [--json]
backend/.venv/bin/python backend/scripts/expert_scout.py digest --experts a,b | --group visual [--window N] [--page N] [--recent-days N] [--json]
backend/.venv/bin/python backend/scripts/expert_scout.py show <expert:message_id> [...] [--comments-limit N] [--expand N] [--json]
```

`--group` (`tech`, `tech_business`, `visual`) резолвится через
`backend/src/expert_groups.py` — ту же карту, что использует Панэкс.
`--comments-limit` — лимит на каждое окно (автор / сообщество) отдельно.
`search` отдаёт широкий пул (по умолчанию 20, максимум 40 карточек) — модель
сама ранжирует; глубина кандидатов поиска постоянна, чтобы широкий пул не
перемешивал топ-10. `--freshness craft|any` отключает штраф за возраст
(durable-крафт), `tool` (дефолт) — мягкий штраф за старость. `--now ISO`
фиксирует «сейчас» для штрафа свежести (воспроизводимые замеры). `--diversity`
— opt-in потолок постов одного эксперта в топ-окне (по замеру нейтрально по
recall, поэтому выключен по умолчанию). `digest` — постраничная вычитка всего
скоупа без поиска (окно ≤30 постов, ≤12k символов на вызов): для вопросов про
конкретного эксперта/видеохаб точнее поиска; `--experts video_hub` — весь
ВидеоХаб. `show --expand N` — вместе с постом подтягивает ±N соседних постов
того же эксперта (контекстная склейка для серийных разборов).

Video Hub segments (`expert_id=video_hub`) additionally return `video_link`
(`https://youtu.be/<id>?t=<seconds>s`), `video_url`, `video_timestamp_s` and
`video_title` in both `search` and `show` (built from `media_metadata`), so
findings can cite the exact moment on YouTube. `visual` (prompt/settings/slides)
is not exposed as a structured field; its text lives inside `content` as a
`VISUAL:` block.

## Измерение качества (стенды)

Два автоматических стенда; каждый пункт улучшений принимается только по их
цифрам (регрессия = пункт отклонён или переводится в opt-in). Текущий снимок:
mean recall@10 = 0.20, recall@40 = 0.39 (baseline `backend/tests/search_probe_baseline.json`).

- **Поисковый стенд** — фикстуры `backend/tests/search_probe_fixtures.py`
  (24 реальных вопроса владельца из `output/scout_runs/` с `source_key`,
  проверенными на существование через `show` и на дословность цитат). Метрики:
  recall@10/@20/@40, MRR, «спрятанные ключи» (в пуле, но вне топ-10), доля
  ключей вообще вне пула (их спасает `digest`), craft-дельта, экспертов в
  топ-10, телеметрия ног гибрида. Команды:
  ```bash
  backend/.venv/bin/python backend/scripts/search_probe.py --check-keys   # фикстуры живы
  SEARCH_PROBE=1 backend/.venv/bin/python backend/scripts/search_probe.py --run --check-baseline
  backend/.venv/bin/python backend/scripts/search_probe.py --write-baseline  # осознанно, с обоснованием
  ```
  Стенд передаёт `--now` с меткой baseline, иначе метрики «плывут» при смене
  календарного дня (штраф свежести суточный). pytest-обёртка:
  `backend/tests/test_search_probe.py` (сетевые тесты — под `SEARCH_PROBE=1`,
  идут через embedding API, ~2–4 минуты).
- **Запуск pytest в этом репозитории** требует `-o addopts=""`:
  `backend/pyproject.toml` прописывает `--cov=*` в `addopts`, но `pytest-cov`
  в venv не установлен, и без override pytest падает с
  `unrecognized arguments: --cov=src`. Рабочая форма:
  ```bash
  # быстро (без сети): проверка фикстур и юниты
  backend/.venv/bin/python -m pytest backend/tests/test_expert_scout.py \
    backend/tests/test_verify_citations.py backend/tests/test_search_probe.py \
    -o addopts="" -q
  # полный поисковый замер (нужна сеть + embedding API)
  SEARCH_PROBE=1 backend/.venv/bin/python -m pytest backend/tests/test_search_probe.py \
    -o addopts="" -q
  ```
- **Агентный стенд** — `backend/scripts/agent_probe.py`: реальные прогоны
  агента на 5 вопросах (3 hit + 2 gap/контроль). Оценка ответа: recall
  ожидаемых ключей, выдуманные ключи, честность abstain, покрытие
  (доля реально прочитанных источников, попавших в ответ). Оговорка: LLM
  вариативен (один вопрос давал 0.25–0.75 в повторах) — одиночные дельты
  индикативны, регрессии перепроверяются повторами; каждый прогон — реальный
  вызов LLM, поэтому стенд дорогой и запускается точечно.
  ```bash
  backend/.venv/bin/python backend/scripts/agent_probe.py --run --json-out /tmp/after.json
  backend/.venv/bin/python backend/scripts/agent_probe.py --compare /tmp/before.json /tmp/after.json
  ```

## Отклонённые и opt-in эксперименты (не повторять без причины)

- **Query-side морфология RU** (2026-09-29, отклонена замером): стемминг
  запроса со звёздочкой («кредитами» → `кредит*`) и более мягкий вариант
  «слово + префикс». Оба дали регрессии топ-10 (MRR 0.145 → 0.108) без роста
  морфо-фикстур: причина провала `morph_credits` — семантическая дистанция
  запроса к текстам, а не морфология; а wildcard-термы размывают BM25-вершину.
  Настоящий фикс морфологии — нормализованные токены на индексации +
  переиндексация (отдельная задача с data release), не правка запроса.
- **Разнообразие выдачи** (2026-09-29, измерено нейтрально → opt-in):
  потолок постов одного эксперта в поисковом окне (`DIVERSITY_CAP_TOP=6`, в
  хвосте `DIVERSITY_CAP_REST=10`) даёт +1 найденный ответ на 20 вопросов и
  +0.7 эксперта в топ-10, но слегка топит глубину. Код и тесты есть
  (`diversify()`), включается флагом `--diversity`, по умолчанию выключен.

## Что уже улучшено (не начинать с нуля)

Проверено замерами 2026-09-29 (все изменения уже в коде):

- широкий пул выдачи (до 40) + ранжирование моделью вместо жёсткой обрезки;
- профили свежести `tool|craft` (+18% находного на крафтовых вопросах);
- телеметрия ног гибрида (`retrieval_stats`) — мёртвая нога больше не молчит;
- `digest` — вычитка скоупа без поиска (71 ключ вообще вне пула поиска);
- план поиска + протокол abstain (честный abstain, ноль выдумок на 5 прогонах);
- верификатор цитат и ловушка повторов (`verify_citations.py`);
- `--now` для воспроизводимых замеров.

Два честных хвоста, чтобы новый агент не считал их сделанными:

- **Леджер находок** (правило в `.opencode/agents/expert-scout.md`: финальный
  ответ собирается только из построенного леджера) — правило есть, замер
  покрытия «после» не завершён (прогоны LLM прерваны владельцем). «До»
  измерено офлайн-пересчётом уже сохранённых прогонов: покрытие 0.856 на трёх
  hit-вопросах (цифра живёт только здесь; пересчитывается через
  `agent_probe.py`). Считать правило неподтверждённым, пока стенд не пройден.
- **Происхождение фикстур**: `backend/tests/search_probe_fixtures.py` собран
  одноразово из реальных ответов в `output/scout_runs/` (ключи из `answer.md`,
  затем mechanically проверены через `show`); `output/` в git не попадает, так
  что пересборка фикстур — ручная операция. Сами фикстуры в репозитории и
  проверяются на живость в каждом прогоне тестов.

Не сделано осознанно: дублирование retrieval-кода между хелпером и
`HybridRetrievalService` (расхождение возможно), contextual embeddings
(нужна переиндексация и data release). Это кандидаты, а не TODO.

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

Когда вопрос привязан к одному эксперту или к ВидеоХабу, поиск иногда
уступает сплошной вычитке скоупа (`digest`): скоупы небольшие, а 71 из
известных ответов вообще не попадают в поисковую выдачу. Агент применяет
digest сам; вручную — `digest --experts <id>` с постраничным чтением.

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
- `# WARNING: unverified source_keys: ...` — верификатор нашёл в ответе
  несуществующий ключ; детали в `integrity.json`, ключ проверяется `show`.
- Пустой ответ (exit 3) — агент не выдал ни одной текстовой части; смотреть
  `events.jsonl` артефактов прогона. Это аномалия, а не «нет сигнала»:
  честный ответ «в корпусе нет сигнала» приходит текстом и даёт exit 0.
