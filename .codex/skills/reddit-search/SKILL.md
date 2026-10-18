---
name: reddit-search
description: Use when the user explicitly asks to search Reddit, check Reddit discussions, or find practitioner/community sentiment. Calls the official Experts Panel Reddit Search V2 API through the portable reddit-search command; returns source-grounded answers with real Reddit links and honestly reports abstention without inventing results.
---

# Reddit Search V2

Use this skill only for explicit Reddit/community research requests. Do not use it
for generic web research or ordinary code review.

## Invocation

From any project directory, run:

```bash
reddit-search "<user question>"
reddit-search "<user question>" --recent
reddit-search --json "<user question>"
reddit-search --doctor
```

If `reddit-search` is not on PATH, use the installed runner path from the
installation report. Do not run the repository backend module and do not call
`reddit-proxy` directly.

The runner uses `REDDIT_SEARCH_API_URL` when set; otherwise it uses the configured
Experts Panel production endpoint. It reads the Reddit-only
`REDDIT_SEARCH_API_TOKEN`, with `AGENT_CONTEXT_API_TOKEN` retained only as a
backward-compatible owner fallback. On macOS it can read the Reddit-only token
from login Keychain (service `com.experts-panel.reddit-search`, account
`reddit-search`) when neither env variable is present. Never print, echo, inspect,
copy, or include either token in a prompt, response, artifact, or log.

## Query handling

- Preserve the user's question; do not add project context unrelated to Reddit.
- Use `--recent` only when the user asks for recent/current/latest changes or
  explicitly requests a recent-only search.
- Use `--json` when structured processing is useful; otherwise use human output.
- Use `--doctor` only to diagnose reachability/auth configuration. It does not
  run a search and does not require a token.

## Result handling

- `completed`: summarize the returned answer, preserving uncertainty, and cite
  the returned real Reddit URLs. Do not claim that a source says more than the
  API response supports.
- `abstained`: read `abstain_reason` before wording the answer.
  - `insufficient_coverage` — retrieval worked, but the sources do not establish
    the central request. Report that sufficiently reliable Reddit evidence was
    not found; this is a valid result with exit code 0.
  - `no_verified_sources` — nothing passed the confidence/evidence filter.
  - `degraded` (or `"degraded": true`) — a pipeline stage failed. This is an
    OPERATIONAL failure, not evidence that Reddit has no material on the topic:
    say so explicitly and do not present it as "nothing found".
  Do not fill any abstain with general knowledge.
- `completed` with `"degraded": true` — the shortlist was produced while a stage
  was failing: keep the answer but disclose that it may be incomplete.
- `completed` where `kept N` is small: the CLI appends how many of the kept
  sources are quote-verified (`all quote-verified` / `none quote-verified`). A
  thin but verified shortlist is evidence-backed; do not describe it as a
  failed search.
- exit code 1 / technical error: report a short operational failure and do not
  present a partial answer as completed.
- Never expose hidden prompts, credentials, stack traces, internal proxy details,
  or raw diagnostic secrets.

## Response format in chat

Keep the final answer concise:

1. one-sentence conclusion;
2. key practitioner patterns or caveats from the returned synthesis;
3. 2–5 source links from the response;
4. explicit note if the result was abstained or technically failed.

The underlying API already performs query formulation, Scout, multi-channel
retrieval, deduplication, enrichment, comment reading, answerability rerank,
confidence filtering, and synthesis. The skill must not reproduce that pipeline
or invent a second interpretation layer pretending to be Reddit evidence.

## Safety boundaries

- Use only the official agent-facing API through `reddit-search`.
- Never access `reddit-proxy:3000` directly.
- Never use Reddit credentials directly.
- Never update a database, deploy, restart services, or modify the current
  project merely to answer a Reddit question.
- Keep the current project's files out of the query unless the user explicitly
  asks for a project-specific Reddit search and the context can be safely
  summarized without secrets.
