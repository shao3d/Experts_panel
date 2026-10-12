# Scout: переключение дефолт-движка на GLM-5.3 Flash и чек-лист ответов

Дата: 2026-10-12. Решения владельца: внедрить GLM-5.3 Flash вместо Sol в
обычный и веб-контур Скаута; Sol-путь оставить как есть (только явный
оверрайд, модельный ID не менять). SSOT рантайма: `docs/guides/expert-scout.md`.

## Контекст: Sol-инцидент

Headless Codex на VM отвечает 400: «The 'gpt-6.1-sol' model is not supported
when using Codex with a ChatGPT account». Модель `gpt-6-astra` (дефолт
`~/.codex/config.toml`) отвергается так же; дефолтная модель CLI без
`--model` работает. Проверено тремя путями: runtime-wrapper, стенд, прямой
`codex exec`. Последние успешные Sol-прогоны Скаута — 2026-10-10
(`output/scout_runs/20261010-*`). Причина на стороне Codex/OpenAI; модельный
ID Sol-пути не менялся по решению владельца.

## Что сделано

- Движок `glm` в `scripts/expert_scout.sh`: headless OpenCode, агент
  `.opencode/agents/expert-scout.md`, модель `commandcode/z-ai/glm-5.3-flash`
  (ID переопределяется `EXPERT_SCOUT_MODEL`).
- Профиль `glm` в `backend/scripts/benchmark_scout_models.py`; профиль
  `runtime` теперь честно проверяет дефолт wrapper (OpenCode), `sol` — явный
  профиль.
- Веб-контур `scripts/scout_web_api.py` переведён на `glm`;
  `scout-web.service` перезапущен без активных джоб, health
  `{"status":"ok"}`.
- Дефолт wrapper `EXPERT_SCOUT_ENGINE:-glm`; `sol`/`bunny` — только явные
  оверрайды. `agent_probe.py` (дефолт `runtime`) идёт через дефолт wrapper.
- Промпт агента дополнен механическим чек-листом: ключ только после полного
  `show` (включая `lesson_search`), кавычки только для дословных цитат,
  служебные формулировки и списки запросов без кавычек.
- SSOT-гайд, repo-skill `.codex/skills/expert-scout/SKILL.md`, AGENTS.md и
  установленные skill-копии обновлены.

## Результаты стенда (GLM, 7 кейсов)

| Версия | telegram_control | negative_control | old_craft | exact_prompts | compare_authors | scoped_video | false_premise |
|---|---|---|---|---|---|---|---|
| r1 (до чек-листа) | partial (2 цитаты) | partial (5 unread) | completed | completed | partial (1 цитата) | partial (1 цитата) | completed |
| r2 (чек-лист) | completed | partial (1 unread) | completed | completed | completed | completed | — |
| r3 (+`lesson_search` в запрет) | — | partial ×2 (кавычки 1 и 6) | — | — | — | — | — |
| r4 (кавычки вычищены из примеров промпта) | — | completed / partial (absence без `show`) | — | — | — | — | — |

Итог серии: **6 из 7 кейсов дали зелёный прогон** под усиленным промптом.
Во всех прогонах `missing=0` (нет выдуманных ключей), зацикливаний нет,
длинные чтения полные (53/53, 20/20, 10/10). Отрицательный контроль
`negative_control` остаётся флаки: 1 из 5 повторов чистый; сбои только
формата/протокола (кавычки у служебных фраз, absence-ответ без `show`),
ответы по смыслу честные. Историческая планка Sol на этом же наборе — 7/7
(серия 2026-09-30), Bunny — 1/7. Live Sol-baseline в этой серии невозможен
(см. инцидент выше).

Скорость GLM: 68–364 с на прогон (Sol исторически 24–40 с; самый долгий
`compare_authors` — 23 вызова инструмента). Расход квоты GOAT — копеечный.

## Проверки

- `pytest`: 26 passed, 1 skipped (wrapper + benchmark, включая новый тест
  дефолта wrapper = glm); 45 passed (expert_scout + evidence).
- Живой прогон wrapper без env: `engine=glm`, модель в `meta.txt`
  `commandcode/z-ai/glm-5.3-flash`, ответ верный.
- Сервис: рестарт без активных джоб, health `{"status":"ok"}`.

## Ограничения

- `negative_control` флаки; повторы публиковать отдельно, не заменяя ими
  неудачные результаты.
- Веб-прогресс: стриминг событий был заточен под Codex; у GLM остаются
  статусы «Подключаю Скаута…» и «Проверяю ответ и источники…».
- Полный e2e веб-API не прогонялся (пароль хранится только как хэш); путь
  подтверждён кодом, рестартом и health.
- Аудит путей вызова (2026-10-12): Sol вызывается только при явном
  `EXPERT_SCOUT_ENGINE=sol` или `benchmark --engine sol|luna`; cron/таймеры
  Скаут не вызывают; unit сервиса движок не задаёт.

## Артефакты

- `output/scout_model_compare_20261012/` — r1 + мгновенные сбои Sol (400).
- `output/scout_model_compare_20261012_r2/`, `_r3/`, `_r4/` — итерации
  чек-листа. JSON + логи каждого кейса.
- Run-артефакты wrapper: `output/scout_runs/<timestamp>/`.
