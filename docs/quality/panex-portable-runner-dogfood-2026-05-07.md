# AND-24 Panex Portable Runner Dogfood

**Date:** 2026-05-07
**Status:** passed
**Scope:** cross-repo Панэкс runner for production Fly.io `expert_digest` and `source_expand` calls.

## Goal

Prove that Панэкс can be called from a different repo/cwd without depending on
the current `Experts_panel` working directory, without accidentally using a
local backend, and without exposing `AGENT_CONTEXT_API_TOKEN`.

## Implemented Interface

```text
panex doctor
panex ask --query "<query>" [--experts refat,akimov | --group tech | --group tech_business | --all] [--response-mode expert_digest|source_bundle] [--recent] --json
panex expand --source-keys refat:234,etechlead:139 --json
```

Production defaults:

- `panex ask` -> `https://experts-panel.fly.dev/api/v1/agent/context`
- `panex expand` -> `https://experts-panel.fly.dev/api/v1/agent/context/expand`
- `panex ask` defaults to `response_mode=expert_digest`.
- `source_bundle` remains explicit raw/audit mode through
  `--response-mode source_bundle`.
- Ambient local `AGENT_CONTEXT_API_URL` / `AGENT_CONTEXT_EXPAND_API_URL` are
  ignored unless `--local` or `--api-url` is explicit.

## BDD Checks

Local contract checks:

```text
backend/.venv/bin/python -m pytest backend/tests/test_agent_context_cli.py backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_experts_panel_researcher_dogfood.py -q -o addopts=''
# 45 passed

backend/.venv/bin/python -m pytest backend/tests/test_agent_context_api.py backend/tests/test_agent_context_acceptance.py backend/tests/test_agent_context_cli.py backend/tests/test_experts_panel_researcher_contract.py backend/tests/test_experts_panel_researcher_dogfood.py backend/tests/test_panex_quality_eval.py -q -o addopts=''
# 88 passed, 2 warnings
```

Covered behavior:

- foreign cwd `panex ask` uses Fly.io by default and sends `expert_digest`;
- foreign cwd `panex expand` uses Fly.io expand by default;
- ambient local API env vars do not hijack production calls;
- `source_bundle` is available only by explicit `--response-mode source_bundle`;
- missing token fails before HTTP and does not print secrets;
- `--local` is explicit for local backend debugging;
- `panex doctor` reports setup without printing the token;
- install script writes a user-level shim without embedding the token;
- repo-local Claude/Codex agent instructions use `panex ask` / `panex expand`
  for real production calls.

## Setup Smoke

Installed user-level shim:

```text
scripts/install_panex_runner.sh
# Installed panex runner: /Users/andreysazonov/.local/bin/panex
# Target backend: /Users/andreysazonov/Documents/Projects/Experts_panel/backend
```

Doctor from `/private/tmp`:

```text
panex doctor
# status: passed
# backend_dir: /Users/andreysazonov/Documents/Projects/Experts_panel/backend
# global_command: /Users/andreysazonov/.local/bin/panex
# token_configured: True
# production_api_url: https://experts-panel.fly.dev/api/v1/agent/context
# production_expand_api_url: https://experts-panel.fly.dev/api/v1/agent/context/expand
# warnings: none
```

The shim stores the backend path and venv Python path only. It does not store
`AGENT_CONTEXT_API_TOKEN`.

## Production Dogfood

`panex ask` from `/private/tmp`:

```text
panex ask --query "Когда subagents помогают в AI-разработке?" --experts refat --json --timeout 3600
```

Observed:

- target: Fly.io production Agent Context API;
- `mode=expert_digest`;
- `selection_used.expert_filter=["refat"]`;
- `include_reddit=false`;
- `include_main_source_comments=true`;
- `include_drift_comment_groups=false`;
- `synthesis_level=none`;
- `use_super_passport=true`;
- `selected_sources_count=28`;
- `warnings=[]`;
- `processing_time_ms=62125`.

`panex expand` from `/private/tmp`:

```text
panex expand --source-keys refat:238 --json --max-content-chars 1200 --max-comments-per-source 3 --timeout 3600
```

Observed:

- target: Fly.io production source expansion API;
- `mode=source_expand`;
- `source_key=refat:238`;
- `not_found=[]`;
- `warnings=[]`;
- returned capped raw content, 3 direct comments, truncation metadata,
  `evidence_quality`, and author-supplied external links with
  `fetch_status=not_fetched`;
- `processing_time_ms=17`.

## Product Verdict

Passed. AND-24 turns Панэкс from a repo-local capability into a practical
cross-repo tool:

- the main user command is short enough for daily use;
- the default target is production Fly.io, not localhost;
- local debug requires explicit opt-in;
- source expansion remains exact and cheap;
- raw `source_bundle` remains available but does not become the default path;
- token handling remains outside the parent-agent prompt and outside the shim.

Remaining limits:

- all-experts production runtime is still intentionally not proven here;
- no async job/result cache exists yet for very long all-expert calls;
- external links remain references-only unless a future explicit enrichment
  mode is built.
