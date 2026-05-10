# Research Channels Operating Model

This guide defines the human-facing research modes for Andrey's Codex workflow.
The goal is to avoid duplicate "search channels" and keep each request routed
by intent.

## Short Rule

Use four modes only:

1. `Панэкс`
2. `Вебсёрчер`
3. `Вебсёрчер под Хафт`
4. `Дипресёрчер`

Do not expose `Harvester standard` as a separate everyday channel. It is the
mandatory extract-backed reading step inside `Вебсёрчер под Хафт`.

## 1. Панэкс

Use when the user wants Experts Panel evidence.

What it does:

- queries Experts Panel only;
- uses `expert_digest` by default;
- uses `source_expand` only after a previous digest or explicit source handles;
- keeps expert separation and source handles;
- does not browse the public web, Reddit, Video Hub, or Harvester.

Typical phrases:

- "Панэкс, спроси Refat и Akimov..."
- "Панэкс, что думают эксперты про..."
- "Панэкс, раскрой подробнее по Рефату..."
- "Панэкс, покажи источники по этому выводу..."

Boundary:

- Панэкс returns expert/practitioner evidence, not proof of truth.
- Project-specific verdicts stay in the parent chat, not inside Панэкс.

## 2. Вебсёрчер

Use when the user wants a fast external-world overview.

What it does:

- uses web search, Tavily, and Reddit when useful;
- prefers official/current sources for factual claims;
- uses Reddit as community/practitioner signal;
- deduplicates overlapping findings;
- returns a concise synthesis with links and caveats.

Typical phrases:

- "Вебсёрчер, быстро найди..."
- "Посмотри, что сейчас пишут..."
- "Проверь актуальность..."
- "Посмотри Reddit и официальные источники..."

Boundary:

- This is a fast overview, not a decision-grade packet.
- It does not call Панэкс by itself.
- It does not run Harvester deep.

## 3. Вебсёрчер под Хафт

Use when the user wants decision-grade external evidence for a later Haft
analysis.

Current implementation:

- global Codex agent: `/Users/andreysazonov/.codex/agents/web-researcher.toml`;
- trigger mode: `Pre-Haft Evidence Packet mode`;
- Harvester target: private VPS sidecar through SSH, `deploy@153.75.248.11`;
- Harvester API from VPS: `http://127.0.0.1:8000`;
- required Harvester request mode: `POST /research` with `mode=standard`.

What it does:

1. Runs discovery like normal `Вебсёрчер`:
   - web;
   - Tavily;
   - Reddit/community signals where relevant;
   - official/current sources where possible.
2. Selects key sources for the decision.
3. Always runs `Harvester standard` on the key sources:
   - search;
   - extract;
   - compact evidence packet.
4. Returns a Haft-ready packet:
   - findings;
   - risks;
   - disagreements;
   - unknowns;
   - candidate comparison dimensions;
   - source quality labels.

The global `web_researcher` must surface the Harvester `job_id`, final
`status`, `error`/warnings when present, and `citation_integrity`. If Harvester
is unavailable or returns degraded citation integrity, the packet is incomplete
and must say so explicitly.

Important waiting rule:

- `web_researcher` must not return a final pre-Haft packet while Harvester is
  still `running`, `queued`, or otherwise non-terminal.
- `citation_integrity: null` means the Harvester report is not ready yet.
- If the agent is interrupted or times out before Harvester reaches
  `completed`, `failed`, or `error`, it should return only an explicit
  incomplete status with the `job_id` and current status, not a decision-grade
  packet.

Typical phrases:

- "Вебсёрчер, собери фактуру под Хафт..."
- "Собери evidence packet под решение..."
- "Подготовь материал для Хафт-анализа..."
- "Сначала research packet, потом Хафт..."

Boundary:

- It does not make the final decision.
- It should separate extracted/read sources from search-only discovery.
- Harvester standard is mandatory for the key decision sources.
- It should not run Harvester deep unless the user explicitly asks for
  `Дипресёрчер` / `deep research`.
- It should not pretend a source was read merely because it appeared in search;
  source reading must be backed by Harvester `citation_integrity`.

## 4. Дипресёрчер

Use when the user explicitly wants a long, full-depth Harvester research run.

What it does:

- runs Harvester deep research;
- uses the multi-agent Hermes workflow;
- includes critic/fact-checking behavior;
- waits for a long-running report;
- expects minutes or tens of minutes, not a quick answer.

Typical phrases:

- "Дипресёрчер, глубоко исследуй..."
- "Сделай deep research..."
- "Harvester на полную катушку..."
- "С мультиагентами, критикой и fact-checking..."

Boundary:

- It is explicit-only.
- It should not be triggered by ordinary "найди" or "посмотри".
- It is for expensive/ambiguous/high-stakes external research questions.

## Routing Summary

| User intent | Mode |
|---|---|
| Expert/practitioner posts from Experts Panel | `Панэкс` |
| Fast public web/current/community overview | `Вебсёрчер` |
| Decision-grade external evidence for Haft | `Вебсёрчер под Хафт` |
| Long multi-agent external deep research | `Дипресёрчер` |

## Anti-Overlap Rules

- Панэкс is not web search.
- Вебсёрчер is not a decision packet unless the user asks for Haft/evidence.
- Вебсёрчер под Хафт always includes Harvester standard over key sources.
- Дипресёрчер is the only mode that runs Harvester deep by default.
- If the user asks for both a fast overview and a Haft packet, provide two
  clearly separated layers: fast overview first, then Haft-ready packet.
