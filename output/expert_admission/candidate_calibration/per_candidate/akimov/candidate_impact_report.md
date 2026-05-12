# Candidate Impact Report: Akimov

## Preliminary Recommendation

- Recommendation: `probe_needed`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `akimov`
- Display name: Akimov
- Channel username: `@ai_product`
- Passport cells: 2
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/akimov/output/akimov_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 42
- Baseline domain + intent rollups: 28

## Impact Summary

- Candidate cells: 2
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 1
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 1
- Related overlaps: 0
- Overlap-heavy caveat: False
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 1

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.811 | `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_product_pm/adoption_roadmaps/assess_ai_tool_business_adoption` | fills_gap | 4.311 |  |  | human_review_then_possible_accept |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Doronin | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Tech_AI_grabli | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Etechlead | 1 | 0 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Ilia Izmailov | 1 | 0 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Kornishev | 1 | 1 | 0 | `coding_agents/design_agentic_dev_workflow` |

## Taxonomy Flags

No candidate taxonomy extensions.

## Limitations

- Diagnostic-only report; it does not make a final admission decision.
- Comparison is deterministic over passport matrix_export cells and matrix rollups.
- It does not inspect raw posts, runtime retrieval behavior, embeddings, or source_bundle quality.
- LLM arbitration is still useful for borderline duplicate-vs-complement cases.

## Next Action

Run a deeper candidate probe only if the candidate is strategically important.
