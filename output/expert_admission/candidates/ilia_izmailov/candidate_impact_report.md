# Candidate Impact Report: Ilia Izmailov

## Preliminary Recommendation

- Recommendation: `promising_needs_human_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `ilia_izmailov`
- Display name: Ilia Izmailov
- Channel username: `@ilia_izmailov`
- Passport cells: 3
- Passport: `output/expert_admission/semantic_passports/ilia_izmailov/output/ilia_izmailov_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 5
- Baseline experts: 5
- Baseline exact cells: 14
- Baseline domain + intent rollups: 11

## Impact Summary

- Candidate cells: 3
- Fills gap: 1
- Adds adjacent viewpoint: 1
- Deepens existing cell: 0
- Likely duplicate: 0
- Taxonomy extension: 0
- Needs probe: 1
- Noise risk: 0
- Exact overlaps: 0
- Related overlaps: 2
- Overlap-heavy caveat: False
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 1

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | fills_gap | 4.774 |  |  | human_review_then_possible_accept |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | adds_adjacent_viewpoint | 4.434 |  | `coding_agents/choose_ai_coding_tool` | human_review_overlap_or_complement |
| `ai_product_pm/pm_workflow/plan_ai_product_feature` | needs_probe | 4.0 |  | `ai_product_pm/plan_ai_product_feature` | run_deeper_candidate_probe |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Polyakov | 2 | 0 | 2 | `ai_product_pm/plan_ai_product_feature`<br>`coding_agents/choose_ai_coding_tool` |
| AI Architect | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |

## Taxonomy Flags

No candidate taxonomy extensions.

## Limitations

- Diagnostic-only report; it does not make a final admission decision.
- Comparison is deterministic over passport matrix_export cells and matrix rollups.
- It does not inspect raw posts, runtime retrieval behavior, embeddings, or source_bundle quality.
- LLM arbitration is still useful for borderline duplicate-vs-complement cases.

## Next Action

Human review of overlap/complement signals, then continue with admission decision or targeted probe.
