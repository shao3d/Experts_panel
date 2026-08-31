# Настройка Reddit Search для Codex на локальном Mac

## Короткий ответ

Да, это можно сделать через GitHub, и это самый удобный путь для файлов проекта:

1. синхронизировать Mac checkout с `main`;
2. запустить штатный installer из репозитория;
3. один раз настроить локальный `AGENT_CONTEXT_API_TOKEN` безопасным способом;
4. проверить `reddit-search --doctor`;
5. перезапустить Codex и попросить его прочитать `AGENTS.md` и этот документ.

Копировать skill вручную по SSH можно, но это запасной вариант. В репозитории уже
есть skill, portable runner и installer; повторное переписывание инструкций вручную
создаёт риск рассинхронизации.

## Что именно нужно перенести

Рабочий комплект состоит из четырёх частей:

- `.codex/skills/reddit-search/SKILL.md` — инструкции Codex;
- `.codex/skills/reddit-search/agents/openai.yaml` — metadata skill;
- `scripts/reddit_search_runner.py` — portable stdlib-only runner;
- `scripts/install_reddit_search_skill.sh` — installer глобального skill и команды.

Правила проекта находятся в корневом `AGENTS.md`. Для Reddit оно требует использовать
только официальную команду `reddit-search` и запрещает прямой вызов `reddit-proxy`.

Skill и `AGENTS.md` не содержат токен. Токен должен существовать только в локальном
пользовательском окружении или в другом защищённом локальном хранилище.

## Рекомендуемый путь: через GitHub

На Mac работай в checkout:

```text
/Users/andreysazonov/Documents/Projects/Experts_panel
```

Синхронизируй checkout обычным безопасным способом, не перезаписывая незнакомые
локальные изменения. После синхронизации запусти из корня проекта:

```bash
bash scripts/install_reddit_search_skill.sh
```

Installer устанавливает:

```text
~/.codex/skills/reddit-search/SKILL.md
~/.codex/skills/reddit-search/agents/openai.yaml
~/.codex/skills/reddit-search/reddit_search_runner.py
~/.local/bin/reddit-search
```

Installer не создаёт, не копирует и не печатает токен. Убедись, что `~/.local/bin`
добавлен в `PATH`. Если команда не находится, вызови её полным путём или добавь
`export PATH="$HOME/.local/bin:$PATH"` в локальную shell-конфигурацию.

## Доступ к API

Команда обращается только к защищённому agent-facing API:

```text
https://expa.beyondhorizon.dev/api/v1/agent/reddit-search
```

URL можно переопределить через `REDDIT_SEARCH_API_URL`, но обычно это не требуется.
Для поиска нужен `AGENT_CONTEXT_API_TOKEN`. Значение токена нельзя помещать в:

- этот документ;
- `AGENTS.md` или `SKILL.md`;
- GitHub, commit, issue или prompt;
- shell history, логи или вывод команд.

Настрой токен через локальный секретный механизм, который уже принят на Mac. Не
выводи его на экран и не вставляй в чат. Если токен ещё не выдан, его нужно получить
у владельца/оператора Experts Panel безопасным каналом; не брать его из репозитория,
`.env`, логов или production checkout.

## Проверка

Проверка доступности API не выполняет поиск и не требует токена:

```bash
reddit-search --doctor
```

Ожидается здоровый API. Затем можно выполнить небольшой реальный поиск:

```bash
reddit-search "What do practitioners say about Claude Code hooks?"
```

Для свежих обсуждений:

```bash
reddit-search "What changed recently in local LLM tooling?" --recent
```

Для машинной обработки:

```bash
reddit-search --json "What do practitioners say about Claude Code hooks?"
```

Если команда вернула `status: abstained`, это нормальный честный результат: надёжных
обсуждений не найдено. Не заменяй его общими знаниями. Ненулевой exit code означает
техническую проблему: отсутствующий токен, недоступный API, timeout или HTTP-ошибку.

## Что попросить Codex

После установки полностью перезапусти Codex, чтобы он перечитал глобальные skills.
Запускай его из корня Mac checkout и попроси:

> Прочитай корневой `AGENTS.md`, `.codex/skills/reddit-search/SKILL.md` и
> `docs/guides/reddit-search-mac-setup.md`. Подтверди, что для Reddit-поиска будешь
> использовать только глобальную команду `reddit-search`, а `reddit-proxy` напрямую
> вызывать не будешь. Не показывай и не диагностируй значение токена.

Затем попроси тестовый поиск. Агент должен вызвать `reddit-search`, а в ответе
показать синтез и реальные Reddit-ссылки при `completed`, честно сообщить об
`abstained` или отдельно указать техническую ошибку.

## SSH-вариант

SSH-копирование возможно, если Mac checkout временно нельзя синхронизировать с
GitHub. Но переносить нужно не только `SKILL.md`, а весь комплект skill + runner +
installer либо запускать installer после копирования репозитория. SSH не решает
вопрос API-доступа и токена: их всё равно нужно настроить отдельно.

Поэтому рекомендуемый порядок такой:

```text
GitHub main -> Mac checkout -> штатный installer -> локальная конфигурация token -> doctor -> Codex
```

## Важные границы

- Не вызывай `reddit-proxy` напрямую: это внутренний sidecar VM.
- Не запускай backend pipeline локально для обычного Reddit-вопроса.
- Не копируй Reddit credentials на Mac: локальному runner нужен только agent API token.
- Не коммить локальные shell-конфиги и секреты.
- Обычная синхронизация кода не обновляет production DB и не выполняет deploy.

## Источники истины в репозитории

- `AGENTS.md` — обязательные правила для всех агентов;
- `docs/architecture/reddit-service.md` — API-контракт и CLI-граница;
- `.codex/skills/reddit-search/SKILL.md` — поведение Codex skill;
- `scripts/install_reddit_search_skill.sh` — установка;
- `scripts/reddit_search_runner.py` — portable CLI runner;
- `services/reddit-proxy/README.md` — внутренний proxy, который не нужно запускать
  для работы Codex на Mac.
