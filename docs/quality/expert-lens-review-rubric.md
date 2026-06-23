# Expert Lens Review Quality Rubric

**Status:** Active guardrail for `expert-lens-review`
**Last updated:** 2026-05-28

This rubric checks the quality of an Expert Lens review after Panex has
returned `expert_digest` or `source_expand` evidence.

It is intentionally separate from Panex delivery quality:

- Panex quality checks whether `experts_panel_researcher` faithfully delivers
  the backend digest/source expansion.
- Expert Lens quality checks whether the parent Codex chat applies that
  evidence to a bounded project question without pretending to be the expert.

The gate is a process check, not a guarantee that the final judgment is true.

## Operating Model

Default control:

```text
Expert Lens run
-> Panex digest
-> targeted source_expand when needed
-> parent Codex interpretation
-> visible Lens quality gate
-> human decision boundary
```

For high-impact decisions, add one or more extra controls:

- negative-control expert;
- second expert with a different corpus;
- no-expansion baseline vs expanded-source run;
- human review of the applicability ledger.

## Required Quality Gates

| Gate | PASS | PARTIAL | FAIL |
| --- | --- | --- | --- |
| Bounded scope | One expert, one project target, one review question, and clear out-of-scope areas. | Scope is useful but slightly broad or inferred. | The answer reviews "the project" without a bounded target. |
| Project packet | Files, docs, or conversation artifacts are listed visibly. | Packet is summarized but not fully listed. | The user cannot tell what was actually reviewed. |
| Evidence handles | Non-trivial source-grounded claims cite `source_key` handles. | Some claims are digest-level only and labeled that way. | Important claims have no source handles or caveat. |
| Expansion rationale | Expanded source keys are justified, or digest-only mode is explicitly justified. | Rationale is present but thin. | Sources are expanded or omitted with no explanation. |
| Applicability labels | Important analogies use `Strong`, `Medium`, `Weak`, or `No signal`. | Labels are present but incomplete. | The answer treats all evidence as equally applicable. |
| Boundary hygiene | No expert simulation, no project verdict attributed to Panex or the expert, uncertainty is visible. | One phrasing is close to authority language but corrected by caveats. | The answer says or implies what the expert would decide for the project. |
| Decision boundary | The final answer says what the human should decide next. | Next step is implied but not crisp. | Panex/Codex appears to make the decision. |

## Compact Status

Normal Lens answers should include a compact status, not a large audit table:

```text
Lens quality gate: passed.
Weak point: digest was broad/noisy; expansion rationale included.
```

For imperfect but useful runs:

```text
Lens quality gate: partial.
Weak point: no expanded sources, so claims are digest-level only.
```

For failed runs:

```text
Lens quality gate: failed.
Weak point: no bounded project target; this is a normal Codex review, not an
Expert Lens review.
```

## Red Flags

- The output sounds like "<expert> would say".
- A source passport or matrix cell is treated as evidence.
- The parent Codex hides which project files or artifacts were reviewed.
- A broad/noisy digest is treated as a clean expert verdict.
- `source_expand` is skipped for weak, surprising, or high-impact claims.
- A negative-control run is forced into "no signal" when the corpus actually
  provides adjacent signal.
- The final answer lacks a human decision boundary.

## Dogfood Cases

Use these cases to test whether the skill is still behaving:

- Refat on the Expert Lens workflow itself.
- Refat on a real bounded architecture doc or PR.
- A weakly related expert on the same project question.
- Digest-only run compared with 1-3 expanded sources.
- A no-signal case where the skill should stop or downgrade to normal Codex
  review.
