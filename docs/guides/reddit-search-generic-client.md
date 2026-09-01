# Generic Reddit Search client

## Назначение

Минимальный пакет для доверенных пользователей CLI-агентов. Клиент вызывает
только hosted Experts Panel Reddit Search API и не требует локального backend,
Docker, базы Experts Panel или Reddit credentials.

## Граница доступа

Каждому пользователю выдаётся отдельный Reddit-only токен. Server env:

```text
REDDIT_SEARCH_CLIENT_TOKENS=<token-a>,<token-b>
```

Эти токены принимаются только `POST /api/v1/agent/reddit-search`. Они не должны
проходить `verify_agent_context_token` и не дают доступ к Панэксу. Общий
`AGENT_CONTEXT_API_TOKEN` пользователям не передаётся.

## Сборка пакета

Из корня checkout:

```bash
bash scripts/build_reddit_search_generic_client.sh
```

Результат:

```text
dist/reddit-search-generic-client.zip
```

Архив не содержит токенов. Runner копируется из единственного SSOT
`scripts/reddit_search_runner.py` во время сборки.

Для персонального автономного handoff передать builder путь к файлу с отдельным
Reddit-only токеном. Значение токена не должно попадать в командную строку:

```bash
REDDIT_SEARCH_TOKEN_FILE=/secure/path/oleg-token \
REDDIT_SEARCH_PACKAGE_NAME=reddit-search-oleg \
bash scripts/build_reddit_search_generic_client.sh
```

Такой ZIP уже является credential: хранить и передавать его только приватно,
не коммитить и не загружать в публичные сервисы. Внутри есть `AGENT_SETUP.md`,
по которому CLI-агент выполняет установку, `--doctor` и live smoke без вопросов
получателю. После установки извлечённая копия токена удаляется, но исходный ZIP
остаётся ключом доступа до отзыва токена на сервере.

## Установка пользователем

Распаковать архив и запустить:

```bash
cd reddit-search-generic-client
bash install.sh
```

Installer попросит токен без отображения ввода и сохранит его в
`~/.config/reddit-search/token` с правами `0600`. Команда устанавливается в
`~/.local/bin/reddit-search`.

Для персонального архива агент запускает без участия пользователя:

```bash
bash install.sh --non-interactive --verify
```

## Подключение к generic CLI agent

Передать агенту содержимое установленного
`~/.config/reddit-search/AGENT_INSTRUCTIONS.md` или добавить его в глобальный
instruction-файл конкретного агента.

## Проверка

```bash
reddit-search --doctor
reddit-search "What do practitioners say about Claude Code hooks?"
```

`--doctor` не выполняет поиск. Реальный запрос должен вернуть `completed` с
Reddit-ссылками или честный `abstained`. Ненулевой exit code — техническая ошибка.

## Отзыв доступа

Удалить конкретный токен из `REDDIT_SEARCH_CLIENT_TOKENS` на сервере и применить
обычный code/config deploy. Остальные клиентские токены продолжают работать.
