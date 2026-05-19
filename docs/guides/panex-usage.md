# Panex Usage Guide

**Status:** Active
**Last updated:** 2026-05-20

This is the human-facing quick guide for using Панэкс from Codex/Claude chats
in any repo.

## What Панэкс Does

Панэкс is an explicit-only bridge to Experts Panel on Fly.io. It helps a parent
agent ask selected practitioners/experts for context, patterns, trade-offs, and
source-backed signals, then delivers the Panel digest without a second summary.

Default behavior:

- uses production Fly.io;
- searches selected experts with forced hybrid/embedding retrieval;
- returns `expert_digest`, not a giant raw bundle;
- treats `expert_digest` as already reduced Panel output;
- saves full real-call responses as local artifacts for subagent workflows;
- includes direct comments under selected answer sources;
- includes `source_key` handles for follow-up expansion;
- keeps external links as author-supplied references;
- does not select drift comment groups by default.

## Ask For Help

In a Codex/Claude chat:

```text
Панэкс, помощь
Панэкс, что ты умеешь?
Как пользоваться Панэксом?
Покажи примеры Панэкса.
Как искать через Панэкс?
```

Панэкс should answer from its instructions and must not call the API for help
requests.

In a terminal:

```bash
panex guide
panex help
panex --help
panex ask --help
panex expand --help
panex read --help
panex export --help
panex cleanup --help
```

`panex guide` and `panex help` are human-friendly and do not require
`AGENT_CONTEXT_API_TOKEN`.

## Ask Experts

Ask concrete experts:

```text
Спроси Панэкс у Refat и Akimov: когда subagents реально помогают?
```

Equivalent CLI shape:

```bash
panex ask --query "Когда subagents реально помогают?" --experts refat,akimov --save --receipt-json
```

Ask a group:

```text
Панэкс, спроси группу tech_business: что такое context rot?
```

```bash
panex ask --query "Что такое context rot?" --group tech_business --save --receipt-json
```

Ask all current database experts except unsupported special sources such as `video_hub`:

```bash
panex ask --query "Что думают про LLM caching?" --all --save --receipt-json
```

Wide requests must use `--save` or `--output`; this is intentional. Wide means
`--all`, `--group`, or `--experts` with 6+ unique expert ids. The full digest may
be large, and the CLI should preserve it as an artifact instead of relying on
chat/stdout transport.

## Artifact Transport

For real Codex/Claude subagent calls, use artifact-first transport:

```bash
panex ask --query "..." --group tech_business --save --receipt-json
```

This prevents large Панэкс responses from being truncated in tool output. The
backend first persists the completed Agent Context response and returns a compact
server receipt. The CLI then fetches that saved backend result and writes a local
copy outside the current repo, under `PANEX_ARTIFACT_DIR` or, by default,
`~/.local/share/panex/artifacts`. Stdout contains only a small receipt with
`artifact_path`, `request_id`, `response_bytes`, optional `backend_result_url`,
warnings, and suggested `panex read` / `panex export` commands.

This is transport hardening only. It does not add a new analysis mode and does
not create a UI-style cross-expert meta-synthesis for Панэкс.

For wide delivery (`--all`, `--group`, or 6+ explicit experts), export the
artifact after receipt and treat chat prose as navigation, not as a replacement
for the saved digest:

```bash
panex export --path /path/to/response.json --json
```

Read saved results in slices:

```bash
panex read --path /path/to/response.json --manifest --json
panex read --path /path/to/response.json --expert refat --json
panex read --path /path/to/response.json --source-key refat:238 --json
```

Do not use `cat response.json` for large Панэкс artifacts; that can reintroduce
tool-output truncation.

Export saved results into human-readable files:

```bash
panex export --path /path/to/response.json --json
```

The export writes:

- `manifest.json` - compact machine-readable artifact passport;
- `digest.md` - readable per-expert digest delivery with source handles;
- `sources_index.tsv` - source handle index for targeted follow-up expansion.

Backend artifact endpoints used by `panex --save`:

- `POST /api/v1/agent/context/artifact` - build/save an `expert_digest` or `source_bundle` response and return a compact receipt;
- `POST /api/v1/agent/context/expand/artifact` - build/save a `source_expand` response and return a compact receipt;
- `GET /api/v1/agent/context/{request_id}/result` - fetch the saved backend result by `request_id`.

Backend-saved Agent Context results are retained for `AGENT_CONTEXT_RESULTS_TTL_DAYS`
(default: 7 days) and cleaned on backend startup. Local artifacts remain under
the local `panex cleanup` policy below.

## Routing From Other Repos

When you ask in another repo:

```text
Панэкс, что думают эксперты про ...
```

the parent Codex should prefer the `experts_panel_researcher` subagent. Direct
`panex` CLI from the parent chat is only a fallback when the subagent is
unavailable or you explicitly ask for CLI. If fallback happens, it must still
use artifact transport:

```bash
panex ask --query "..." --group tech_business --save --receipt-json
panex read --path /path/to/response.json --manifest --json
panex read --path /path/to/response.json --expert refat --json
panex export --path /path/to/response.json --json
```

This keeps the explicit-only boundary and avoids parent-chat stdout truncation.

The parent chat may pass current-project context to Панэкс as a retrieval lens:
domain, constraints, target audience, architecture area, or decision question.
Панэкс should use that context only to search and deliver Experts Panel digest
fields. It should not make project-specific PM, product, backend, architecture,
roadmap, go/no-go, or implementation recommendations. It should not summarize
the digest again or create a new meta-synthesis. Final applicability analysis
stays in the parent chat.

## Expand Sources

After an `expert_digest`, Панэкс can reveal selected sources without rerunning
the full search:

```text
Панэкс, раскрой по Рефату.
Панэкс, покажи источники.
Панэкс, что там в комментариях?
Панэкс, самый спорный источник.
```

Equivalent CLI shape:

```bash
panex expand --source-keys refat:238 --save --receipt-json
panex expand --source-keys refat:238 --max-comments-per-source 3 --save --receipt-json
```

`source_expand` is exact source lookup. It is not a new search, not a new
digest, and not a raw dump of every source.

Default expansion limits are explicit in the API response: `max_content_chars`
is `20000` per source and `max_comments_per_source` is `50` per source, with
direct comments and author-supplied external links included by default. If the
response says `content_truncated=true` or `comments_truncated=true`, ask Панэкс
to expand the same source with higher limits.

Default `expert_digest` is generated by the backend LLM from all selected
source refs, comment snippets, external-link refs, and returned key signals.
Digest caps are opt-in environment overrides: `0` means "all selected evidence"
for count/char caps. The supported caps are
`AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS`,
`AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS`,
`AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE`,
`AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS`,
`AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE`,
`AGENT_CONTEXT_DIGEST_MAX_SIGNALS`, and
`AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS`. `digest.source_index` keeps handles
for all selected sources so follow-up expansion can target exact evidence.

## Raw/Audit Mode

Use raw `source_bundle` only when explicitly needed for audit/debug:

```bash
panex ask --query "..." --experts refat,akimov --response-mode source_bundle --save --receipt-json
```

Default Панэкс answers should use `expert_digest`.

## Diagnostics

Check local/global setup:

```bash
panex doctor
```

Run a tiny live production check:

```bash
panex doctor --live
```

`panex doctor` reports whether the token is configured, but does not print the
token value.

Clean up old local artifacts:

```bash
panex cleanup
```

Default retention is 7 days. Override it with `PANEX_ARTIFACT_TTL_DAYS` or
`panex cleanup --ttl-days 14`.

## Boundaries

- Панэкс must be invoked explicitly.
- Панэкс is not default web search.
- Панэкс should not be called automatically for every trends/software/architecture question.
- Production calls go to `https://experts-panel.fly.dev`.
- Localhost is used only through explicit `--local` or `--api-url`.
- Saved artifacts live outside the current repo by default and may contain
  project-sensitive queries/responses.
- External links are not opened, crawled, cloned, or summarized by default.
- Drift comment groups are not selected by default; current API only includes
  direct comments under selected `main_sources`.
- Practitioner posts and comments are opinion evidence, not proof of truth.
