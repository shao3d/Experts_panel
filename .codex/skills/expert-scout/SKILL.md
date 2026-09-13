---
name: expert-scout
description: Use when the user explicitly asks to involve Scout / expert-scout / «Скаут» / «задействуй Скаута» / «сырой поиск по экспертам» for agentic read-only mining over the Experts Panel Telegram practitioner corpus. Runs the no-shell scout and returns findings with source_key citations and honest gaps. Not for Reddit (reddit-search) and not for the Panex digest (panex ask).
---

# Expert Scout

Read-only agentic search over the Experts Panel Telegram practitioner corpus.
Unlike Panex (a ready compact digest) and `reddit-search` (community sentiment),
Scout iteratively searches the corpus, reads primary sources, and returns
findings with `source_key` citations and explicit gaps.

## When to use

Trigger only on explicit user phrases such as:

- "Скаут", "expert-scout", "задействуй Скаута", "погоняй Скаута",
  "сырой поиск по экспертам", "посмотри по корпусу экспертов".

Do not trigger automatically for generic research. Do not confuse with:

- `reddit-search` — Reddit/community discussions;
- Panex (`panex ask`) — a ready digest over selected experts.

## Invocation

On the Mac (Codex chat or terminal):

```bash
expert-scout "<bounded question>"
```

If the command is missing from PATH, use `~/.local/bin/expert-scout`. If the
bridge itself is missing, install it from the Experts Panel repo:

```bash
scripts/install_expert_scout_skill.sh --with-shim
```

On the VM (opencode), from the repository root (or use the absolute path):

```bash
./scripts/expert_scout.sh "<bounded question>"
/home/ubuntu/apps/experts-panel/dev/scripts/expert_scout.sh "<bounded question>"
```

A run takes roughly 15 seconds to a few minutes. If the harness asks for a
command timeout, allow up to 300 seconds; raise it with `EXPERT_SCOUT_TIMEOUT`
(seconds) when needed. Never open the corpus database directly and never call
the helper outside the sanctioned wrapper or the no-shell `scout` plugin tool.

## Expert scope

Scout searches all experts by default and has no group flag. To scope, name the
expert ids inside the question, for example:

- "по визуалам" → append: `Ограничь визуальными экспертами: acidcrunch, strangedalle`
- a named expert → include the id or display name in the question.

Do not silently broaden or narrow the expert scope.

## Query handling

- Keep the user's question; add facets only when the user asks for breadth.
- Prefer failure language ("camera drift", "lost branding", "wake stops",
  "invented angles") together with the positive phrasing.
- Do not paste secrets, `.env`, tokens, or private project data into the query.
- Keep the question short: the scout agent performs its own facet decomposition
  and query reformulation.

## Result handling

- The scout answer is already curated: findings with `source_key` + dates,
  concrete techniques, gaps, and the list of queries it ran. Deliver it and do
  not add a second interpretation layer.
- Preserve `source_key` values so the user can ask follow-ups.
- An honest "в корпусе нет сигнала" is a valid result; never replace it with
  general knowledge.
- Exit codes: `0` — answer (including "no signal"); `3` — the agent produced no
  text (anomaly; inspect run artifacts on the VM); `124` — wrapper hard timeout
  (default `EXPERT_SCOUT_TIMEOUT=300`); other non-zero — operational failure.
  Report failures as technical problems, not as "no signal".
- Run artifacts live on the VM under `output/scout_runs/<timestamp>/`
  (`question.txt`, `events.jsonl`, `answer.md`, `meta.txt`).

## Response format in chat

1. one-sentence conclusion;
2. findings grouped by facet, each with `source_key` and date;
3. concrete techniques / fields / caveats when present;
4. gaps, weak or outdated signal;
5. keep the scout's "what I searched" list when it helps verification.

## Safety boundaries

- Read-only: Scout never writes to the corpus or to the current project.
- Do not print secrets, tokens, `.env` contents, or raw database dumps.
- Do not modify the Experts Panel repository, deploy, restart services, or touch
  the production database to answer a question.
- Media is never opened or analyzed.
