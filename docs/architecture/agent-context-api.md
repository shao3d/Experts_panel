# Agent Context API Spec

**Status:** Accepted / AND-5 + AND-6 + AND-7 + AND-8 + AND-9 + AND-10 + AND-11 + AND-12 + AND-13 + AND-14 + AND-15 implemented / forced embedding search implemented
**Decision:** `.haft/decisions/dec-20260504-b2539c3d.md`
**Last updated:** 2026-05-05

This spec defines the first agent-facing surface for Experts Panel: an explicit-only research/context API for Codex, Claude Code, and similar coding/research agents.

---

## 0. Implementation Status

Current state as of 2026-05-05:

| Slice | Status | What it means |
|-------|--------|---------------|
| AND-5 authenticated endpoint skeleton | Done | `POST /api/v1/agent/context` exists, uses a separate bearer token, has request validation, timeout, response-size limit, and in-process per-token rate limiting. |
| AND-6 real `source_bundle` pipeline | Done | The endpoint now returns selected source bundles instead of the placeholder `experts=[]` response. It runs retrieval, Map, MEDIUM scoring, HIGH resolve, source selection, and main-source comment loading. |
| AND-7 local CLI wrapper | Done | `src.cli.agent_context` calls the endpoint over HTTP with safe source-bundle defaults, keeps the token in the Authorization header, supports all/group/custom selection, and prints agent-readable summaries or raw JSON. |
| AND-8 BDD acceptance hardening | Done | In-process CLI -> HTTP -> FastAPI -> `source_bundle` acceptance tests cover explicit expert selection, safe defaults, no full synthesis, source evidence shape, token boundary, and actionable API failures. |
| AND-9 repo-local `experts_panel_researcher` subagent contract | Done | Repo-local Claude and Codex agent instructions exist, stay read-only, require explicit triggers, call the local CLI only, and return practitioner-opinion intelligence using the Signals frame. |
| AND-10 local dogfood for `experts_panel_researcher` | Done | A synthetic source_bundle fixture and dogfood tests verify that CLI JSON is synthesis input, local readiness failures are actionable, defaults stay local, and the six-section Signals frame is usable before production exposure. |
| AND-11 live local dogfood smoke | Done | `backend/scripts/agent_context_live_smoke.py` can preflight local readiness, start Experts Panel on a free localhost port, call the CLI with explicit `--api-url`, validate `source_bundle`, and write a sanitized report with `passed`/`skipped`/`failed` status. |
| AND-12 paid local live smoke | Done | Paid local smoke passed with the default `refat,akimov` query and returned a valid real `source_bundle`. Runtime defaults are intentionally large (`3600s` / `100000000` bytes) because all-expert source-bundle requests are naturally long and bulky. |
| AND-13 bounded expert parallelism | Done | Agent Context now inherits the main pipeline's bounded expert parallelism pattern: selected experts run as async tasks behind `MAX_CONCURRENT_EXPERTS`, while response order stays aligned to the requested expert order. |
| AND-14 all-experts paid local smoke | Done | Paid local smoke passed for the full MVP Telegram roster (`17` experts, no `video_hub`) with bounded parallelism, no warnings, and a `7.46MB` source_bundle response after forced Embs&Keys retrieval. |
| AND-15 production Fly smoke mode | Done | `backend/scripts/agent_context_live_smoke.py` has an explicit external mode via `--api-url`; without that flag it still starts a local backend and ignores ambient `AGENT_CONTEXT_API_URL` to avoid accidental Fly calls. Production smoke passed on Fly with a separate production token for `refat,akimov`. |
| Forced embedding search for Agent Context | Done | Agent Context always forces Embs&Keys hybrid retrieval: CLI sends `use_super_passport=true`, API records `selection_used.use_super_passport=true`, and service prepares one query embedding for all selected experts before bounded parallel expert processing. UI toggle state does not apply to subagent/API calls. |
| Production Fly exposure | Done for explicit smoke | `https://experts-panel.fly.dev/api/v1/agent/context` is callable with the separate production bearer token and large source-bundle budgets. The repo-local subagent default remains local; production calls must stay explicit. |

Implemented code paths:

- `backend/src/api/agent_context_endpoint.py`
- `backend/src/services/agent_context_service.py`
- `backend/src/services/simple_resolve_service.py`
- `backend/src/api/models.py`
- `backend/src/cli/agent_context.py`
- `backend/tests/test_agent_context_acceptance.py`
- `backend/tests/test_agent_context_api.py`
- `backend/tests/test_agent_context_cli.py`
- `backend/tests/test_experts_panel_researcher_contract.py`
- `backend/tests/test_experts_panel_researcher_dogfood.py`
- `backend/tests/test_agent_context_live_smoke.py`
- `backend/tests/fixtures/experts_panel_researcher_source_bundle_sample.json`
- `backend/scripts/agent_context_live_smoke.py`
- `.claude/agents/experts_panel_researcher.md`
- `.codex/agents/experts_panel_researcher.toml`

Verified checks:

```text
backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py -q -o addopts=''
# 16 passed

backend/.venv/bin/python -m pytest backend/tests/test_experts_api.py -q -o addopts=''
# 1 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_cli.py -q -o addopts=''
# 10 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_acceptance.py -q -o addopts=''
# 6 passed

backend/.venv/bin/python -m pytest backend/tests/test_experts_panel_researcher_contract.py -q -o addopts=''
# 8 passed

backend/.venv/bin/python -m pytest backend/tests/test_experts_panel_researcher_dogfood.py -q -o addopts=''
# 6 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_live_smoke.py -q -o addopts=''
# 13 passed

cd backend && .venv/bin/python scripts/agent_context_live_smoke.py --require-live
# passed: source_bundle_valid
# selection_used.use_super_passport: true
# selected_source_counts: refat=42, akimov=67
# response_bytes: 1081305
# processing_time_ms: 57321
# no lingering local backend process observed after helper shutdown

cd backend && .venv/bin/python scripts/agent_context_live_smoke.py --require-live --experts ai_architect,neuraldeep,ilia_izmailov,polyakov,etechlead,glebkudr,ostrikov,pashazloy,ai_grabli,refat,akimov,llm_under_hood,elkornacio,doronin,air_ai,silicbag,kornish
# passed: source_bundle_valid
# experts: 17
# selection_used.use_super_passport: true
# selected_source_counts: ai_architect=10, neuraldeep=10, ilia_izmailov=6, polyakov=31, etechlead=41, glebkudr=3, ostrikov=38, pashazloy=30, ai_grabli=7, refat=68, akimov=32, llm_under_hood=31, elkornacio=41, doronin=66, air_ai=9, silicbag=60, kornish=14
# response_bytes: 7462364
# processing_time_ms: 275622
# warnings: []
# no lingering local backend process observed after helper shutdown

cd backend && AGENT_CONTEXT_API_TOKEN=<production token> .venv/bin/python scripts/agent_context_live_smoke.py --require-live --api-url https://experts-panel.fly.dev/api/v1/agent/context --experts refat,akimov --timeout 3600
# passed: source_bundle_valid
# target_mode: external
# selected_source_counts: refat=54, akimov=53
# response_bytes: 1125055
# processing_time_ms: 40473
# warnings: []

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py backend/tests/test_experts_api.py backend/tests/test_agent_context_cli.py backend/tests/test_agent_context_acceptance.py backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_experts_panel_researcher_dogfood.py backend/tests/test_agent_context_live_smoke.py -q -o addopts=''
# 60 passed, 2 warnings

git diff --check
# clean
```

CLI usage:

```text
cd backend
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --experts refat,akimov
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --group tech
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --json
```

Important boundary: production Fly exposure is proven only for an explicit
manual `refat,akimov` smoke. It does not make Fly the default subagent target,
does not prove all-experts production runtime, and does not build a Reddit
source packet or Video Hub source-bundle adapter.

---

## 1. Goal

Experts Panel should be callable by AI agents only when Andrey explicitly asks for it.

The first product surface is not a full public platform, not a full MCP server, and not the current UI answer pipeline exposed as-is. It is a thin authenticated REST endpoint that returns a source-backed evidence packet under a selected expert scope.

Target shape:

```text
Andrey
  -> "Спроси Панель Экспертов по Refat и Akimov..."

Main Codex / Claude Code
  -> calls explicit-only experts_panel_researcher

experts_panel_researcher
  -> POST /api/v1/agent/context
  -> response_mode = "source_bundle"

Experts Panel
  -> partial source discovery pipeline
  -> selected sources + comments under those sources
  -> structured context packet
```

## 2. Non-Goals

Do not build these in the first slice:

- public anonymous API;
- automatic background calls from the main Codex/Claude Code agent;
- full MCP server as the first transport;
- full AI Architect workflow API;
- dumping all posts for selected experts;
- running the entire `/api/v1/query` UI/SSE answer pipeline by default;
- drift comment group scoring by default;
- comment synthesis by default;
- cross-expert meta-synthesis by default;
- admin/import/data mutation operations.

## 3. Invocation Model

The integration must be explicit-only.

Allowed triggers:

- "Спроси Панель Экспертов ..."
- "вызови experts_panel_researcher ..."
- "/experts ..."
- "проверь через Experts Panel ..."

Forbidden behavior:

- main agents must not query Experts Panel just because a task is about trends, software, market analysis, or architecture;
- main agents must not treat Experts Panel as default web search;
- the API token must not be exposed to broad agents if a narrower subagent/wrapper can hold it.

Recommended local tooling:

```text
experts_panel_researcher
  - read-only
  - explicit-only
  - owns the API token/wrapper
  - parses expert selection
  - requests source_bundle
  - returns practitioner-opinion intelligence, not proof claims
  - uses the Signals frame:
    1. Query and selection
    2. Source-backed signals
    3. Expert positions
    4. Convergence / divergence
    5. Practical application
    6. Limits and missing evidence
```

The subagent must not present practitioner posts as proven facts. It should
separate what the selected sources explicitly say, how different experts frame
the topic, where sources converge or diverge, what practical interpretation is
reasonable for the user's query, and what remains weak, missing, stale,
indirect, or unsupported.

Optional shortcut:

```text
/experts <query>
```

MCP can be added later as an adapter over the same internal service after the REST/source bundle contract is proven.

## 4. Expert Selection

Use one subagent with parameterized expert selection. Do not create separate subagents per expert or group.

Supported selection modes:

| User phrase | API interpretation |
|-------------|--------------------|
| "по всем" / no subset | `expert_scope = "all"`, `expert_filter = null` |
| "по технарям" / "Tech" | `expert_scope = "group"`, `expert_group = "tech"` |
| "по бизнесовым" / "Tech & Business" | `expert_scope = "group"`, `expert_group = "tech_business"` |
| "по видео" / "Video Hub" | `expert_scope = "custom"`, `expert_filter = ["video_hub"]` |
| named experts | `expert_scope = "custom"`, `expert_filter = [...]` |
| "только Reddit/community" | `expert_scope = "none"`, `include_reddit = true` |

The current active roster source is `docs/architecture/current-expert-roster.md`.

MVP boundary:

- `all` means all active Telegram-sync experts from Tech and Tech & Business.
- `video_hub` is a separate Knowledge Hub source and should be queried only when the user explicitly asks for video/video_hub, or when a later implementation adds a tested video source_bundle adapter.
- Do not silently add `video_hub` to normal "по всем экспертам" calls in the first implementation slice.

Backend implementation must not import frontend TypeScript config. Define an explicit backend group map for MVP and keep it covered by tests:

```python
AGENT_CONTEXT_EXPERT_GROUPS = {
    "tech": [
        "ai_architect",
        "neuraldeep",
        "ilia_izmailov",
        "polyakov",
        "etechlead",
        "glebkudr",
        "ostrikov",
        "pashazloy",
    ],
    "tech_business": [
        "ai_grabli",
        "refat",
        "akimov",
        "llm_under_hood",
        "elkornacio",
        "doronin",
        "air_ai",
        "silicbag",
        "kornish",
    ],
}
```

`all` for MVP is `tech + tech_business`, filtered to experts that exist in runtime data. If any configured expert has no runtime data, return a warning rather than failing the whole request.

Every response must include `selection_used`, so the caller can see exactly what was queried.

If a user names an unknown or ambiguous expert, the subagent must ask one clarification before calling the API.

## 5. API Endpoint

First endpoint:

```http
POST /api/v1/agent/context
Authorization: Bearer <agent token>
Content-Type: application/json
```

### Request

```json
{
  "query": "Что Refat и Akimov писали про AI agents для отдела продаж?",
  "response_mode": "source_bundle",
  "expert_scope": "custom",
  "expert_group": null,
  "expert_filter": ["refat", "akimov"],
  "include_reddit": false,
  "include_main_source_comments": true,
  "include_drift_comment_groups": false,
  "synthesis_level": "none",
  "use_recent_only": false,
  "use_super_passport": true
}
```

Field rules:

| Field | Rule |
|-------|------|
| `query` | Natural language query, same user intent as normal query flow. |
| `response_mode` | Default for subagent is `source_bundle`. |
| `expert_scope` | `all`, `group`, `custom`, or `none`. |
| `expert_group` | Required only for `group`. |
| `expert_filter` | Explicit `expert_id` list for `custom`; `null` for `all`. |
| `include_reddit` | Default `false`; enable only when user asks for community/sentiment/fresh external signal. |
| `include_main_source_comments` | Default `true`. |
| `include_drift_comment_groups` | Default `false`; not part of MVP unless explicitly added later. |
| `synthesis_level` | Default `none` for source bundle. Possible future values: `compact`, `deep`. |
| `use_recent_only` | Explicit or auto-derived later; do not silently change without showing it in `selection_used`. |
| `use_super_passport` | Always normalized to `true` for Agent Context. The UI Embs&Keys toggle does not control subagent/API retrieval. |

Validation rules:

- `expert_scope = "group"` requires a known `expert_group`.
- `expert_scope = "custom"` requires a non-empty `expert_filter`.
- `expert_scope = "all"` ignores `expert_filter` and records `expert_filter = null` in `selection_used`.
- `expert_scope = "none"` requires `include_reddit = true`; otherwise return `400`.
- reject unknown `expert_id` values with `400` and a list of unknown IDs.
- reject `include_drift_comment_groups = true` in MVP with `400` or return `501 Not Implemented`; do not silently run drift scoring.
- reject `synthesis_level != "none"` in MVP with `400` or `501`; do not silently run Reduce.
- default `include_reddit = false`, `include_main_source_comments = true`, `include_drift_comment_groups = false`, `synthesis_level = "none"`.
- force `use_super_passport = true` even if a caller sends `false`; Agent Context must use Embs&Keys hybrid retrieval rather than the UI-controlled standard search mode.

## 6. Response Contract

The endpoint returns a bounded evidence packet, not the entire corpus.

```json
{
  "request_id": "req_...",
  "mode": "source_bundle",
  "query": "Что Refat и Akimov писали про AI agents для отдела продаж?",
  "selection_used": {
    "expert_scope": "custom",
    "expert_group": null,
    "expert_filter": ["refat", "akimov"],
    "include_reddit": false,
    "include_main_source_comments": true,
    "include_drift_comment_groups": false,
    "synthesis_level": "none",
    "use_recent_only": false,
    "use_super_passport": true
  },
  "experts": [
    {
      "expert_id": "refat",
      "expert_name": "Refat",
      "channel_username": "nobilix",
      "selected_sources_count": 3,
      "unattached_linked_context": [],
      "main_sources": [
        {
          "telegram_message_id": 123,
          "source_key": "refat:123",
          "source_role": "main",
          "relevance": "HIGH",
          "reason": "Directly discusses workflow-first AI agent adoption in sales.",
          "content": "...",
          "created_at": "2026-04-10T12:00:00",
          "author_name": "Refat",
          "is_original": true,
          "linked_context": [],
          "comments": {
            "author_comments": [],
            "community_comments": []
          }
        }
      ],
      "no_results_reason": null
    }
  ],
  "reddit": null,
  "pipeline_used": [
    "expert_selection",
    "retrieval",
    "map_relevance",
    "medium_scoring_if_needed",
    "resolve_high_sources_if_needed",
    "source_selection",
    "main_source_comments"
  ],
  "pipeline_skipped": [
    "reduce_answer_synthesis",
    "language_validation",
    "drift_comment_group_scoring",
    "comment_synthesis",
    "cross_expert_meta_synthesis",
    "reddit_synthesis"
  ],
  "warnings": [],
  "processing_time_ms": 0
}
```

Error response should use the existing API style where practical:

```json
{
  "error": "invalid_expert_scope",
  "message": "expert_scope='group' requires expert_group.",
  "request_id": "req_..."
}
```

## 7. Source Selection Rule

The system decides how many sources are relevant under the query and expert scope.

Do not impose a product-level `max_sources_per_expert` as the normal selection rule.

Correct behavior:

```text
If the source discovery pipeline selects 2 main_sources for Refat, return 2.
If it selects 7 main_sources for Akimov, return 7.
If it selects 0 for Rinat, return 0 with `no_results_reason`.
```

Safety limits may exist only as hard abuse/transport caps, and if they truncate results the response must say so explicitly:

```json
{
  "truncated": true,
  "truncation_reason": "hard transport safety cap",
  "sources_selected": 40,
  "sources_returned": 25
}
```

Important implementation seam:

- Today, `main_sources` are produced by `ReduceService` after answer synthesis.
- Source bundle mode must not depend on full Reduce.
- Implement a reusable source-selection step before Reduce, for example `AgentSourceSelectionService`.
- Internally, this step may call the result `selected_sources`; the response can expose them as `main_sources` for caller familiarity.
- Existing `/api/v1/query` behavior must remain unchanged.

Initial MVP source selection:

```text
selected_sources = original HIGH posts from Map
                 + selected MEDIUM posts after MediumScoringService
```

Rules:

- include all selected original HIGH posts;
- include all MEDIUM posts that pass the existing medium scoring threshold/top selection;
- do not include LOW posts;
- do not promote linked CONTEXT posts to `main_sources`;
- return linked/resolve context under the selected source as `linked_context` only when explicit provenance proves the association;
- preserve each selected source's `relevance`, `reason`, and optional medium `score` / `score_reason`.

Implementation detail:

- `MapService.process()` returns `relevant_posts`.
- Split `relevant_posts` into HIGH and MEDIUM exactly like `process_expert_pipeline()`.
- `MediumScoringService.score_medium_posts()` already applies `MEDIUM_SCORE_THRESHOLD`, `MEDIUM_MAX_POSTS`, and `MEDIUM_MAX_SELECTED_POSTS`; source_bundle should reuse those config values rather than inventing new limits.
- `SimpleResolveService.process()` returns original selected posts plus linked `CONTEXT` posts in one flat `enriched_posts` list.
- Build stable `source_key` values for original selected sources, for example `{expert_id}:{telegram_message_id}`.
- Main sources are only `is_original = true` selected HIGH/MEDIUM posts.
- Linked context is any `is_original = false` / `relevance = "CONTEXT"` item returned by resolve.
- Linked context must be attached to `main_sources[].linked_context` only through explicit resolve provenance, for example `parent_source_key` or `linked_from_source_keys`.
- Heuristic attachment by date, text similarity, neighboring list position, or channel-level co-occurrence is not allowed in the MVP.
- If one linked CONTEXT post has explicit provenance for multiple selected sources, it may appear under each relevant `linked_context` list with the same stable context id.
- If association cannot be proven from the current data shape, return the item in expert-level `unattached_linked_context` with a warning rather than promoting it to `main_sources`.

This is the first deterministic source_bundle contract. If later quality checks show that Reduce's LLM-selected `main_sources` are materially better, add a narrow selector step instead of re-enabling full answer synthesis.

## 8. Partial Pipeline For `source_bundle`

Default `source_bundle` mode should run a source discovery pipeline:

```text
1. Parse and validate request.
2. Resolve expert scope to expert_id list.
3. Process selected experts with bounded parallelism using `MAX_CONCURRENT_EXPERTS`.
   3.1 Load candidate posts under recent/all filter.
   3.2 Use existing retrieval/relevance logic.
   3.3 Run medium rerank if needed.
   3.4 Resolve HIGH sources if linked context is useful.
   3.5 Select sources for the evidence packet.
   3.6 Load comments under selected sources.
4. Optionally add Reddit source packet if requested.
5. Return source_bundle JSON.
```

Expert execution must follow the same operational shape as the existing
`/api/v1/query` pipeline:

- create one async task per selected expert;
- guard expert work with `asyncio.Semaphore(config.MAX_CONCURRENT_EXPERTS)`;
- keep the response `experts[]` order aligned to the resolved expert order;
- keep per-expert warnings isolated during processing, then merge them into the
  top-level `warnings` list after task completion.

Default `source_bundle` mode should skip:

```text
ReduceService answer synthesis
LanguageValidationService
CommentGroupMapService.score_drift_groups()
CommentSynthesisService
MetaSynthesisService
Reddit synthesis
```

This is intentionally not a set of `skip_*` flags on `/api/v1/query`. It should be a separate endpoint/service path for agent context.

## 9. Comments Policy

Comments under selected main sources are included by default.

Include:

- author comments under selected main source posts;
- community comments under selected main source posts;
- enough metadata to keep comments attached to their anchor post.

The response should normalize existing comment-group loader output into the source shape:

```text
main_source.comments.author_comments
main_source.comments.community_comments
```

Do not return main-source comments as unrelated top-level drift groups in default source_bundle mode.

Implementation detail:

- The existing `CommentGroupMapService.merge_with_main_sources(scored_drift_groups=[], main_source_ids=[...])` can load author/community comments without running drift scoring.
- For a cleaner service boundary, prefer extracting public helper methods rather than calling private `_load_main_source_*` methods directly from the endpoint.
- Preserve comment metadata: `comment_id`, `comment_text`, `author_name`, `created_at`, `updated_at`.

Do not include by default:

- drift comment groups from unrelated posts;
- LLM scoring of drift groups;
- synthesized comment insights.

Reasoning:

- comments under selected sources are direct evidence/context;
- drift groups are a separate expensive research layer;
- Codex/Claude Code needs source material, not a second commentary synthesis, for the default mode.

Future opt-in may add:

```json
{
  "include_drift_comment_groups": true,
  "synthesis_level": "deep"
}
```

This must be treated as a separate cost/latency mode and should not be the default for the subagent.

## 10. Reddit Policy

Default:

```json
"include_reddit": false
```

Enable Reddit only when the user explicitly asks for:

- Reddit;
- community sentiment;
- practitioner feedback;
- fresh external signal;
- comparison/troubleshooting from communities.

If included, return Reddit as a separate block. Do not silently blend Reddit and Telegram expert sources.

```json
{
  "reddit": {
    "query_sent": "...",
    "sources": [],
    "warnings": []
  }
}
```

For MVP, do not require full Reddit synthesis. The agent can use source metadata and snippets.

Implementation detail:

- Do not call the existing full `process_reddit_pipeline()` for default agent source_bundle, because that path is oriented toward UI/community synthesis.
- If Reddit is implemented in MVP, call the lower-level enhanced Reddit search service and return source metadata/snippets only.
- If a source-only Reddit packet is not ready, reject `include_reddit = true` with `501 Not Implemented` rather than silently running full Reddit synthesis.

## 11. Auth, Safety, And Audit

Production exposure requires:

- separate agent API token, not admin secret;
- rate limit per token;
- timeout budget;
- request id;
- structured audit log with query, expert scope, mode, source counts, LLM phases used/skipped, and processing time;
- no secrets in logs;
- no admin/import/maintenance routes reachable through this surface;
- response size guardrails with explicit truncation metadata.

MVP config:

```text
AGENT_CONTEXT_API_TOKEN=<secret>
AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE=10
AGENT_CONTEXT_TIMEOUT_SECONDS=3600
AGENT_CONTEXT_MAX_RESPONSE_BYTES=100000000
```

Add these to `backend/src/config.py` and `.env.example`.

Auth dependency:

- implement a new dependency, for example `verify_agent_context_token`;
- require `Authorization: Bearer <token>`;
- do not reuse `ADMIN_SECRET`;
- if `AGENT_CONTEXT_API_TOKEN` is not configured, return `500`;
- if token is wrong/missing, return `403`;
- never log the token.

Rate limit can start as a simple in-process per-token limiter for MVP, but the response must fail closed when the limit is exceeded (`429`).

Recommended isolation:

```text
main agent
  - no token
  - cannot call endpoint directly

experts_panel_researcher / wrapper
  - owns token
  - explicit-only
  - read-only
```

## 12. Fly.io Deployment Impact

Yes, current Fly.io deployment constraints affect this design.

Current repo config:

- main app `experts-panel`: `shared` CPU, `1` vCPU, `1gb` memory, `auto_stop_machines = 'stop'`, `min_machines_running = 0`;
- Reddit proxy `experts-reddit-proxy`: `shared` CPU, `1` vCPU, `512mb` memory, auto-stop enabled.

Official Fly.io docs state:

- there is no general "free account/free tier"; Fly has Free Trial / possible allowances, and overages are billed;
- started Machines are billed while running;
- stopped/suspended Machines still incur rootfs/volume-related charges;
- auto-stop/auto-start can stop idle Machines and restart them on traffic;
- Fly does not support billing alerts yet, so usage must be budgeted and checked manually.

Design consequences:

1. Default source_bundle must avoid full synthesis phases.
2. Reddit must be opt-in, because it can wake the proxy and add latency/cost.
3. No automatic background calls from Codex/Claude Code.
4. Add hard request timeouts and response size limits.
5. Add per-token rate limits before production exposure.
6. Expect cold starts because `min_machines_running = 0`.
7. First testing can be local-only or low-frequency production smoke, not high-frequency agent usage.
8. If agent use becomes regular, revisit machine size, min running machines, and billing budget.

Practical MVP stance:

```text
Fly free/trial/low-cost deployment is fine for manual explicit calls.
It is not a safe assumption for automatic, frequent, or deep research calls.
```

Official references:

- https://fly.io/docs/about/cost-management/
- https://fly.io/docs/about/billing/
- https://fly.io/docs/about/free-trial/
- https://fly.io/docs/reference/configuration/

## 13. Implementation Plan And Status

### Step 1 - Schema and service contract

Status: **Done in AND-5/AND-6.**

Add request/response models for:

- `AgentContextRequest`
- `AgentContextResponse`
- `SelectionUsed`
- `AgentExpertSourceBundle`
- `AgentMainSource`
- `AgentSourceComments`
- `AgentLinkedContext`
- `AgentContextError`

Expected files:

```text
backend/src/api/models.py
backend/src/api/agent_context_endpoint.py
backend/src/api/main.py
backend/src/api/dependencies.py
backend/src/services/agent_context_service.py
backend/src/config.py
.env.example
docs/architecture/agent-context-api.md
```

### Step 2 - Source selection seam

Status: **Done in AND-6.**

Extract or implement source selection before Reduce:

```text
candidate enriched posts
  -> selected main sources for source_bundle
```

The initial selection can reuse existing Map/HIGH/MEDIUM/Resolve outputs and should be tested against current full pipeline behavior.

Do not modify `process_expert_pipeline()` for this first slice unless extracting shared helper functions. The UI/SSE endpoint should stay behaviorally unchanged.

### Step 3 - Main source comments loader

Status: **Done in AND-6.**

Reuse the existing main-source comment loading logic, but without drift scoring:

```text
selected_source_ids
  -> author comments
  -> community comments
```

Do not call drift scoring or comment synthesis in default source_bundle mode.

### Step 4 - Endpoint

Status: **Done in AND-5 and connected to the real source-bundle service in AND-6.**

Add:

```text
POST /api/v1/agent/context
```

Register as a read-only router.

Route wiring:

```python
from .agent_context_endpoint import router as agent_context_router
app.include_router(agent_context_router)
```

The router should own its `/api/v1/agent` prefix so registration does not double-prefix routes.

### Step 5 - Explicit-only subagent spec

Status: **Done for local usage. CLI wrapper is implemented in AND-7; repo-local Claude and Codex subagent contracts are implemented in AND-9. Production exposure is still pending.**

Before wiring the subagent to production Fly, add a local CLI wrapper around the agent context endpoint. The wrapper is the first supported integration surface for Codex/Claude Code.

Wrapper responsibilities:

- hold the API token outside the broad main-agent prompt;
- target local development by default;
- allow explicit production URL configuration later;
- send `response_mode = source_bundle`;
- send `use_super_passport = true` and rely on the API to force it true even if a caller tries to disable it;
- keep `include_reddit = false`, `include_main_source_comments = true`, `include_drift_comment_groups = false`, and `synthesis_level = none` unless explicitly overridden by the caller;
- print `selection_used`, warnings, and source packet metadata.

Production Fly usage is allowed only after endpoint auth, rate limiting, timeout, response-size limits, and basic request logging are implemented and covered by tests.

Add durable instructions for Codex/Claude Code integration:

- explicit triggers only;
- parse expert selection;
- default `response_mode = source_bundle`;
- print `selection_used`;
- return practitioner-opinion intelligence using the Signals frame:
  `Query and selection`, `Source-backed signals`, `Expert positions`,
  `Convergence / divergence`, `Practical application`,
  `Limits and missing evidence`;
- never present practitioner posts as proven facts;
- never edit repo files;
- never broaden scope silently.

The first subagent lives in repo-local Claude/Codex configuration, next to this spec and the CLI wrapper. A global user-level subagent may be added later only as a stable shortcut after the endpoint and wrapper contract have proven safe.

### Step 5.5 - Local Dogfood

Status: **Done in AND-10 for local contract and manual smoke readiness.**

Local dogfood proves the user-facing workflow before production Fly exposure:

```text
explicit user request
  -> experts_panel_researcher
  -> local CLI with --json
  -> source_bundle JSON
  -> compact Signals frame synthesis
```

The CLI JSON is input for synthesis, not the final answer. The subagent should
not dump raw JSON unless the parent explicitly asks for it.

Dogfood fixture:

```text
backend/tests/fixtures/experts_panel_researcher_source_bundle_sample.json
```

Manual smoke, only when local backend and `AGENT_CONTEXT_API_TOKEN` are
intentionally available:

```text
cd backend
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --experts refat,akimov --json
```

The local backend default remains:

```text
http://localhost:8000/api/v1/agent/context
```

Do not use production/Fly for dogfood unless `AGENT_CONTEXT_API_URL` is
explicitly configured for that later production slice.

Signals frame checklist:

1. Query and selection
2. Source-backed signals
3. Expert positions
4. Convergence / divergence
5. Practical application
6. Limits and missing evidence

Failure handling:

- missing `AGENT_CONTEXT_API_TOKEN`: explain that the local token must be configured;
- unreachable local backend: ask to start backend or check `AGENT_CONTEXT_API_URL`;
- `video_hub`/`501`: report unsupported source_bundle adapter;
- unknown expert: ask one clarification before retrying.
- `HTTP 413` / `response_too_large`: report that the source bundle exceeded
  `AGENT_CONTEXT_MAX_RESPONSE_BYTES`.
- `HTTP 504` / `api_timeout`: report that the source-bundle pipeline exceeded
  `AGENT_CONTEXT_TIMEOUT_SECONDS`.
- `cli_timeout`: write a sanitized report instead of surfacing a raw Python
  traceback.

Operational note: Agent Context is a long-running research surface, not a fast
interactive UI endpoint. Keep timeout and response-size limits large enough for
explicit all-expert requests. The current default budget is `3600s` and
`100000000` bytes; callers may still narrow expert selection when they need a
faster, smaller packet.

### Step 5.6 - Live Dogfood Smoke

Status: **Done in AND-11 for preflight + optional live smoke harness. Done in AND-12 for paid local live smoke with raised source-bundle budget. Extended in AND-15 with explicit external/Fly mode.**

Use the live smoke helper when you want a real backend/CLI check.

Default mode is local and does not touch Fly:

```text
cd backend
.venv/bin/python scripts/agent_context_live_smoke.py
```

In default local mode the helper:

- loads `backend/.env`;
- checks `AGENT_CONTEXT_API_TOKEN` without printing the value;
- ignores ambient `AGENT_CONTEXT_API_URL`;
- chooses a free localhost port instead of assuming `8000`;
- starts `uvicorn src.api.main:app`;
- waits for `/health`;
- calls `src.cli.agent_context` with explicit `--api-url`;
- validates `mode = source_bundle`;
- writes a sanitized report to:

```text
backend/test_results/agent_context_live_smoke/latest.json
```

Status meanings:

- `passed`: local token exists, backend starts, and CLI returns valid `source_bundle`;
- `skipped`: local token/readiness is absent and `--require-live` was not used;
- `failed`: backend/CLI returns an unexpected error or invalid response;
- `response_too_large`: the CLI reached the API, but the response exceeded
  `AGENT_CONTEXT_MAX_RESPONSE_BYTES`;
- `api_timeout`: the API returned `504` before completing the source bundle;
- `cli_timeout`: the helper subprocess exceeded its timeout and wrote a
  sanitized failure report.

Use `--require-live` only when missing local readiness should fail the run.

Use explicit external mode only when you intentionally want to call an already
running/deployed backend:

```text
cd backend
.venv/bin/python scripts/agent_context_live_smoke.py \
  --require-live \
  --api-url https://experts-panel.fly.dev/api/v1/agent/context \
  --experts refat,akimov
```

In external mode the helper:

- does not choose a local port;
- does not start local `uvicorn`;
- derives the health-check base URL from `--api-url`;
- waits for external `/health`;
- calls the Agent Context CLI with that explicit API URL;
- writes `target_mode = "external"` into the sanitized report.

### Step 5.7 - Production Fly Smoke

Status: **Done in AND-15 for the first explicit production smoke.**

First production smoke scope is intentionally narrow:

```text
experts = refat,akimov
query = AI agents for sales
api_url = https://experts-panel.fly.dev/api/v1/agent/context
```

Production prerequisites:

- set a separate production `AGENT_CONTEXT_API_TOKEN` in Fly secrets;
- keep `AGENT_CONTEXT_TIMEOUT_SECONDS = 3600`;
- keep `AGENT_CONTEXT_MAX_RESPONSE_BYTES = 100000000`;
- deploy the committed AND-15 helper/API code through the normal Fly path;
- verify `/health`;
- run the explicit external smoke command above.

Measured production result on 2026-05-05:

```text
status = passed
reason = source_bundle_valid
target_mode = external
selected_source_counts = refat=54, akimov=53
response_bytes = 1125055
processing_time_ms = 40473
warnings = []
Fly release = v333
GitHub deploy run = 25389631513, completed success
```

The first attempt was intentionally discarded as non-proof: it ran while the
GitHub deploy was still in progress and hit the previous production image,
which returned `HTTP 405` for `POST /api/v1/agent/context`. The accepted proof is
the rerun after the deploy completed and the production token was rotated.

Do not switch the repo-local subagent default to Fly automatically. The safe
default remains local CLI usage; production calls require explicit `--api-url`.

### Step 6 - Verification

Status: **Partially done. Backend API/source-bundle, CLI wrapper, BDD acceptance tests, repo-local subagent contract tests, local dogfood tests, live smoke helper tests, paid local live smoke, all-experts local smoke, and first production Fly smoke pass. All-experts production smoke remains unproven.**

Required checks:

- all experts query returns selected sources by expert;
- custom expert query respects `expert_filter`;
- group query resolves to expected roster;
- comments under selected main sources are present;
- drift groups are absent by default;
- Reduce/language validation/comment synthesis/meta synthesis are not called in default source_bundle mode;
- existing `/api/v1/query` still works;
- auth/rate/timeout gates are covered before production exposure.

Targeted test files:

```text
backend/tests/test_agent_context_api.py
backend/tests/test_agent_context_cli.py
backend/tests/test_agent_context_acceptance.py
backend/tests/test_experts_panel_researcher_contract.py
backend/tests/test_experts_panel_researcher_dogfood.py
backend/tests/test_agent_context_live_smoke.py
```

Minimum tests:

- missing token -> `403`;
- unconfigured token -> `500`;
- valid token + `expert_scope=custom` uses only requested experts;
- `expert_scope=group`, `expert_group=tech` resolves to the expected MVP list;
- `expert_scope=all` excludes `video_hub` in MVP;
- unknown expert returns `400`;
- `source_bundle` response includes `selection_used`, `pipeline_used`, `pipeline_skipped`;
- Agent Context processes selected experts with bounded parallelism through `MAX_CONCURRENT_EXPERTS` and preserves response order;
- Agent Context always prepares one query embedding and uses hybrid retrieval for subagent/API source discovery regardless of the UI Embs&Keys toggle;
- default source_bundle does not call `ReduceService`, `LanguageValidationService`, `score_drift_groups`, `CommentSynthesisService`, or `MetaSynthesisService` (use monkeypatch fakes that fail if called);
- comments under selected sources are returned under each source;
- `include_drift_comment_groups=true` is rejected in MVP;
- CLI -> HTTP -> FastAPI -> source_bundle flow preserves explicit expert selection and safe defaults;
- CLI acceptance path does not leak the API token into request body, stdout, or stderr;
- unsupported `video_hub` request fails with an actionable API message;
- repo-local Claude/Codex subagent instructions are read-only, explicit-only, token-safe, and use the Signals frame instead of proof framing;
- local dogfood fixture and instructions verify JSON-as-input, actionable readiness failures, local defaults, and Signals frame usability;
- live local smoke helper can preflight, skip/fail/pass cleanly, use a free port, call CLI with explicit `--api-url`, and write a sanitized report;
- external smoke helper mode can call an explicit production/Fly URL without starting a local backend;
- default local smoke ignores ambient `AGENT_CONTEXT_API_URL` so Fly is never the accidental default;
- existing `/api/v1/query` smoke still passes.

## 14. Acceptance Criteria Status

Backend source-bundle MVP status:

| Criterion | Status |
|-----------|--------|
| explicit-only subagent can call the endpoint with a manual user trigger | Done locally: repo-local Claude/Codex subagent instructions and CLI wrapper exist; paid local source_bundle smoke passes |
| `source_bundle` returns selected source packets, not whole corpora | Done |
| source count follows system selection, not arbitrary per-expert product limits | Done |
| selected main source comments are included | Done |
| drift comment groups are not included by default | Done |
| skipped pipeline phases are visible in response metadata | Done |
| `selection_used` is always present | Done |
| all/custom/group expert selection works | Done |
| Reddit is off by default and separate when enabled | Partially done: Reddit remains off/default rejected in MVP; separate packet is not implemented yet |
| production exposure is blocked until auth, rate, timeout, and audit logging exist | Done for explicit smoke: auth/rate/timeout/size gates exist, production bearer token is separate, Fly `/health` passed, and external `refat,akimov` source_bundle smoke passed |
| local CLI wrapper works before production Fly usage is enabled | Done |
| BDD acceptance checks cover the CLI -> API -> source_bundle boundary | Done |
| first subagent is repo-local and explicit-only | Done |
| local dogfood can evaluate source_bundle JSON through the Signals frame | Done |
| live local smoke helper verifies real local CLI/API readiness without Fly | Done |
| external smoke helper can target production Fly only when explicitly requested | Done: `--api-url` enables `target_mode = "external"`, default local mode ignores ambient `AGENT_CONTEXT_API_URL`, and live Fly smoke passed |
| Agent Context inherits bounded parallel expert processing | Done: selected experts run behind `MAX_CONCURRENT_EXPERTS`, response order stays stable |
| first paid local live smoke returns a valid real source_bundle | Done: after forced Embs&Keys retrieval, default `refat,akimov` query passed with `refat=42`, `akimov=67`, `response_bytes=1081305`, `processing_time_ms=57321`, no warnings |
| all-experts paid local smoke returns a valid real source_bundle | Done: after forced Embs&Keys retrieval, full MVP Telegram roster passed with `17` experts, `response_bytes=7462364`, `processing_time_ms=275622`, no warnings |
| first production Fly smoke returns a valid real source_bundle | Done: explicit `refat,akimov` production smoke passed with `response_bytes=1125055`, `processing_time_ms=40473`, no warnings |
| subagent/CLI/API retrieval always uses embeddings | Done: CLI sends `use_super_passport=true`, API normalizes `selection_used.use_super_passport=true`, and service passes a precomputed query embedding into `HybridRetrievalService` for every selected expert |
| existing UI/SSE query endpoint is unchanged | Done by route-preservation/source-bundle isolation tests |

## 15. Closed Design Decisions

These decisions close the remaining open questions for the MVP implementation:

1. `CONTEXT` association uses explicit resolve provenance only. If provenance is missing, return the linked item in `unattached_linked_context` with a warning.
2. Build and use a local CLI wrapper before enabling production Fly usage.
3. Keep the first `experts_panel_researcher` subagent repo-local. Add a global user-level shortcut only after the API and wrapper contract are stable.
