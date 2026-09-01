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
backward-compatible owner fallback. Never print, echo, inspect, copy, or include
either token in a prompt, response, artifact, or log.

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
- `abstained`: report that sufficiently reliable Reddit evidence was not found.
  This is a valid result and exit code 0; do not fill it with general knowledge.
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
