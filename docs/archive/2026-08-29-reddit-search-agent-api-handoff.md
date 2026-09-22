# Handoff: универсальный API полного Reddit Search V2

## Для кого этот документ

Этот handoff предназначен ИИ-агенту, который будет работать на большой Oracle VM
в актуальном checkout Experts Panel:

```text
/home/ubuntu/apps/experts-panel/dev
```

Андрей запускает агента из этой папки. Технические проверки, Git-команды и
диагностику агент выполняет самостоятельно — не перекладывает их на Андрея.

## Короткая цель

Нужно дать другим проектам и ИИ-агентам стабильный программный доступ к **полному
Reddit Search V2**, который уже работает внутри Experts Panel.

Это **не** задача выставить наружу сырой Node.js `reddit-proxy`. Proxy выполняет
только OAuth search/details. Ценный полный механизм также включает:

- формулировку Reddit-friendly запросов и AI Scout;
- несколько discovery-каналов;
- дедупликацию и enrichment;
- раннее чтение комментариев;
- answerability rerank и confidence filtering;
- честный abstain на слабой выдаче;
- итоговый synthesis со ссылками на реальные Reddit-треды.

Желаемая будущая цепочка:

```text
любой проект / Codex skill
        -> универсальная CLI-команда
        -> стабильный Experts Panel API
        -> существующий полный Reddit Search V2
```

Главная и единственная реализационная задача этой сессии — создать и проверить
серверный API-контракт. CLI и глобальный Codex skill не реализовывать: это
следующий отдельный этап после production-проверки API. Новый API сразу сделать
пригодным для будущего тонкого CLI, но не расширять текущий scope ради клиента.

## Рабочие правила проекта

Перед изменениями обязательно полностью прочитать:

1. `AGENTS.md`
2. `docs/DOCUMENTATION_MAP.md`
3. `docs/architecture/reddit-service.md`
4. `services/reddit-proxy/README.md`
5. профильные части `docs/architecture/agent-context-api.md`

Работать только в:

```text
/home/ubuntu/apps/experts-panel/dev
```

Не редактировать production checkout:

```text
/home/ubuntu/apps/experts-panel/app
```

На момент подготовки handoff VM checkout был чистым:

```text
main...origin/main
f3c9bf8 ops: simplify Experts Panel development workflow
```

Это только исходное наблюдение. В начале работы проверить состояние заново. Не
удалять и не перезаписывать незнакомые изменения, если они появились позднее.

## Доказанное текущее состояние

- `services/reddit-proxy` — отдельный Fastify/TypeScript Docker service.
- Proxy имеет `POST /search`, `POST /details`, `GET /health`.
- В production proxy доступен backend по Compose-адресу
  `http://reddit-proxy:3000`, но не является отдельным публичным продуктовым API.
- Полная orchestration-логика находится в
  `backend/src/services/reddit_enhanced_service.py`.
- Synthesis находится в
  `backend/src/services/reddit_synthesis_service.py`.
- Основной `/query` использует SSE и сейчас требует `expert_filter` из 1–5
  экспертов, поэтому не является готовым универсальным Reddit-only API.
- Agent Context API содержит поле `include_reddit`, но MVP сейчас явно отклоняет
  его как не реализованное. Нельзя просто объявить этот путь готовым.
- Старый отдельный Fly.io Reddit proxy существовал исторически, но его контракт и
  архитектура устарели. Не восстанавливать старый MCP/Fly runtime.

## Сначала исследовать, затем менять

До реализации проследить реальный текущий вызов Reddit pipeline от API endpoint
до результата. Найти минимальную переиспользуемую функцию/границу, которая:

- принимает пользовательский query и `use_recent_only`;
- запускает именно Search V2;
- возвращает final synthesis, реальные sources и статус выполнения;
- различает успешный ответ, честный abstain и техническую ошибку;
- не требует фиктивного выбора эксперта;
- не дублирует orchestration-код из основного pipeline.

Если такой чистой границы сейчас нет, разрешён небольшой выделяющий refactor,
который используют и существующая Panel, и новый API. Нельзя копировать большой
кусок pipeline во второй endpoint.

Перед кодом кратко сообщить Андрею:

- какой существующий путь найден;
- где будет новая тонкая граница;
- какие файлы предполагается изменить;
- почему это не меняет обычный поиск Experts Panel.

## Зафиксированное решение

Добавить небольшой синхронный versioned JSON API полного Reddit-only поиска:

```text
POST /api/v1/agent/reddit-search
```

Endpoint должен находиться в существующей agent-facing API boundary с prefix
`/api/v1/agent`. Не создавать новый микросервис, новый API namespace и не
переносить код в другой репозиторий.

Минимальный request contract:

```json
{
  "query": "What do practitioners say about Claude Code hooks?",
  "use_recent_only": false
}
```

Не добавлять десятки пользовательских tuning-параметров. Внутренние лимиты,
модели, thresholds и discovery strategies остаются конфигурацией Experts Panel.

Успешный HTTP response должен быть пригоден для будущего CLI и ИИ-агента и
содержать:

- machine-readable status: `completed` или `abstained`;
- исходный query;
- итоговый synthesis/answer при наличии;
- структурированный массив источников с title, URL и subreddit;
- достаточную метаинформацию, чтобы отличить пустой честный результат от поломки;
- стабильное диагностическое сообщение без выдачи внутренних секретов.

Зафиксированный минимальный shape (дополнительные поля — только если они уже
естественно следуют из общей Search V2 модели и доказанно нужны клиенту):

```json
{
  "status": "completed",
  "query": "What do practitioners say about Claude Code hooks?",
  "answer": "Source-grounded synthesis",
  "sources": [
    {
      "title": "Discussion title",
      "url": "https://www.reddit.com/r/example/comments/example",
      "subreddit": "example"
    }
  ],
  "message": null
}
```

Для честного abstain: `status="abstained"`, `answer=null`, `sources=[]` и
короткий `message`, объясняющий отсутствие достаточно надёжных результатов.
Не превращать abstain в искусственно заполненный LLM-ответ.

Техническую поломку не маскировать как успешный `200 failed`: использовать
подходящий HTTP 4xx/5xx и короткий безопасный `detail`. Будущий CLI преобразует
такую ошибку в своё пользовательское состояние `failed` и ненулевой exit code.

Не включать в response:

- chain-of-thought или скрытые prompts;
- токены, credentials, env values;
- внутренние stack traces;
- несвязанный ответ экспертов/Telegram pipeline;
- выдуманные источники или LLM-текст, представленный как источник.

Для первой версии использовать существующий синхронный Agent Context pattern:
`asyncio.wait_for` и `AGENT_CONTEXT_TIMEOUT_SECONDS`. Не строить SSE, polling,
очередь, брокер, artifact delivery или новую job platform без доказанного
превышения уже установленного timeout/response-size контракта. Если реальный
smoke докажет, что синхронный ответ непригоден, остановиться и принести Андрею
конкретные timings/размеры перед расширением архитектуры.

## Доступ и безопасность

API не должен становиться анонимным дорогим публичным endpoint. Решение по
авторизации уже принято — не создавать второй секрет или новую auth-схему.

- Переиспользовать `verify_agent_context_token` из
  `backend/src/api/dependencies.py`.
- Использовать существующий `Authorization: Bearer <token>` и
  `AGENT_CONTEXT_API_TOKEN`.
- Сохранить существующий per-token rate limit через ту же dependency.
- Использовать существующие `AGENT_CONTEXT_TIMEOUT_SECONDS` и, где применимо,
  `AGENT_CONTEXT_MAX_RESPONSE_BYTES`; не добавлять Reddit-дубликаты этих env.
- Не создавать и не печатать реальные секреты в коде, docs, tests или чате.
- Не читать и не выводить `.env`.
- Не использовать Reddit credentials напрямую из CLI.
- `reddit-proxy:3000` не выставлять публично и не менять его network boundary.
- Предусмотреть bounded input, понятные 4xx и безопасные 5xx.
- Учитывать стоимость synthesis/Serper и возможность злоупотребления, но не
  строить пользовательские тарифы, кабинеты и биллинг.

Внешний доступ для других людей — будущий этап. Сейчас нужен защищённый личный
API, пригодный для Андрея и его агентов.

## Совместимость — главный инвариант

После изменения обычная Experts Panel должна продолжать использовать тот же
Reddit Search V2 и работать как раньше.

Правильная схема:

```text
Experts Panel UI ---------+
                         +--> одна существующая Reddit Search V2 логика
новый Reddit API --------+
```

Недопустимая схема:

```text
новый endpoint --> скопированный второй Reddit pipeline
```

Не менять без необходимости:

- алгоритм retrieval/rerank/synthesis;
- confidence thresholds;
- UI и его Reddit toggle;
- proxy OAuth implementation;
- Compose network exposure;
- production DB или процесс её обновления;
- текущие модельные настройки.

## Будущий CLI — контекст, не текущий scope

После отдельного решения поверх GREEN production API будет добавлен минимальный
CLI/portable runner. Целевой UX в будущем:

```bash
reddit-search "что пишут про Claude Code hooks"
reddit-search "что изменилось в локальных LLM" --recent
reddit-search doctor
```

Будущий CLI должен:

- работать независимо от текущей project directory;
- обращаться только к официальному API;
- брать URL/token из безопасной пользовательской конфигурации или env;
- не печатать token;
- выдавать удобный текст и, при необходимости, стабильный JSON mode;
- корректно различать completed/abstained/failed;
- возвращать ненулевой exit code только для реальной технической ошибки.

Сейчас CLI-файлы, installer и skill не создавать. Не писать MCP-server и не
добавлять framework для плагинов.

## Проверки

Нужны минимальные, но реальные проверки изменённого scope.

### Контрактные/автоматические

- валидный query;
- слишком короткий/длинный или пустой query;
- `use_recent_only=true/false`;
- completed со structured sources;
- abstained без подмены его ошибкой;
- безопасная обработка upstream failure/timeout;
- unauthorized request;
- отсутствие stack trace и secret-like значений в response;
- доказательство, что endpoint вызывает общую Search V2 логику, а не копию.

Моки разрешены для локальных контрактных тестов, но нельзя менять production
behavior только ради зелёного теста. До deploy достаточно контрактных тестов и
существующего локального/контейнерного smoke, который не требует чтения секретов.
После явного `выкатывай` для итогового доказательства нужен отдельный
authenticated production smoke полного pipeline с фактическими Reddit-ссылками.

### Регрессия Experts Panel

- профильные backend tests;
- существующие Reddit Search V2 checks по документации;
- проверка текущего panel query path с включённым Reddit;
- proxy health/build только если proxy действительно менялся;
- не запускать весь тяжёлый test suite автоматически без необходимости.

### Production

Не commit, не push и не deploy по словам «проверь», «подготовь» или
«разберись». Следовать семантике команд из `AGENTS.md`.

После явного `выкатывай`:

1. выполнить нужные проверки;
2. commit и push `main`;
3. дождаться GitHub Actions;
4. проверить общий `/health`;
5. выполнить authenticated smoke нового API;
6. выполнить smoke старого Panel Reddit flow;
7. убедиться, что production DB не обновлялась.

## Документация

Обновить профильный SSOT, а не плодить несколько конкурирующих документов.
Документация должна коротко фиксировать:

- назначение agent-facing Reddit API;
- request/response schema;
- authentication без значения секрета;
- completed/abstained semantics и HTTP 4xx/5xx для технических ошибок;
- будущую CLI boundary без описания несуществующих команд как готовых;
- что `reddit-proxy` остаётся внутренним компонентом;
- какие проверки подтверждают совместимость Panel.

Если нужен новый документ, добавить его в `docs/DOCUMENTATION_MAP.md` и связать с
`docs/architecture/reddit-service.md`. Не тащить исторический Fly/MCP spec обратно
в активные инструкции.

## Не входит в scope

- отдельный GitHub-репозиторий Reddit service;
- перенос runtime с Oracle VM;
- возвращение Fly.io;
- публичное открытие порта proxy;
- новый MCP server;
- multi-user accounts, dashboard, billing или API marketplace;
- реализация CLI и глобального Codex skill на Mac;
- переработка качества Search V2 без отдельной задачи и evidence;
- ротация исторически утёкших credentials в рамках этой реализации;
- любые изменения production DB.

## Definition of Done

Работа готова только когда:

1. Есть один документированный защищённый API полного Reddit Search V2.
2. Он не требует фиктивного выбора эксперта.
3. Он возвращает понятный JSON для completed/abstained, а технические ошибки —
   безопасные HTTP 4xx/5xx.
4. Источники структурированы и содержат реальные Reddit URL.
5. Реализация переиспользует существующий pipeline без его копирования.
6. Обычная Experts Panel и её Reddit flow прошли регрессионную проверку.
7. Внутренний `reddit-proxy` не выставлен наружу.
8. Секреты не попали в Git, docs, tests, logs или ответы API.
9. Документация обновлена в правильном SSOT.
10. CLI и skill не реализованы внутри этого scope.
11. Ничего не задеплоено без явной команды Андрея `выкатывай`.

## Формат финального отчёта Андрею

Объяснить без DevOps-жаргона:

- **Зачем:** какую возможность теперь получил Андрей;
- **Что изменилось:** endpoint и общая внутренняя граница;
- **Как проверено:** автоматические tests и реальные smoke;
- **Что не проверено:** честно и с причиной;
- **Совместимость:** доказательства, что поиск внутри Panel не сломан;
- **Состояние выпуска:** только локально / committed / pushed / deployed;
- **Следующий шаг:** что потребуется для глобального Codex skill на Mac.
