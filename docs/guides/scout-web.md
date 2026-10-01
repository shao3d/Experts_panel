# Веб-Скаут

Status: Active
Last updated: 2026-10-01

Минимальная страница: https://shao3d.github.io/scout-web/.
Пароль → вопрос → один текущий этап с временем → ответ со ссылками.
Кнопка поиска во время работы становится кнопкой остановки. Каждый вопрос
независимый; обновление страницы восстанавливает последний поиск.

## Устройство

```text
GitHub Pages (scout-web/)
  → HTTPS expa.beyondhorizon.dev/scout-api
  → Caddy → scout-web.service на VM, dev checkout
  → scripts/expert_scout.sh
  → существующий Скаут и проверка источников
```

Поиск, модель и область по умолчанию описаны в [Expert Scout](expert-scout.md).
Веб-интерфейс не добавляет второй поисковый pipeline. API запускает штатный
CLI из `dev`; production DB не используется. Wrapper сохраняет прежнее
поведение для обычного CLI. Веб-вызов включает `SCOUT_WEB_PROGRESS=1` и
прокси `scripts/scout_web_progress.py`: этапы приходят из реальных событий
вызова инструментов и финальной проверки, без рассуждений модели.

Frontend: HTML, CSS, JavaScript, без сборщика и фреймворка. Оформление по
просьбе владельца взято из papa_wisdom_bot: тёплый тёмный фон, кремовый текст,
янтарные акценты, Cormorant Garamond/Literata/Golos Text. Google Fonts загружаются
в браузере; системные шрифты служат запасными. Markdown разбирает vendored
Marked 18.0.14 (MIT), HTML очищает DOMPurify 3.4.16 (Apache-2.0 или MPL-2.0).
Лицензии лежат в `scout-web/vendor/`. HTML ответа не считается доверенным.

## API и доступ

`scripts/scout_web_api.py`: FastAPI/Uvicorn из существующего backend venv.
На сервере хранится только SHA-256 проверка отдельного длинного пароля,
`SCOUT_WEB_PASSWORD_HASH` в `/home/ubuntu/.config/scout-web/access.env`, режим 600.
Не использовать короткий или повторно используемый пароль. Проверка удаляется
из окружения дочернего Скаута. В Git и frontend пароль не попадает.
Браузер держит пароль в sessionStorage этой вкладки; идентификатор последнего
поиска — в localStorage. Публично доступен только `/health`; остальные маршруты
требуют `X-Scout-Password`. CORS разрешает только `https://shao3d.github.io`.

Маршруты относительно `/scout-api`: `GET /health`, `GET /auth`, `POST /jobs`
с `{"question":"..."}`, `GET /jobs/{id}`, `DELETE /jobs/{id}`.
Страница опрашивает состояние раз в секунду. Один активный поиск на весь
сервис; второй получает 409. Вопрос ограничен 6000 символами, существующий
CLI ограничивает время работы. Остановка завершает группу процессов.

Результаты хранятся в игнорируемом `output/scout_web/`, максимум 20 записей.
Рестарт помечает незавершённый поиск ошибкой, без автоматического повтора.
`completed` означает успешное завершение CLI и его проверки; `partial`
показывается явно, без обещания полного подтверждения. История в интерфейсе
и очереди задач отсутствуют.

## Публикация

Источник страницы — папка `scout-web/` в основном репозитории. Репозиторий
`shao3d/scout-web` — только публикуемое зеркало этой папки, без ручных правок.
После проверок и разрешённого commit/push `main` выполнить:

```bash
scripts/publish_scout_web.sh
```

GitHub Pages настроен на корень ветки `main` зеркала. Дождаться успешной сборки
Pages и проверить страницу; основного code deploy — workflow и `/health`.
Для изменения API установить unit из `scripts/scout-web.service`, выполнить
`systemctl daemon-reload` и `systemctl restart scout-web`. Unit запускает dev
venv с адресом `172.18.0.1:8766` (gateway сети `experts-panel_default`).
Смена Docker сети требует согласовать этот адрес в unit и Caddy.

В `/home/ubuntu/apps/experts-panel/Caddyfile` внутри существующего сайта:

```caddy
handle_path /scout-api/* {
    reverse_proxy 172.18.0.1:8766
}
handle {
    reverse_proxy panel:8000
}
```

Проверить конфигурацию Caddy перед reload; проверить публичный API health,
401 без пароля, вход, реальный поиск с прогрессом и остановку. Это отдельный
code release: обновление БД не требуется.

## Проверки

```bash
backend/.venv/bin/python -m pytest scripts/tests/test_scout_web.py -o addopts='' -q
node --check scout-web/app.js
```

`scout-web/tests/browser.cjs` проверяет desktop/mobile через Playwright:
вход, поиск, прогресс, восстановление, остановку, безопасный Markdown и ссылки.
Задаётся `PLAYWRIGHT_MODULE` с путём к установленному Playwright;
`SCOUT_PAGE` необязательно меняет URL страницы. API в этом тесте подменён,
поэтому дополнительно нужен один живой прогон через штатный wrapper.
