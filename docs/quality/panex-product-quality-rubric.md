# Panex Product Quality Rubric

**Status:** AND-21 initial rubric
**Last updated:** 2026-05-06

This rubric checks the product quality of the `Панэкс` / `experts_panel_researcher`
answer after the Agent Context API has already returned `expert_digest` or
`source_expand` data.

It is intentionally separate from API contract tests:

- API tests prove that Fly.io, auth, selection, retrieval, digest shape,
  `source_refs`, `source_index`, and `evidence_quality` work.
- Product-quality eval checks whether the final subagent answer is useful to a
  human who asked for expert/practitioner signals.

## Core Principle

Панэкс must treat the database as a collection of practitioner posts and
comments, not as a ground-truth oracle.

The answer should therefore frame output as:

- source-backed signals;
- practitioner positions;
- convergence / divergence;
- caveats and missing evidence;
- practical decision help.

It must not frame practitioner opinions as proof.

## Required Answer Qualities

| Dimension | What Good Looks Like |
|-----------|----------------------|
| Request fidelity | The answer preserves the actual user query, selected experts/group, response mode, target, and warnings in a compact Request passport. |
| Source grounding | Important claims reference `source_key` handles such as `refat:234`, or clearly name the source handles used. |
| Signal honesty | The answer says "signals", "по источникам", "мнение", "похоже", "ограничение", "слабый сигнал" when evidence is not strong. |
| Coverage | The answer covers the scenario-specific asks, not just a generic summary. |
| Decision usefulness | The answer helps the user decide what to do: criteria, trade-offs, when yes/no, risks, next steps. |
| Nuance preservation | The answer keeps caveats, disagreement, and low-confidence areas visible. |
| Brevity | The answer is compact enough for the parent chat, not a raw digest dump. |
| Expand path | When deeper audit is useful, the answer suggests a targeted source/comment expansion step. |
| External boundary | External links are listed as author-supplied references only; Панэкс must not claim it opened/fetched/crawled them unless explicitly asked and actually did so. |

## Compact Default

Default `expert_digest` answers should fit a parent-agent chat, not read like a
full analyst report. Target range is roughly `3500-6000` characters, with a soft
ceiling around `6500` unless the user explicitly asks for a deep/full answer.

Good compact shape:

- compact Request passport;
- short take / "Короткий вывод" in 2-4 sentences;
- 3-5 source-backed signals with `source_key` handles;
- 2-4 practical decision bullets;
- limits and next expansion with 1-3 concrete `source_key` handles when deeper
  audit would help.

Long reports are acceptable only when the user explicitly asks for that style,
for example "подробно", "глубоко", "разверни", "полный отчёт", "full report",
or "deep analysis".

For `source_expand`, the correct passport is intentionally lean:
`source_keys_sent`, `target`, `mode`, and `warnings`. It does not need
`query_sent`, `experts_sent`, or `response_mode`, because expansion is an exact
lookup over source handles from a previous digest.

## Red Flags

- The final answer is raw JSON or a near-raw digest dump.
- It hides which experts/group were queried.
- It gives strong conclusions without source handles or caveats.
- It uses proof framing such as "доказано" or "scientifically proven" for
  practitioner opinions.
- It silently changes the user scope.
- It automatically invokes Reddit, external browsing, GitHub cloning, or link
  summarization when the user only asked Панэкс.
- It expands every raw source instead of proposing a targeted `source_expand`
  follow-up.
- It produces a long report by default when a compact Signals answer would be
  enough.

## Current Eval Tool

The first deterministic evaluator is:

```bash
backend/.venv/bin/python backend/scripts/panex_quality_eval.py \
  --scenario-id subagents_tradeoff \
  --answer-file /path/to/panex_answer.md \
  --digest-dir /path/to/digests \
  --report-path backend/test_results/panex_quality_eval/latest.json
```

For production dogfood, add `--live` and pass the Fly endpoint explicitly only
when you intentionally want a fresh production digest:

```bash
backend/.venv/bin/python backend/scripts/panex_quality_eval.py \
  --scenario-id subagents_tradeoff \
  --answer-file /path/to/panex_answer.md \
  --live \
  --api-url https://experts-panel.fly.dev/api/v1/agent/context \
  --report-path backend/test_results/panex_quality_eval/latest.json
```

The evaluator is a guardrail, not an oracle. It catches structural and product
quality regressions. Human review is still the final judge for the first
golden scenarios.
