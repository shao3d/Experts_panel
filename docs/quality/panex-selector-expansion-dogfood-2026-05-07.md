# Panex Selector Expansion Dogfood - 2026-05-07

**Scope:** AND-23 BDD/product dogfood for selector-based source expansion UX.

This run checks the second-step Панэкс workflow after a digest answer: the user
can ask in ordinary Russian to reveal sources, comments, weak spots, or a named
expert's evidence without knowing `source_key` / `source_expand` terminology.

## Local BDD Guardrails

Six AND-23 scenarios were added to
`backend/tests/fixtures/panex_quality_scenarios.json`:

| Scenario | Intent | Result |
|----------|--------|--------|
| `and23_expand_named_expert` | "раскрой по Рефату" selects top previous source for Refat | passed, score `0.890` |
| `and23_expand_claim` | "этот вывод" maps to supporting sources for a claim | passed, score `0.972` |
| `and23_expand_comments_focus` | comments selector stays `source_expand` and comments-first | passed, score `0.972` |
| `and23_expand_weak_sources` | weak-source selector preserves caveats and weak-signal framing | passed, score `0.972` |
| `and23_ambiguous_selector_clarifies` | ambiguous selector asks one clarification instead of guessing | passed, score `1.000` |
| `and23_no_previous_digest_boundary` | missing previous digest does not invent handles or call expand | passed, score `1.000` |

Full evaluator run over the old six golden scenarios, five AND-22 scenarios,
and six AND-23 scenarios:

```text
backend/.venv/bin/python backend/scripts/panex_quality_eval.py \
  --answers-dir backend/test_results/panex_quality_eval/answers \
  --report-path backend/test_results/panex_quality_eval/latest.json

panex_quality_eval: passed (17 passed, 0 failed, 0 needs_answer)
```

Contract/evaluator tests:

```text
backend/.venv/bin/python -m pytest \
  backend/tests/test_panex_quality_eval.py \
  backend/tests/test_experts_panel_researcher_contract.py \
  -q -o addopts=''

29 passed
```

## Production Dogfood

Панэкс was called against Fly.io production, not localhost.

Digest request:

```text
query_sent: Когда subagents реально помогают в AI-разработке, а когда только усложняют workflow?
experts_sent: refat, akimov, doronin
response_mode: expert_digest
target: https://experts-panel.fly.dev/api/v1/agent/context
warnings: none
latency: 79559 ms
```

Digest signals used handles including `refat:239`, `refat:238`, `refat:220`,
`doronin:73`, `doronin:110`, `doronin:177`, `doronin:263`, and `doronin:261`.

Follow-up 1:

```text
user-style selector: "раскрой по Рефату"
source_keys_sent: refat:239
target: https://experts-panel.fly.dev/api/v1/agent/context/expand
mode: source_expand
warnings: none
latency: 12 ms
```

Observed behavior:

- Панэкс selected the top Refat source from the previous digest.
- It did not run a new `expert_digest` / `source_bundle`.
- It returned a lean Evidence Note: what `refat:239` says, what comments add,
  external refs as author-supplied references only, and whether the source
  supports or changes the previous digest.

Follow-up 2:

```text
user-style selector: "что там в комментариях по самому спорному или слабому источнику?"
source_keys_sent: doronin:73
target: https://experts-panel.fly.dev/api/v1/agent/context/expand
mode: source_expand
warnings: none
latency: 15 ms
```

Observed behavior:

- Панэкс selected `doronin:73` because the previous digest marked it as
  caveated/comment-heavy: `confidence=medium`, `depth=moderate`,
  `comment_signal=mostly_noise`.
- It stated that no obviously weaker source was visible and did not invent a
  fresh ranking.
- It focused on direct comments and separated useful comment signal from noise.
- It did not open external links, print raw JSON, or expose the token.

## Product Observations

- The selector UX works as intended for the most valuable day-to-day case:
  digest -> "раскрой по <эксперту>" -> exact `source_expand`.
- Weak/comment-focused expansion is useful, but depends on the previous digest
  preserving enough `evidence_quality`, caveat, and comments metadata.
- The no-call BDD scenarios matter: the correct behavior for ambiguous selector
  or missing previous digest is not a clever guess, but one short clarification
  or a request to ask the main Панэкс question first.
- AND-23 added no backend API behavior. It is an agent-contract and
  product-quality guardrail slice over the already deployed `expert_digest` and
  `source_expand` endpoints.

## Verdict

AND-23 passed local BDD guardrails and production dogfood. The main remaining
limitation is context continuity: if the parent/subagent loses the previous
digest handles, selector expansion should stop and ask for a new main digest.
That is the reason `Digest Snapshot And Result IDs` remains a plausible later
upgrade, but it is not required for this slice.
