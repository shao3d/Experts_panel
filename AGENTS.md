# Experts Panel: правила для ИИ-агентов

Этот файл обязателен для Codex, OpenCode, Freebuff и других ИИ-агентов.
Он хранится в Git и одинаково действует на Mac и на development VM.

## Перед любой работой

1. Выполни `git status --short --branch`, `git remote -v` и
   `git rev-parse --short HEAD`.
2. Не трогай незнакомые изменения: это может быть работа человека или другого агента.
3. Прочитай корневой `CLAUDE.md`. Для backend или frontend дополнительно прочитай
   соответствующий `backend/CLAUDE.md` или `frontend/CLAUDE.md`.
4. Для UI-изменений соблюдай
   `docs/design-system/refero-say-briefly/UX_INVARIANTS.md`.

## Где ведётся разработка

- GitHub: `shao3d/Experts_panel`, ветка `main`.
- Основной development checkout на VM:
  `oracle-work:/home/ubuntu/apps/experts-panel/dev`.
- Запасной checkout на Mac:
  `/Users/andreysazonov/Documents/Projects/Experts_panel`.
- Production checkout на той же VM:
  `/home/ubuntu/apps/experts-panel/app`.
  В нём запрещены обычная разработка, запуск ИИ-кодеров и ручное редактирование.
- Production runtime и данные находятся уровнем выше checkout, в
  `/home/ubuntu/apps/experts-panel/`; не изменяй их без профильного runbook и
  явного разрешения владельца.

GitHub — источник истины для закоммиченного кода. В один момент времени изменения
вносит только один development checkout: VM `dev` или Mac. Не синхронизируй код
через `scp`, `rsync` или ручное копирование.

## Переключение между VM и Mac

Перед сменой машины текущий агент обязан:

1. Показать владельцу `git status` и отделить нужные изменения от чужих.
2. Запустить проверки для изменённого scope.
3. По явной команде владельца создать commit.
4. Отдельно предупредить, что push в `main` запускает production-деплой, и не
   пушить без явного разрешения.
5. На второй машине проверить чистое tracked-состояние, затем выполнить
   `git fetch origin` и `git pull --ff-only`.

Если на исходной машине остались незакоммиченные изменения, переключение не
завершено. Не начинай ту же задачу на второй машине без решения владельца.

## Команды владельца и релиз

- `проверь`, `разберись`, `подготовь` — без commit, push, deploy и restart.
- `зафиксируй` — commit только в текущем development checkout, без push.
- `выкатывай`, `опубликуй`, `закоммить и пушни main` — можно push в `main`,
  дождаться `.github/workflows/deploy-oracle.yml` и проверить production `/health`.

Любой push в `main` считается production-деплоем. После push не редактируй
production checkout и дождись окончания GitHub Actions. Никогда не выполняй
force-push, rebase общей `main`, `git reset --hard` или `git clean` без отдельного
явного разрешения владельца.

## Данные, секреты и опасные операции

- Не читай, не печатай, не копируй и не коммить `.env`, ключи, токены,
  авторизационные файлы и production-конфигурацию.
- Production SQLite corpus не обновляется обычным code deploy. Синхронизация,
  backup, promotion, rollback и миграции БД — отдельная операция с отдельным
  разрешением владельца и профильным runbook.
- Не добавляй в commit базы данных, backups, логи, временные результаты,
  `review/` и случайные локальные файлы.
- Все запросы к данным эксперта должны сохранять изоляцию по `expert_id`.
- Не выдавай синтез модели за источник: ответы продукта должны оставаться
  привязанными к реальным материалам экспертов.

## Проверки

Выбирай минимальные проверки по затронутому scope:

- backend: релевантные тесты из `backend/tests/`;
- frontend: `npm run type-check`, релевантный `npm run test:run`, при необходимости
  `npm run build` из `frontend/`;
- Reddit proxy: команды из `services/reddit-proxy/README.md`.

Не запускай весь тяжёлый набор автоматически. Перед отчётом снова покажи
`git status` и явно перечисли: что изменено, что проверено, что не проверено и
требуется ли commit, push, deploy или отдельное обновление production DB.
