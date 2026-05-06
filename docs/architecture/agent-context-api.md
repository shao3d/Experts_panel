# Agent Context API Spec

**Status:** Accepted / AND-5 + AND-6 + AND-7 + AND-8 + AND-9 + AND-10 + AND-11 + AND-12 + AND-13 + AND-14 + AND-15 + AND-16 + AND-17 + AND-18 + AND-19 implemented / forced embedding search implemented
**Decision:** `.haft/decisions/dec-20260504-b2539c3d.md`
**Last updated:** 2026-05-06

This spec defines the first agent-facing surface for Experts Panel: an explicit-only research/context API for Codex, Claude Code, and similar coding/research agents.

---

## 0. Implementation Status

Current state as of 2026-05-06:

| Slice | Status | What it means |
|-------|--------|---------------|
| AND-5 authenticated endpoint skeleton | Done | `POST /api/v1/agent/context` exists, uses a separate bearer token, has request validation, timeout, response-size limit, and in-process per-token rate limiting. |
| AND-6 real `source_bundle` pipeline | Done | The endpoint now returns selected source bundles instead of the placeholder `experts=[]` response. It runs retrieval, Map, MEDIUM scoring, HIGH resolve, source selection, and main-source comment loading. |
| AND-7 local CLI wrapper | Done | `src.cli.agent_context` calls the endpoint over HTTP with safe source-bundle defaults, keeps the token in the Authorization header, supports all/group/custom selection, and prints agent-readable summaries or raw JSON. |
| AND-8 BDD acceptance hardening | Done | In-process CLI -> HTTP -> FastAPI -> `source_bundle` acceptance tests cover explicit expert selection, safe defaults, no full synthesis, source evidence shape, token boundary, and actionable API failures. |
| AND-9 `experts_panel_researcher` / `Панэкс` subagent contract | Done | Repo-local Claude/Codex agent instructions and the user-level Codex shortcut exist, stay read-only, require explicit triggers, call the Agent Context CLI/wrapper only, pin real user calls to the production Fly.io endpoint, translate UI/Russian expert names to `expert_id`, accept human Russian trigger phrases without requiring API jargon, and return practitioner-opinion intelligence using the Signals frame with a compact Request passport. |
| AND-10 local dogfood for `experts_panel_researcher` | Done | A synthetic source_bundle fixture and dogfood tests verify that CLI JSON is synthesis input, readiness failures are actionable, local smoke remains explicit-only, and the six-section Signals frame is usable. |
| AND-11 live local dogfood smoke | Done | `backend/scripts/agent_context_live_smoke.py` can preflight local readiness, start Experts Panel on a free localhost port, call the CLI with explicit `--api-url`, validate `source_bundle`, and write a sanitized report with `passed`/`skipped`/`failed` status. |
| AND-12 paid local live smoke | Done | Paid local smoke passed with the default `refat,akimov` query and returned a valid real `source_bundle`. Runtime defaults are intentionally large (`3600s` / `100000000` bytes) because all-expert source-bundle requests are naturally long and bulky. |
| AND-13 bounded expert parallelism | Done | Agent Context now inherits the main pipeline's bounded expert parallelism pattern: selected experts run as async tasks behind `MAX_CONCURRENT_EXPERTS`, while response order stays aligned to the requested expert order. |
| AND-14 all-experts paid local smoke | Done | Paid local smoke passed for the full MVP Telegram roster (`17` experts, no `video_hub`) with bounded parallelism, no warnings, and a `7.46MB` source_bundle response after forced Embs&Keys retrieval. |
| AND-15 production Fly smoke mode | Done | `backend/scripts/agent_context_live_smoke.py` has an explicit external mode via `--api-url`; without that flag it still starts a local backend and ignores ambient `AGENT_CONTEXT_API_URL` to avoid accidental Fly calls. Production smoke passed on Fly with a separate production token for `refat,akimov`. |
| AND-16 source external links V1 | Done | `source_bundle` now extracts HTTP(S) links from each selected `main_source` into `main_sources[].external_links` as author-supplied references with `fetch_status=not_fetched`. The API/CLI/subagent contract does not fetch, crawl, clone, or summarize external URLs unless a later explicit enrichment mode is requested. Local live dogfood for `neuraldeep` found 40 real external links with `bad_suffix_links_count=0`; production public endpoint verification on Fly version `338` found 99 real external links with `bad_suffix_links_count=0`. |
| AND-17 panel-side `expert_digest` reduce | Done + deployed | Agent Context now supports `response_mode = "expert_digest"` for subagent calls. The backend still runs the same source discovery/comment-loading pipeline, then reduces selected posts and main-source comments into compact per-expert digests with provenance (`digest.source_refs`, `digest.source_index`, `digest.key_signals`, `digest.comments_digest`, `digest.omitted_counts`) and omits raw `main_sources` from that response. `source_bundle` remains available for explicit raw evidence/audit/debug requests. Production Fly smoke passed for `refat` with `mode=expert_digest`, `selected_sources_count=17`, `source_refs=8`, and no `expert_digest_reduce_failed` warning. |
| AND-18 production `expert_digest` BDD hardening | Done + deployed | Added production-live BDD tests that hit Fly.io directly with `AGENT_CONTEXT_PRODUCTION_LIVE=1` and no local backend/mocks. The first red run found that some LLM digest outputs return top-level signal lists without `position`; the backend now fills a safe fallback `position` instead of weakening the contract. Final production runs passed for two-expert, three-expert, digest-vs-source_bundle compactness, comments-off, unknown expert, unsupported response mode, and `video_hub` 501 scenarios. |
| AND-19 evidence expansion by `source_key` | Done + deployed | `expert_digest` now includes compact `digest.source_index` handles for all selected sources, while `POST /api/v1/agent/context/expand` expands exact `source_key` handles such as `refat:234` into raw/capped post evidence, direct comments, external link metadata, truncation metadata, and `not_found` entries without rerunning search, Map, Resolve, Reduce, or digest. Панэкс instructions use `src.cli.agent_context_expand` when the user asks in plain Russian to reveal sources/proofs/details from a previous digest, or gives concrete handles, then report a lean Evidence Note rather than a second digest. |
| Forced embedding search for Agent Context | Done | Agent Context always forces Embs&Keys hybrid retrieval: CLI sends `use_super_passport=true`, API records `selection_used.use_super_passport=true`, and service prepares one query embedding for all selected experts before bounded parallel expert processing. UI toggle state does not apply to subagent/API calls. |
| FTS5 query sanitation hardening | Done | Production logs for the Панэкс query about `file-fist` showed AI Scout returning an invalid FTS5 query and then fallback producing unsafe terms such as `file-fist*`, which made the FTS5 side of hybrid retrieval fail with `no such column: fist` while vector retrieval still worked. `AIScoutService` fallback and `sanitize_fts5_query()` now normalize hyphens, punctuation, and unbalanced Scout quotes into safe OR-only FTS5 terms such as `file* OR fist*`. Fallback slang expansion also avoids treating short particles like Russian `а` as substring slang matches while preserving exact short tech terms such as `бд`, `c#`, `c++`, and `.net`. |
| Production Fly exposure | Done for explicit smoke and default subagent target | `https://experts-panel.fly.dev/api/v1/agent/context` is callable with the separate production bearer token and large source-bundle budgets. The subagent must pass this Fly URL explicitly for real user research calls; localhost is only for explicit local smoke/debug. |

Implemented code paths:

- `backend/src/api/agent_context_endpoint.py`
- `backend/src/services/agent_context_service.py`
- `backend/src/services/ai_scout_service.py`
- `backend/src/services/fts5_retrieval_service.py`
- `backend/src/services/simple_resolve_service.py`
- `backend/src/api/models.py`
- `backend/src/cli/agent_context.py`
- `backend/src/cli/agent_context_expand.py`
- `backend/tests/test_agent_context_acceptance.py`
- `backend/tests/test_agent_context_api.py`
- `backend/tests/test_agent_context_cli.py`
- `backend/tests/test_experts_panel_researcher_contract.py`
- `backend/tests/test_experts_panel_researcher_dogfood.py`
- `backend/tests/test_agent_context_live_smoke.py`
- `backend/tests/test_agent_context_production_expert_digest.py`
- `backend/tests/test_fts5_query_sanitization.py`
- `backend/tests/fixtures/experts_panel_researcher_source_bundle_sample.json`
- `backend/scripts/agent_context_live_smoke.py`
- `.claude/agents/experts_panel_researcher.md`
- `.codex/agents/experts_panel_researcher.toml`

Verified checks:

```text
backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py -q -o addopts=''
# 19 passed

backend/.venv/bin/python -m pytest backend/tests/test_experts_api.py -q -o addopts=''
# 1 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_cli.py -q -o addopts=''
# 11 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_acceptance.py -q -o addopts=''
# 7 passed

backend/.venv/bin/python -m pytest backend/tests/test_experts_panel_researcher_contract.py -q -o addopts=''
# 11 passed

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
# selection_used.use_super_passport: true
# selected_source_counts: refat=21, akimov=19
# response_bytes: 438663
# processing_time_ms: 140105
# warnings: []

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py backend/tests/test_experts_api.py backend/tests/test_agent_context_cli.py backend/tests/test_agent_context_acceptance.py backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_experts_panel_researcher_dogfood.py backend/tests/test_agent_context_live_smoke.py backend/tests/test_agent_context_production_expert_digest.py -q -o addopts=''
# 68 passed, 3 skipped, 2 warnings

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py backend/tests/test_agent_context_production_expert_digest.py -q -o addopts=''
# 19 passed, 3 skipped, 2 warnings

env AGENT_CONTEXT_PRODUCTION_LIVE=1 backend/.venv/bin/python -m pytest backend/tests/test_agent_context_production_expert_digest.py -q -o addopts=''
# first run: 1 passed, 2 failed
# failure: live Fly expert_digest sometimes had key_signals but no digest.position
# fix: fallback position when the LLM digest reducer returns a top-level signal list or omits position
# final run after deploy: 3 passed in 269.53s

env AGENT_CONTEXT_PRODUCTION_LIVE=1 backend/.venv/bin/python -m pytest backend/tests/test_agent_context_production_expert_digest.py -q -o addopts=''
# extended run after adding comments-off and bad-input scenarios: 7 passed in 355.19s

backend/.venv/bin/python -m pytest backend/tests/test_fts5_query_sanitization.py -q -o addopts=''
# first red run: 3 failed on file-fist*/method?*/unbalanced Scout quote cases
# final run after sanitizer hardening: 3 passed

backend/.venv/bin/python -m pytest backend/tests/test_fts5_query_sanitization.py backend/tests/test_agent_context_api.py backend/tests/test_experts_api.py backend/tests/test_agent_context_cli.py backend/tests/test_agent_context_acceptance.py backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_experts_panel_researcher_dogfood.py backend/tests/test_agent_context_live_smoke.py backend/tests/test_agent_context_production_expert_digest.py -q -o addopts=''
# 80 passed, 7 skipped, 2 warnings

backend/.venv/bin/python -m pytest backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_agent_context_api.py backend/tests/test_agent_context_acceptance.py backend/tests/test_agent_context_cli.py -q -o addopts=''
# AND-19 local BDD/TDD: 57 passed, 2 warnings

cd backend && .venv/bin/python -m src.cli.agent_context_expand --api-url https://experts-panel.fly.dev/api/v1/agent/context/expand --source-keys refat:220 --max-content-chars 1200 --max-comments-per-source 3 --timeout 3600 --json
# AND-19 production source_expand smoke after Fly deploy
# mode: source_expand
# source_key: refat:220
# not_found: []
# warnings: []
# returned: raw content, 3 direct comments under source, external_links metadata
# truncation: content_truncated=true, comments_truncated=true
# processing_time_ms: 92

cd backend && .venv/bin/python -m src.cli.agent_context --query "Когда стоит использовать subagents?" --experts refat --response-mode expert_digest --api-url https://experts-panel.fly.dev/api/v1/agent/context
# mode: expert_digest
# selected_sources_count: refat=17
# source_refs: 8
# warning: agent_context_ai_scout_fallback_used
# no expert_digest_reduce_failed warning

git diff --check
# clean
```

CLI usage:

```text
cd backend
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --experts refat,akimov
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --experts refat,akimov --response-mode expert_digest
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --group tech
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --json
.venv/bin/python -m src.cli.agent_context_expand --source-keys refat:234,etechlead:139 --api-url https://experts-panel.fly.dev/api/v1/agent/context/expand --json
```

Important boundary: Fly.io is now the default target for real subagent research
calls, but production proof is still narrow: explicit `refat,akimov` smoke has
passed, while all-experts production runtime remains unproven. This also does
not build a Reddit source packet or Video Hub source-bundle adapter.

---

## 1. Goal

Experts Panel should be callable by AI agents only when Andrey explicitly asks for it.

The first product surface is not a full public platform, not a full MCP server, and not the current UI answer pipeline exposed as-is. It is a thin authenticated REST endpoint that returns a source-backed evidence packet under a selected expert scope.

Target shape:

```text
Andrey
  -> "Панэкс: спроси Refat и Akimov..."

Main Codex / Claude Code
  -> calls explicit-only experts_panel_researcher

experts_panel_researcher
  -> POST /api/v1/agent/context
  -> response_mode = "expert_digest" by default

Experts Panel
  -> partial source discovery pipeline
  -> selected sources + comments under those sources
  -> compact per-expert digest with source refs
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

- "Панэкс: ..."
- "Спроси Панэкс ..."
- tolerated spelling: "Панэнкс ..."
- "Спроси Панель Экспертов ..."
- "вызови experts_panel_researcher ..."
- "/experts ..."
- "проверь через Experts Panel ..."

The user-facing trigger language should stay human. Андрей does not need to
write internal terms such as `source_key`, `source_expand`, `expert_digest`, or
`Evidence Note`.

Plain Russian digest triggers:

- "Панэкс, спроси ...";
- "что думают эксперты ...";
- "по мнению экспертов ...";
- "узнай у <экспертов> ...".

Plain Russian expansion triggers over the previous digest:

- "раскрой подробнее";
- "покажи источники";
- "дай пруфы";
- "на чём основано";
- "почему такой вывод";
- "покажи первоисточник";
- "разверни по <эксперту>";
- "что там в комментариях";
- "проверь источник".

For expansion triggers, "previous digest" means the latest Панэкс
`expert_digest` output available in the current agent/parent context, with
`digest.source_refs`, `digest.source_index`, and `digest.key_signals`. Панэкс
must not infer source handles from memory or expert names alone.

Expansion source selection priority:

1. concrete `source_key` in the user request;
2. `key_signal.supporting_sources` for "этот вывод" / "этот тезис";
3. named expert -> that expert's `digest.source_refs` in their existing order;
4. `digest.source_index` only when `source_refs` are missing or the user
   explicitly asks for omitted/all sources.

"Strongest" means first HIGH / first listed source in the previous digest, not
a new ranking by the subagent. "по каждому эксперту" -> top 1 source per expert
unless the user asks for more; generic "покажи источники" -> top 1-2 strongest
sources. "что там в комментариях" still uses `source_expand`, but the answer
should focus on direct comments and say if comments are mostly noise. "дай
пруфы" means supporting practitioner sources, not proof of truth.

If the target could refer to several experts, claims, or sources, Панэкс should
ask one short clarification unless the user asked generically for top sources.
If no previous digest/source handle context is available, Панэкс must not guess,
must not use memory, and must not run `source_expand`; it should say that a main
Панэкс question must be asked first or ask whether to run one now. It must not
run a new `expert_digest` / `source_bundle` to satisfy an expansion phrase
unless the user explicitly asks to refresh, rerun, or ask a new main question.

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
  - requests expert_digest by default
  - requests source_bundle only for explicit raw evidence/audit/debug mode
  - returns practitioner-opinion intelligence, not proof claims
  - uses the Signals frame:
    1. Query and selection
    2. Source-backed signals
    3. Expert positions
    4. Convergence / divergence
    5. Practical application
    6. Limits and missing evidence
```

The `Query and selection` section must start with a compact Request passport,
not a raw JSON dump. Required fields are:

```text
query_sent: exact query string sent in the API payload
experts_sent: selected expert ids, group, or all
response_mode: expert_digest or source_bundle
target: Fly.io production or explicit local smoke/debug URL
warnings: none, or important top-level API warnings
```

The passport exists to verify scope through the parent-agent -> subagent ->
CLI/API chain. It must not include the API token, raw JSON, or long pipeline
dumps.

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

User-facing expert names should follow the UI labels from
`docs/architecture/current-expert-roster.md` / `frontend/src/config/expertConfig.ts`.
The subagent translates those labels, common English variants, and obvious
Russian spellings into backend `expert_id` values before calling the CLI. Minor
case, spacing, punctuation, Latin/Russian spelling, and one-obvious-target typos
may be corrected by the subagent. If a name or typo could map to more than one
expert, the subagent must ask one clarification before calling the API.

Supported selection modes:

| User phrase | API interpretation |
|-------------|--------------------|
| "по всем" / no subset | `expert_scope = "all"`, `expert_filter = null` |
| "по технарям" / "Tech" | `expert_scope = "group"`, `expert_group = "tech"` |
| "по бизнесовым" / "Tech & Business" | `expert_scope = "group"`, `expert_group = "tech_business"` |
| "по видео" / "Video Hub" | `expert_scope = "custom"`, `expert_filter = ["video_hub"]` |
| named experts using UI labels, Russian names, or `expert_id` | `expert_scope = "custom"`, `expert_filter = [...]` |
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
  "response_mode": "expert_digest",
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
| `response_mode` | Default for subagent is `expert_digest`; use `source_bundle` only for explicit raw evidence/audit/debug. |
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
- accept only `response_mode = "source_bundle"` or `response_mode = "expert_digest"`.
- reject `synthesis_level != "none"` in MVP with `400` or `501`; do not silently run the full UI Reduce pipeline.
- default `include_reddit = false`, `include_main_source_comments = true`, `include_drift_comment_groups = false`, `synthesis_level = "none"`.
- force `use_super_passport = true` even if a caller sends `false`; Agent Context must use Embs&Keys hybrid retrieval rather than the UI-controlled standard search mode.

## 6. Response Contract

The endpoint returns a bounded evidence packet, not the entire corpus.
There are two response modes:

- `expert_digest`: default for Панэкс/subagent calls. The backend returns compact
  per-expert digests and strips raw `main_sources` from the transport response.
- `source_bundle`: raw evidence mode for explicit audit/debug/smoke requests.

### `source_bundle` response

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
          "external_links": [
            {
              "url": "https://github.com/example/repo",
              "domain": "github.com",
              "label": "example repo",
              "context": "... surrounding source text ...",
              "link_type": "github_repo",
              "fetch_status": "not_fetched"
            }
          ],
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
    "main_source_comments",
    "external_link_references"
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

### `expert_digest` response

In `expert_digest` mode, `selected_sources_count` still reflects how many
main sources the source discovery pipeline selected, but the response carries
compact digest fields instead of the raw posts/comments payload:

```json
{
  "request_id": "req_...",
  "mode": "expert_digest",
  "query": "Когда стоит использовать subagents?",
  "selection_used": {
    "expert_scope": "custom",
    "expert_filter": ["refat"],
    "include_main_source_comments": true,
    "include_drift_comment_groups": false,
    "synthesis_level": "none",
    "use_super_passport": true
  },
  "experts": [
    {
      "expert_id": "refat",
      "expert_name": "Refat",
      "channel_username": "nobilix",
      "selected_sources_count": 12,
      "unattached_linked_context": [],
      "main_sources": [],
      "digest": {
        "position": "Short neutral summary of this expert's stance.",
        "key_signals": [
          {
            "claim": "A compact practitioner signal grounded in selected sources.",
            "support_level": "direct",
            "supporting_sources": ["refat:123"],
            "comment_signal": "Optional compact comment signal.",
            "limits": "Optional uncertainty or missing evidence."
          }
        ],
	        "source_refs": [
          {
            "telegram_message_id": 123,
            "source_key": "refat:123",
            "relevance": "HIGH",
            "reason": "Why this source matched the query.",
            "short_excerpt": "... clipped source excerpt ...",
            "external_links": [
              {
                "url": "https://github.com/example/repo",
                "domain": "github.com",
                "link_type": "github_repo",
                "fetch_status": "not_fetched"
              }
            ],
            "linked_context_count": 1,
            "author_comments_count": 2,
            "community_comments_count": 4
	          }
	        ],
	        "source_index": [
	          {
	            "telegram_message_id": 123,
	            "source_key": "refat:123",
	            "relevance": "HIGH",
	            "reason": "Why this source matched the query.",
	            "created_at": "2026-04-10T12:00:00",
	            "author_comments_count": 2,
	            "community_comments_count": 4,
	            "external_links_count": 1,
	            "linked_context_count": 1,
	            "content_chars": 3140
	          }
	        ],
	        "comments_digest": {
          "author_comments_count": 2,
          "community_comments_count": 4,
          "included_comments": [],
          "omitted_comments_count": 3
        },
        "omitted_counts": {
          "main_sources": 4,
          "linked_context": 2,
          "author_comments": 1,
          "community_comments": 2,
          "external_links": 1
        },
        "limits": [],
        "no_signal_reason": null
      },
      "no_results_reason": null
    }
  ],
  "pipeline_used": ["expert_selection", "source_selection", "expert_digest_reduce"],
  "pipeline_skipped": ["reduce_answer_synthesis", "comment_synthesis"]
	}
	```

### `source_expand` endpoint

`source_expand` is a second-step exact lookup by `source_key`, not a new search.
It should be used after `expert_digest` when the user asks Панэкс to reveal raw
evidence such as `refat:234`.

```text
POST /api/v1/agent/context/expand
```

```json
{
  "source_keys": ["refat:234", "etechlead:139"],
  "include_comments": true,
  "include_external_links": true,
  "max_content_chars": 20000,
  "max_comments_per_source": 50
}
```

Response:

```json
{
  "request_id": "req_...",
  "mode": "source_expand",
  "sources": [
    {
      "source_key": "refat:234",
      "expert_id": "refat",
      "expert_name": "Refat",
      "channel_username": "nobilix",
      "telegram_message_id": 234,
      "content": "... raw or capped post text ...",
      "created_at": "2026-04-10T12:00:00",
      "author_name": "Refat",
      "comments": {
        "author_comments": [],
        "community_comments": []
      },
      "external_links": [],
      "truncation": {
        "content_truncated": false,
        "comments_truncated": false
      }
    }
  ],
  "not_found": [],
  "warnings": [],
  "processing_time_ms": 0
}
```

`source_expand` must not call AI Scout, embeddings, retrieval, Map, MEDIUM
scoring, Resolve, `ReduceService`, `expert_digest`, language validation,
comment synthesis, Reddit, or meta synthesis. Missing valid keys go to
`not_found`; malformed keys return actionable `400`.

Панэкс must present expanded sources as a lean Evidence Note, not as another
digest/reduce/synthesis layer. The note stays tied to the requested
`source_key` handles and does not rebuild the expert's overall position. It
should briefly state what the source itself says, what direct comments add or
whether they are mostly noise, notable author-supplied external refs,
truncation/limits, and whether the raw evidence changes or merely supports the
earlier digest. For one or two sources, keep this to roughly 3-6 bullets unless
the parent explicitly asks for raw text or raw JSON.

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
- return external HTTP(S) references found inside selected source content as `main_sources[].external_links`;
- external links are author-supplied references only in V1: set `fetch_status = "not_fetched"` and do not fetch, crawl, clone, or summarize URL contents inside default `source_bundle`;
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
- External link extraction is source-local and references-only. Extract Markdown links and plain `http(s)` URLs from the selected source content, include domain/link type/context metadata, and dedupe repeated URLs within one source. Do not use external URL contents as evidence unless a future explicit link-enrichment mode records fetch status, timestamp, and provenance.

This is the first deterministic source_bundle contract. If later quality checks show that Reduce's LLM-selected `main_sources` are materially better, add a narrow selector step instead of re-enabling full answer synthesis.

## 8. Partial Pipeline For `source_bundle` And `expert_digest`

Both modes start with the same source discovery pipeline:

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
   3.7 Extract external HTTP(S) references from selected source content without fetching them.
4. Optionally add Reddit source packet if requested.
5. Return response:
   - `source_bundle`: raw selected sources/comments/context.
   - `expert_digest`: compact per-expert digest plus source refs/source index and omitted counts.
```

Expert execution must follow the same operational shape as the existing
`/api/v1/query` pipeline:

- create one async task per selected expert;
- guard expert work with `asyncio.Semaphore(config.MAX_CONCURRENT_EXPERTS)`;
- keep the response `experts[]` order aligned to the resolved expert order;
- keep per-expert warnings isolated during processing, then merge them into the
  top-level `warnings` list after task completion.

Default Agent Context modes should skip the full UI synthesis phases:

```text
ReduceService answer synthesis
LanguageValidationService
CommentGroupMapService.score_drift_groups()
CommentSynthesisService
MetaSynthesisService
Reddit synthesis
```

This is intentionally not a set of `skip_*` flags on `/api/v1/query`. It should be a separate endpoint/service path for agent context.

`expert_digest` adds one narrow panel-side reduce step after source/comment
loading:

```text
raw AgentExpertSourceBundle
  -> cap source refs/comments/external links by Agent Context digest limits
  -> include source_index handles for all selected sources
  -> LLM compact digest per expert
  -> return digest fields and clear raw main_sources from the transport response
```

This reduce step is not the old full `ReduceService` answer synthesis. It does
not run language validation, drift comment scoring, comment synthesis, cross-
expert meta synthesis, Reddit synthesis, or the UI `/api/v1/query` pipeline.
If digest generation fails for one expert, return extractive source refs for
that expert with an `expert_digest_reduce_failed` warning rather than failing
the entire request.

`source_expand` is intentionally outside this search pipeline:

```text
source_key handles
  -> exact DB lookup by expert_id + telegram_message_id
  -> load direct main-source comments
  -> extract source-local external link references
  -> return raw/capped source evidence with truncation metadata
```

It must not rerun search, AI Scout, embeddings, Map, MEDIUM scoring, Resolve,
full Reduce, or `expert_digest`. This keeps second-step expansion fast,
deterministic, and scoped to user-requested evidence handles.

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

Status: **Done. CLI wrapper is implemented in AND-7; repo-local Claude and Codex subagent contracts are implemented in AND-9; production Fly usage is implemented and is the default target for real subagent research calls after AND-15.**

The Agent Context CLI/wrapper is the first supported integration surface for Codex/Claude Code. The CLI still has a local default for backend debugging, but the subagent must not rely on that default for real research calls.

Wrapper responsibilities:

- hold the API token outside the broad main-agent prompt;
- target production Fly.io explicitly for real subagent calls:
  `https://experts-panel.fly.dev/api/v1/agent/context`;
- keep local development as an explicit smoke/debug mode only;
- send `response_mode = expert_digest` by default;
- reserve `response_mode = source_bundle` for explicit raw evidence/audit/debug requests;
- send `use_super_passport = true` and rely on the API to force it true even if a caller tries to disable it;
- keep `include_reddit = false`, `include_main_source_comments = true`, `include_drift_comment_groups = false`, and `synthesis_level = none` unless explicitly overridden by the caller;
- print `selection_used`, warnings, and source packet metadata.

Production Fly usage is allowed because endpoint auth, rate limiting, timeout,
response-size limits, and basic request logging are implemented and covered by
tests. Agents copied into other repositories must keep the same Fly URL and
must not fall back to random `localhost` services.

Add durable instructions for Codex/Claude Code integration:

- explicit triggers only;
- recognize `Панэкс` / `Спроси Панэкс` as Russian shorthand triggers, with `Панэнкс` tolerated as a spelling variant;
- parse expert selection using UI/display labels first, then translate to backend `expert_id`;
- accept obvious Russian expert names and correct only one-obvious-target typos;
- ask one clarification for unknown or ambiguous expert names before calling the CLI;
- default `response_mode = expert_digest`;
- print `selection_used`;
- return practitioner-opinion intelligence using the Signals frame:
  `Query and selection`, `Source-backed signals`, `Expert positions`,
  `Convergence / divergence`, `Practical application`,
  `Limits and missing evidence`;
- never present practitioner posts as proven facts;
- never edit repo files;
- never broaden scope silently.

The first subagent lives in repo-local Claude/Codex configuration, next to this
spec and the CLI wrapper. A global user-level Codex subagent also exists as a
stable shortcut at `~/.codex/agents/experts_panel_researcher.toml`; it uses the
canonical local Experts Panel backend checkout as the CLI wrapper host and keeps
the production Fly URL pinned for real research calls.

### Step 5.5 - Local Dogfood

Status: **Done in AND-10 for local contract and manual smoke readiness. Local smoke is no longer the default user-facing subagent target.**

Local dogfood proves the workflow against a local backend only when explicitly
requested:

```text
explicit user request
  -> experts_panel_researcher
  -> local CLI with --json
  -> expert_digest JSON by default
  -> compact Signals frame synthesis
```

The CLI JSON is input for synthesis, not the final answer. The subagent should
not dump raw JSON unless the parent explicitly asks for it. The older
`source_bundle` fixture remains useful for raw evidence dogfood and audit
coverage; user-facing Панэкс calls now prefer `expert_digest`.

Dogfood fixture:

```text
backend/tests/fixtures/experts_panel_researcher_source_bundle_sample.json
```

Real user-facing subagent smoke should use production Fly:

```text
cd backend
.venv/bin/python -m src.cli.agent_context \
  --query "AI agents for sales" \
  --experts refat,akimov \
  --response-mode expert_digest \
  --api-url https://experts-panel.fly.dev/api/v1/agent/context \
  --json
```

Manual local smoke, only when local backend and `AGENT_CONTEXT_API_TOKEN` are
intentionally available:

```text
cd backend
.venv/bin/python -m src.cli.agent_context --query "AI agents for sales" --experts refat,akimov --json
```

The CLI local backend default remains for explicit local debug:

```text
http://localhost:8000/api/v1/agent/context
```

Do not use the CLI default for real subagent calls. Always pass the Fly URL with
`--api-url`.

Signals frame checklist:

1. Query and selection
   - starts with the compact Request passport:
     `query_sent`, `experts_sent`, `response_mode`, `target`, `warnings`
2. Source-backed signals
3. Expert positions
4. Convergence / divergence
5. Practical application
6. Limits and missing evidence

Failure handling:

- missing `AGENT_CONTEXT_API_TOKEN`: explain that the production token must be configured;
- `HTTP 403` / invalid token: explain that the configured token is not the production Agent Context token;
- DNS/`NameResolutionError`/unreachable Fly endpoint: explain that production network access is blocked or unavailable;
- unreachable local backend during explicit local smoke: ask to start backend or check `AGENT_CONTEXT_API_URL`;
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

Measured production result on 2026-05-05 after forced Embs&Keys retrieval
deployed:

```text
status = passed
reason = source_bundle_valid
target_mode = external
selection_used.use_super_passport = true
selected_source_counts = refat=21, akimov=19
response_bytes = 438663
processing_time_ms = 140105
warnings = []
Fly release = v336
GitHub deploy run = 25391387130, completed success
```

Earlier production smoke evidence before forced Embs&Keys retrieval used Fly
release `v333`; the accepted current proof is the rerun after commit `5023e56`
deployed and the production token was rotated.

The subagent now treats Fly.io as the safe real-request target. It must pass
`--api-url https://experts-panel.fly.dev/api/v1/agent/context` explicitly on
production calls and reserve localhost/default CLI usage for explicit local
smoke or backend debugging.

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
backend/tests/test_agent_context_production_expert_digest.py
backend/tests/test_fts5_query_sanitization.py
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
- AI Scout fallback and shared FTS5 sanitization keep punctuation-heavy queries safe for hybrid retrieval (`file-fist`, `метод?`, unbalanced Scout quotes);
- default source_bundle does not call `ReduceService`, `LanguageValidationService`, `score_drift_groups`, `CommentSynthesisService`, or `MetaSynthesisService` (use monkeypatch fakes that fail if called);
- comments under selected sources are returned under each source;
- external links under selected sources are returned as `external_links` with `fetch_status=not_fetched`, and the subagent instructions forbid automatic external browsing;
- `include_drift_comment_groups=true` is rejected in MVP;
- CLI -> HTTP -> FastAPI -> source_bundle flow preserves explicit expert selection and safe defaults;
- CLI -> HTTP -> FastAPI -> expert_digest flow compacts raw evidence before subagent output and preserves source provenance;
- CLI -> HTTP -> FastAPI -> source_expand flow reveals exact source keys without rerunning search/digest;
- CLI acceptance path does not leak the API token into request body, stdout, or stderr;
- unsupported `video_hub` request fails with an actionable API message;
- repo-local Claude/Codex subagent instructions are read-only, explicit-only, token-safe, pin production Fly.io for real calls, use the Signals frame instead of proof framing, and start `Query and selection` with a compact Request passport;
- local dogfood fixture and instructions verify JSON-as-input, actionable readiness failures, explicit local smoke, and Signals frame usability;
- live local smoke helper can preflight, skip/fail/pass cleanly, use a free port, call CLI with explicit `--api-url`, and write a sanitized report;
- external smoke helper mode can call an explicit production/Fly URL without starting a local backend;
- default local smoke ignores ambient `AGENT_CONTEXT_API_URL`; subagent real-call instructions bypass the local default by always passing the Fly URL explicitly;
- production-live expert_digest tests can hit Fly.io directly with `AGENT_CONTEXT_PRODUCTION_LIVE=1`, validate two/three-expert digest contracts, assert no raw `main_sources`/`comment_id` leakage, compare compact digest transport against raw `source_bundle`, verify comments-off digest behavior, and check cheap bad-input failures before digest work;
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
| first subagent is repo-local and explicit-only | Done; real research calls pin the production Fly.io endpoint |
| local dogfood can evaluate source_bundle JSON through the Signals frame | Done |
| live local smoke helper verifies real local CLI/API readiness without Fly | Done |
| external smoke helper can target production Fly only when explicitly requested | Done: `--api-url` enables `target_mode = "external"`, default local mode ignores ambient `AGENT_CONTEXT_API_URL`, live Fly smoke passed, and subagent instructions now pass the Fly URL explicitly for real calls |
| Agent Context inherits bounded parallel expert processing | Done: selected experts run behind `MAX_CONCURRENT_EXPERTS`, response order stays stable |
| first paid local live smoke returns a valid real source_bundle | Done: after forced Embs&Keys retrieval, default `refat,akimov` query passed with `refat=42`, `akimov=67`, `response_bytes=1081305`, `processing_time_ms=57321`, no warnings |
| all-experts paid local smoke returns a valid real source_bundle | Done: after forced Embs&Keys retrieval, full MVP Telegram roster passed with `17` experts, `response_bytes=7462364`, `processing_time_ms=275622`, no warnings |
| first production Fly smoke returns a valid real source_bundle | Done after forced Embs&Keys retrieval: explicit `refat,akimov` production smoke passed with `selection_used.use_super_passport=true`, `response_bytes=438663`, `processing_time_ms=140105`, no warnings |
| subagent/CLI/API retrieval always uses embeddings | Done: CLI sends `use_super_passport=true`, API normalizes `selection_used.use_super_passport=true`, and service passes a precomputed query embedding into `HybridRetrievalService` for every selected expert |
| selected source external links are surfaced without automatic browsing | Done: `main_sources[].external_links` carries author-supplied references with `fetch_status=not_fetched`; CLI summary prints link counts; subagent instructions forbid opening/fetching/crawling/cloning/summarizing external URLs unless explicitly requested; local live dogfood for `neuraldeep` found 40 real external links across 11 selected sources, all `not_fetched`, with `bad_suffix_links_count=0`; production public endpoint verification on `https://experts-panel.fly.dev/api/v1/agent/context` found 99 real external links across 23 selected sources, all `not_fetched`, with `bad_suffix_links_count=0` |
| subagent default response is compact enough for parent-agent synthesis | Done + deployed: `response_mode=expert_digest` returns `digest` fields with source refs/source index/comment counts/omitted counts and clears raw `main_sources` from the transport response; Панэкс instructions use `--response-mode expert_digest` by default; production Fly smoke passed for `refat` |
| Панэкс can reveal specific digest sources without a new search query | Done locally: `POST /api/v1/agent/context/expand` and `src.cli.agent_context_expand` expand concrete `source_key` handles into raw/capped source evidence, comments, external links, truncation metadata, and `not_found`; tests assert search/Map/Resolve/Reduce/digest are not called |
| subagent responses expose the actual request scope | Done: Панэкс instructions require a compact Request passport with `query_sent`, `experts_sent`, `response_mode`, `target`, and `warnings` at the start of `Query and selection` |
| raw evidence remains available for audit/debug | Done: `response_mode=source_bundle` remains the CLI/API default outside the subagent contract and is explicitly reserved in Панэкс instructions for raw evidence, audit/debug, and source-bundle smoke verification |
| production BDD checks cover the deployed `expert_digest` contract | Done: `backend/tests/test_agent_context_production_expert_digest.py` passed against Fly.io with two-expert, three-expert, digest-vs-source_bundle compactness, comments-off, unknown expert, unsupported response mode, and `video_hub` 501 scenarios |
| FTS5 side of hybrid retrieval survives punctuation-heavy Scout/fallback queries | Done locally: `backend/tests/test_fts5_query_sanitization.py` covers `file-fist`, question-mark suffixes, and unbalanced Scout quotes; broad Agent Context/backend contour passed with `71 passed, 7 skipped` |
| existing UI/SSE query endpoint is unchanged | Done by route-preservation/source-bundle isolation tests |

## 15. Closed Design Decisions

These decisions close the remaining open questions for the MVP implementation:

1. `CONTEXT` association uses explicit resolve provenance only. If provenance is missing, return the linked item in `unattached_linked_context` with a warning.
2. Build and use a local CLI wrapper before enabling production Fly usage.
3. Keep the first `experts_panel_researcher` subagent repo-local, but pin real research calls to the production Fly.io endpoint so the same agent contract can be copied into other repositories. Add the user-level Codex shortcut as `Панэкс` only after the API and wrapper contract are stable.
4. Treat external URLs found in selected source posts as references-only in default `source_bundle`. Surface them under `main_sources[].external_links` but do not fetch or summarize them without an explicit future enrichment mode.
5. Use `expert_digest` as the default Панэкс/subagent response mode. It is a narrow panel-side reduce over selected sources and direct main-source comments, not the old full UI Reduce/Meta/Comment synthesis pipeline. Keep `source_bundle` as explicit raw evidence/audit/debug mode.
6. Use exact `source_key` expansion as the second-step raw evidence path. `source_expand` is a lookup over `digest.source_refs` / `digest.source_index` handles, not a new `expert_digest` or `source_bundle` search.
