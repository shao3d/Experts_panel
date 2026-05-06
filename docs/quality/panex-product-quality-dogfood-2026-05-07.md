# Panex Adversarial Product Dogfood - 2026-05-07

**Scope:** AND-22 BDD-heavy adversarial product dogfood

This run evaluates final `Панэкс` answers under realistic user-style pressure:
compact default answers, weak evidence, human Russian follow-up expansion,
external-link boundaries, and exact expert scope discipline.

## Scenarios

Five AND-22 scenarios were added to
`backend/tests/fixtures/panex_quality_scenarios.json`:

| Scenario | Intent | Result |
|----------|--------|--------|
| `and22_compact_default_fresh` | Default digest should stay compact and useful | passed, score `0.972` |
| `and22_weak_signal_small_tasks` | Weak evidence should stay weak | passed, score `0.972` |
| `and22_human_followup_expansion` | Russian follow-up should trigger exact source expansion | passed, score `1.000` |
| `and22_external_links_boundary` | External links stay author-supplied references | passed, score `0.944` |
| `and22_scope_discipline_two_experts` | Exact two-expert scope is preserved | passed, score `0.969` |

Full evaluator run over the old six golden scenarios plus five AND-22 scenarios:

```text
backend/.venv/bin/python backend/scripts/panex_quality_eval.py \
  --answers-dir backend/test_results/panex_quality_eval/answers \
  --report-path backend/test_results/panex_quality_eval/latest.json

panex_quality_eval: passed (11 passed, 0 failed, 0 needs_answer)
```

## Product Observations

- Compact tuning worked on fresh production answers. AND-22 answer lengths were
  `4333`, `5887`, `4380`, `6346`, and `4664` characters, all inside their
  scenario limits.
- Weak-signal behavior was good: Панэкс explicitly said that there is no strong
  signal for subagents on tiny one-file tasks, then narrowed the positive case
  to reviewer/skeptic use.
- Human follow-up expansion worked without user-facing API jargon. The follow-up
  request used natural Russian, and Панэкс called `source_expand` over exact
  handles without rerunning a new digest.
- External-link boundary held: links were described as author-supplied
  references with `fetch_status=not_fetched`; Панэкс did not claim to open,
  fetch, crawl, clone, or verify them.
- Exact scope discipline held for `refat,akimov`: no extra experts were added.

## Tuning From Dogfood

The dogfood surfaced one useful evaluator gap: Панэкс may say
`Targeted Expansion Suggestion` or "расширять handles" instead of the literal
`source_expand`. That is acceptable human-facing wording, so
`panex_quality_eval.py` now accepts those phrases as a valid expansion path.

## Verdict

AND-22 passed as a BDD-heavy product check. The strongest remaining limitation
is not API correctness, but product review judgment: the deterministic evaluator
can catch structural regressions, while humans still need to judge whether a
specific synthesis is genuinely useful.
