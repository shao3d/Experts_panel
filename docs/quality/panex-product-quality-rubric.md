# Panex Delivery Quality Rubric

**Status:** AND-28 relay-only delivery BDD guardrail
**Last updated:** 2026-05-15

This rubric checks the delivery quality of the `Панэкс` /
`experts_panel_researcher` answer after the Agent Context API has already
returned `expert_digest` or `source_expand` data.

It is intentionally separate from API contract tests:

- API tests prove that Fly.io, auth, selection, retrieval, digest shape,
  `source_refs`, `source_index`, and `evidence_quality` work.
- Delivery-quality eval checks whether the subagent faithfully delivers the
  Panel's digest/source expansion without becoming a second summarizer.

## Core Principle

Панэкс must be a relay-only delivery layer over practitioner posts and comments,
not as a ground-truth oracle and not as a second reducer.

For default `expert_digest`, Панэкс must not summarize the digest again. It
should deliver backend digest fields with minimal wrapping:

- compact Request passport;
- scope and warnings;
- per-expert `digest.position`, `digest.key_signals`, `digest.source_refs`,
  `digest.comments_digest`, and `digest.omitted_counts`;
- expansion candidates for targeted `source_expand`.

It must not frame practitioner opinions as proof.

## Required Answer Qualities

| Dimension | What Good Looks Like |
|-----------|----------------------|
| Request fidelity | The answer preserves the actual user query, selected experts/group, response mode, target, and warnings in a compact Request passport. |
| Source grounding | Important claims reference `source_key` handles such as `refat:234`, or clearly name the source handles used. |
| Signal honesty | The answer says "signals", "по источникам", "мнение", "похоже", "ограничение", "слабый сигнал" when evidence is not strong. |
| Coverage | The answer covers the scenario-specific asks, not just a generic summary. |
| Relay fidelity | The answer preserves backend digest fields and does not create a new meta-synthesis, fresh ranking, or project verdict. |
| Nuance preservation | The answer keeps caveats, disagreement, and low-confidence areas visible. |
| Proportionality | The answer is as large as the backend digest requires: not a raw JSON dump, but not shortened or second-summarized. |
| Expand path | When deeper audit is useful, the answer suggests a targeted source/comment expansion step. |
| External boundary | External links are listed as author-supplied references only; Панэкс must not claim it opened/fetched/crawled them unless explicitly asked and actually did so. |

## AND-22 Adversarial BDD Checks

AND-22 adds product-behavior scenarios rather than backend API scenarios. They
stress Панэкс as a user-facing research helper:

- faithful default digest delivery for ordinary expert questions;
- weak-signal honesty for small/single-file subagent questions;
- human Russian follow-up expansion without requiring `source_key` jargon;
- external-link boundary when sources mention GitHub/repos/tools;
- exact expert-scope discipline when the user says "only these experts".

The evaluator remains deterministic and non-oracular. It now supports
scenario-specific `forbidden_terms` for obvious product failures such as
silently broadening expert scope, claiming external fetches, or turning weak
signals into strong facts.

## AND-23 Selector Expansion BDD Checks

AND-23 tests the second-step workflow after a digest answer: Андрей can ask in
plain Russian to reveal the evidence without saying `source_key`,
`source_expand`, or `Evidence Note`.

Covered selector behaviors:

- named expert: "раскрой по Рефату" -> top 1 source for that expert from the
  previous digest;
- claim selector: "этот вывод" / "этот тезис" / "на чём основано" ->
  `key_signal.supporting_sources` when the previous digest clearly points to a
  specific claim;
- comments selector: "что там в комментариях" -> `source_expand` over the
  relevant source, with the final answer focused on direct comments/noise;
- weak-source selector: "слабые места" / "самый спорный источник" -> previous
  digest `evidence_quality`, caveats, and comments signals, not a fresh ranking;
- ambiguity boundary: if the selector can point to several experts, claims, or
  sources, Панэкс asks one short clarification instead of guessing;
- no-previous-digest boundary: if the agent has no digest/source handles in
  context, it does not run `source_expand` and does not invent handles from
  memory.

Default expansion stays intentionally narrow: top 1 source per named expert and
top 1-2 for generic "покажи источники". Expanding all sources is allowed only
when the user explicitly asks for all/raw/concrete handles.

The evaluator supports no-call `clarification` and `boundary` scenarios. Those
scenarios intentionally do not require a Request passport or source handles,
because a Request passport would imply that the agent actually called the API.

## AND-28 Relay-Only Digest Delivery

AND-28 changes default `expert_digest` output from synthesis to delivery.
Панэкс is still useful as the safe cross-repo protocol layer: it calls Fly.io,
saves artifacts, reads slices, preserves scope/warnings, and exposes source
handles. It should not add another semantic reduce pass over the digest.

Good default delivery shape:

- Request passport;
- Scope and warnings;
- Expert digest delivery;
- Expansion candidates.

Red flags:

- it creates a new meta-synthesis over already reduced digest fields;
- it adds practical decision bullets, go/no-go recommendations, or project
  applicability;
- it reranks experts or sources beyond the order/calibration returned by the
  digest;
- it hides `source_refs`, `comments_digest`, `omitted_counts`, or warnings.

## Faithful Digest Delivery

Default `expert_digest` answers should faithfully deliver the backend-generated
digest fields. Панэкс may clean formatting, but must not shorten, rerank, or
second-summarize the digest into a new analysis.

Good delivery shape:

- compact Request passport;
- scope and warnings;
- per-expert digest delivery with `source_key` handles;
- limits and next expansion with concrete handles when deeper audit would help.

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
- It second-summarizes the `expert_digest` into a new overall verdict.
- It adds project-specific go/no-go or implementation recommendations.
- It silently changes the user scope.
- It automatically invokes Reddit, external browsing, GitHub cloning, or link
  summarization when the user only asked Панэкс.
- It expands every raw source instead of proposing a targeted `source_expand`
  follow-up.
- It guesses `source_key` handles from memory or names alone when no previous
  digest/source handle context is available.
- It runs a new `expert_digest` / `source_bundle` to satisfy an expansion phrase
  such as "раскрой по Рефату" unless the user explicitly asked to refresh or
  ask a new main question.
- It shortens, reranks, or re-summarizes the backend-generated `expert_digest`
  instead of cleanly delivering the digest fields returned by the Panel.

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
