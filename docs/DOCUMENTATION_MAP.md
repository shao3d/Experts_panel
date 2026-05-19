# Карта Документации

Status: Active
Last updated: 2026-05-20

Это навигационный слой проекта Experts Panel. Он должен отвечать на вопрос
"куда смотреть?", а не пересказывать содержимое всех документов.

## Новый Чат

В новом чате по проекту начинай так:

1. Открой этот файл.
2. Выбери маршрут по таблице ниже.
3. Читай только нужные SSOT-документы.
4. Для текущего статуса, деплоя, CLI и БД проверяй код/команды, а не память.

## Быстрые Маршруты

| Задача | Сначала читать | Потом, если нужно |
| --- | --- | --- |
| Общая архитектура / pipeline | `docs/architecture/pipeline.md` | `CLAUDE.md`, `backend/CLAUDE.md` |
| Retrieval / Embs&Keys / FTS5 | `docs/architecture/super-passport-search.md` | `hybrid_retrieval_plan.md` как историю |
| Панэкс как пользователь/оператор | `docs/guides/panex-usage.md` | `panex guide` |
| Панэкс API / CLI / subagent | `docs/architecture/agent-context-api.md` | agent files ниже |
| Новый эксперт / матрица знаний | `docs/architecture/expert-admission-control.md` | `output/expert_admission/admission_manifest.json` |
| Текущий roster экспертов | `docs/architecture/current-expert-roster.md` | `frontend/src/config/expertConfig.ts`, `expert_metadata` |
| Добавить/удалить эксперта | `docs/guides/add-expert.md` | `scripts/add_new_expert.sh`, `scripts/update_production_db.sh` |
| Drift analysis | `docs/guides/drift-analysis.md` | drift scripts in `backend/scripts/` |
| Video Hub | `docs/architecture/video-hub-service.md` | `docs/guides/video-hub-operator.md` |
| Reddit sidecar | `docs/architecture/reddit-service.md` | service code under `services/reddit-proxy/` |
| Backend runtime / health / CLI bootstrap | `docs/roadmap/backend-runtime-cleanup.md` | `backend/CLAUDE.md` |
| Frontend layout/state | `frontend/CLAUDE.md` | frontend source files |

## Правила Навигации

- `docs/architecture/*` - системное поведение и design constraints.
- `docs/guides/*` - операторские команды и процедуры.
- `docs/quality/*` - рубрики и dogfood evidence.
- `output/expert_admission/*` - generated artifacts, не ручная документация.
- `docs/archive/*` - только история; не использовать как current SSOT.

## Главные SSOT

| Файл | Зачем |
| --- | --- |
| `.gemini/GEMINI.md` | Project-level AI operating prompt. Это не подробная архитектурная спека. |
| `docs/architecture/pipeline.md` | Главный backend pipeline: Map, Resolve, Reduce, Reddit, Video, Meta-Synthesis, SSE, durable UI delivery. |
| `docs/architecture/super-passport-search.md` | Hybrid retrieval: Vector KNN, FTS5, RRF, AI Scout, punctuation hardening. |
| `docs/architecture/current-expert-roster.md` | Актуальный roster, UI-группы, source-of-truth caveats. |
| `CLAUDE.md` | Root project guide and repo-level operating notes. |
| `backend/CLAUDE.md` | Backend services, commands, config, runtime notes. |
| `frontend/CLAUDE.md` | Frontend structure, state, layout conventions. |

## Панэкс

Для обычного использования Панэкса читай `docs/guides/panex-usage.md`.

Текущая краткая модель:

- explicit-only: Панэкс вызывается только по явной просьбе;
- default response: backend `expert_digest`;
- raw/audit mode: только явно через `source_bundle`;
- exact source reveal: `panex expand`;
- real calls: `--save --receipt-json`;
- wide delivery: `--all`, `--group`, или `--experts` с 6+ experts;
- wide результат сохраняется artifact-first и читается через `panex read` / `panex export`;
- external links в постах - references-only, без auto-fetch.

Agent instruction files:

- Codex repo-local: `.codex/agents/experts_panel_researcher.toml`
- Claude repo-local: `.claude/agents/experts_panel_researcher.md`
- Codex global: `/Users/andreysazonov/.codex/agents/experts_panel_researcher.toml`

Если меняется поведение Панэкса, синхронизируй repo-local и global Codex agent.
Global copy живёт вне git.

## Expert Admission / Knowledge Matrix

SSOT: `docs/architecture/expert-admission-control.md`.

Короткая доктрина:

- semantic passport даёт ценностно-смысловой профиль эксперта;
- knowledge matrix даёт карту покрытия и стартовую механическую рекомендацию;
- overlap/gap зона не решается чисто механически;
- при сильных overlap нужен LLM/human semantic review по источникам;
- не переусложнять служебкой: держать паспорт, матрицу, report/verdict и понятный artifact trail.

Generated artifacts:

| Artifact | Зачем |
| --- | --- |
| `output/expert_admission/admission_manifest.json` | Кто принят в матрицу и где лежат паспорта/reports. |
| `output/expert_admission/knowledge_matrix/knowledge_matrix.md` | Человеческая версия матрицы. |
| `output/expert_admission/knowledge_matrix/knowledge_matrix.json` | Машинная версия матрицы. |
| `output/expert_admission/current_coverage.md` | Snapshot покрытия и caveats по данным. |
| `output/expert_admission/semantic_passports/<expert>/...` | Паспорта экспертов. |
| `output/expert_admission/candidates/<expert>/...` | Admission reports и impact/arbitration artifacts. |

Generated artifacts лучше регенерировать скриптами, а не править руками.

## Operator Guides

| Файл | Когда читать |
| --- | --- |
| `docs/guides/add-expert.md` | Добавление/удаление эксперта, DB/embedding/Fly sync. |
| `docs/guides/panex-usage.md` | Как пользоваться Панэксом из чата или CLI. |
| `docs/guides/drift-analysis.md` | Проверка тематического drift. |
| `docs/guides/ab-testing-super-passport.md` | A/B MapReduce vs Hybrid Retrieval. |
| `docs/guides/video-hub-operator.md` | Операторский Video Hub workflow. |
| `docs/guides/add-video.md` | Короткий flow добавления видео. |

## Quality Docs

| Файл | Роль |
| --- | --- |
| `docs/quality/panex-product-quality-rubric.md` | Рубрика качества ответа Панэкса. |
| `docs/quality/panex-product-quality-dogfood-2026-05-07.md` | Product-quality dogfood snapshot. |
| `docs/quality/panex-selector-expansion-dogfood-2026-05-07.md` | Selector expansion dogfood snapshot. |
| `docs/quality/panex-portable-runner-dogfood-2026-05-07.md` | Portable runner dogfood snapshot. |

Quality docs - evidence snapshots and guardrails, not current API specs.

## Concepts, Roadmap, Archive

| Файл/папка | Статус |
| --- | --- |
| `docs/concepts/ai-architect-mode.md` | Product concept, not runtime behavior. |
| `docs/roadmap/video-hub-scaling.md` | Active scaling roadmap for larger Video Hub usage. |
| `docs/roadmap/scout-next-steps.md` | Historical metadata-enrichment plan; removed phases are not active. |
| `hybrid_retrieval_plan.md` | Historical implemented plan; current retrieval SSOT is `super-passport-search.md`. |
| `docs/archive/*` | Historical only. Do not route new implementation from archive docs. |

## Update Checklist

| Change | Update |
| --- | --- |
| Pipeline/model/SSE/final delivery | `docs/architecture/pipeline.md`; maybe `CLAUDE.md`, `backend/CLAUDE.md` |
| Hybrid search / embeddings / FTS5 / Scout | `docs/architecture/super-passport-search.md`; maybe `pipeline.md` |
| Панэкс CLI/API/subagent behavior | `docs/guides/panex-usage.md`, `docs/architecture/agent-context-api.md`, repo-local agent files, global Codex agent |
| New env var | `.env.example`, `backend/CLAUDE.md`, relevant architecture doc |
| Expert roster/groups | `docs/architecture/current-expert-roster.md`, `docs/guides/add-expert.md`, frontend config if UI changes |
| Expert admission doctrine / matrix workflow | `docs/architecture/expert-admission-control.md`; this map only if navigation changes |
| Add/remove expert scripts | `docs/guides/add-expert.md` |
| Video Hub behavior | `docs/architecture/video-hub-service.md`, `docs/guides/video-hub-operator.md` |
| Reddit behavior | `docs/architecture/reddit-service.md`; maybe `CLAUDE.md` |
| Frontend layout/state | `frontend/CLAUDE.md` |
| Backend runtime/health/CLI bootstrap | `docs/roadmap/backend-runtime-cleanup.md`, `backend/CLAUDE.md` |

If a file or command is removed, run `rg` over Markdown docs for stale
references and update only real hits.
