# OpenCode 2: миграция контура Скаута (2026-10-14)

## Что случилось

VM `oracle-work` переведена с OpenCode 1.19.0 на **OpenCode 2.0.29**
(`opencode upgrade --major`; флаг появился только в 1.19.0+). V2 намеренно
ломает совместимость плагинов: v1-реализация `.opencode/plugins/expert-scout-tools.ts`
в V2 не запускается — Скаут теряет инструмент `scout` молча, без ошибки апгрейда
(обнаружено контрольным прогоном 2026-10-13, тогда VM откатили на 1.19.0).

## Изменения

1. **Плагин переписан под V2** (`.opencode/plugins/expert-scout-tools.ts`):
   `Plugin.define` + `ctx.tool.transform`, схема аргументов — JSON Schema,
   `execute` возвращает `{ content }`. Guard по агенту сохранён
   (`context.agent === "expert-scout"`); директория проекта захватывается в
   `setup` (`ctx.location.directory`) — в V2 контекст execute её больше не отдаёт.
   Обязательно `options: { codemode: false }`: дефолтный Code Mode V2 оборачивает
   вызовы в generic `execute`-евенты с JS-кодом, integrity-чекер не видит
   `show`-вызовы и помечает все ключи как непрочитанные (ложный partial).
   Подключён пакет `@opencode/plugin@2.0.29` (`.opencode/package.json`).
2. **Терминальное событие потока.** В V2 `run --format json` заканчивается
   финальным text-евентом без `turn.completed`/`step_finish(reason=stop)` —
   integrity помечает чистые прогоны как `unfinished_run`. Хелпер
   `ensure_turn_completed()` в `backend/src/utils/scout_evidence.py` дописывает
   синтетический `turn.completed` для потоков, завершившихся непустым ответом;
   убитые/упавшие прогоны остаются незавершёнными. Вызывается из wrapper
   (`scripts/expert_scout.sh`, только при `ENGINE_EXIT=0`) и из стенда
   (`backend/scripts/benchmark_scout_models.py`, с guard-ом на eval-timeout).
   Потоки V1 проходят без изменений.
3. **MCP-адаптер Sol-профиля** (`scripts/expert_scout_mcp.ts`) импортировал
   v1-экспорт плагина — переписан под V2 (фальш-контекст `setup`, схема берётся
   из `tool.input` как JSON Schema, unwrap `{ content }`). Сам движок Sol
   остаётся сломанным на стороне Codex API (см. 2026-10-12), это не трогалось.

## Стенд (engine=glm, 2026-10-14)

| Кейс | Результат |
|---|---|
| telegram_control | completed (122s, 8 вызовов, 8/8 источников прочитаны) |
| negative_control | partial — 3 unread; исторический флаки (формат/протокол), не регрессия |
| old_craft | completed |
| exact_prompts | 1-й прогон partial (1 неверифицируемая цитата), повтор ×2 — completed |
| compare_authors | completed |
| scoped_video | 1-й прогон partial (1 неверифицируемая цитата), повтор ×2 — completed |
| false_premise | completed |

Соответствует базлайну r2 (6/7 зелёных, `negative_control` флаки). Смысловые
ответы, чтение источников и цитирование не деградировали. Ростер-смоук: 8s,
1 tool call, профиль статусов идентичен v1.19.0.

## Проверено

- Ростер-смоук через wrapper; полный стенд; повторы `exact_prompts`/`scoped_video`.
- MCP-адаптер: JSON-RPC `initialize`/`tools/list`/`tools/call(experts)` через bun.
- Панель `:8000/health` — healthy; `scout-web.service` активен (контуры вызывают
  тот же wrapper на каждый запрос, рестарт не требуется).

## Откат

V1 для linux-arm64 в npm-канале V2-апгрейдера нет; откат — официальным
инсталлером с пином версии: `curl -fsSL https://opencode.ai/install | bash -s 1.19.0`
и `git revert` этого коммита. Код V1 плагина сохранён в истории git.
