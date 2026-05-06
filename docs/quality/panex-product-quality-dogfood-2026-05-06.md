# Panex Product Quality Dogfood - 2026-05-06

**Status:** passed with caveats
**Scope:** AND-21 golden product-quality scenarios

This run evaluates final `Панэкс` answers, not only the Agent Context API JSON
contract. The answers were produced by the real `experts_panel_researcher`
subagent against the production Fly.io Experts Panel endpoint.

## What Was Run

Six golden scenarios from `backend/tests/fixtures/panex_quality_scenarios.json`:

| Scenario | Selection | Result |
|----------|-----------|--------|
| `subagents_tradeoff` | `refat`, `akimov`, `doronin` | passed, score `0.970` |
| `context_rot` | group `tech_business` | passed, score `0.985` |
| `file_first_embeddings` | `refat`, `doronin`, `kornish` | passed, score `0.977` |
| `llm_caching_recent` | `refat`, `akimov`, recent-only | passed, score `0.944` |
| `weak_signal_probe` | `refat`, `akimov`, `doronin` | passed, score `0.896` |
| `expand_sources_followup` | `source_expand` for `refat:238`, `doronin:1066` | passed, score `0.924` |

Evaluator command:

```bash
backend/.venv/bin/python backend/scripts/panex_quality_eval.py \
  --answers-dir backend/test_results/panex_quality_eval/answers \
  --report-path backend/test_results/panex_quality_eval/latest.json
```

Result:

```text
panex_quality_eval: passed (6 passed, 0 failed, 0 needs_answer)
```

## Source Handle Audit

After the evaluator run, all unique source handles emitted by Панэкс were checked
against production `source_expand` with minimal content/comments limits.

Result:

```text
source_expand warnings: none
not_found: none
validated_source_keys: 44
```

This verifies that the final answers did not invent `source_key` handles.

## Findings

Strengths:

- Панэкс consistently returned a Request passport for digest scenarios.
- Answers were source-backed and included real `source_key` handles.
- The agent did not return raw JSON as final output.
- The agent preserved practitioner-signal framing instead of proof framing.
- External links were treated as author-supplied references and were not
  presented as fetched/verified external evidence.
- `weak_signal_probe` correctly avoided claiming strong direct evidence for
  tiny one-file subagent tasks.
- `source_expand` follow-up used exact handles and did not run a new digest.

Caveats:

- Answers are usually too long for the current product target. Brevity failed
  as a non-critical check in several scenarios:
  - `subagents_tradeoff`: `11714` chars vs target `6500`;
  - `context_rot`: `9686` chars vs target `7500`;
  - `file_first_embeddings`: `10654` chars vs target `7000`;
  - `llm_caching_recent`: `7050` chars vs target `6000`;
  - `weak_signal_probe`: `7061` chars vs target `6500`.
- `weak_signal_probe` did not suggest a targeted expansion follow-up even though
  the scenario expected one. The answer was still useful, but this is a good
  instruction-tuning signal.
- `expand_sources_followup` used a lean source-expand passport
  (`source_keys_sent`, `mode`, `target`) rather than the full digest Request
  passport (`query_sent`, `experts_sent`, `response_mode`, `warnings`). The
  evaluator scored this lower, but the format is appropriate for `source_expand`.

## Product Verdict

The product-quality layer is useful. It caught meaningful non-critical issues
that API tests cannot catch: answer length, missing expansion suggestion, and
passport differences between digest and expand modes.

The current Панэкс behavior is good enough for real dogfood as an explicit
research helper, with one clear next tuning target: make default answers more
compact while preserving source handles, caveats, and practical decision help.

