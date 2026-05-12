# Candidate Impact Report: Kornishev

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `kornish`
- Display name: Kornishev
- Channel username: `@NGI_ru`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/kornish/output/kornish_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 42
- Baseline domain + intent rollups: 28

## Impact Summary

- Candidate cells: 4
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Deepens existing cell: 1
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 3
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 2

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | deepens_existing_cell | 4.849 | `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | `ai_product_pm/plan_ai_product_feature` | human_review_then_possible_accept |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.434 | `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/reasoning_control/improve_retrieval_quality` | fills_gap | 4.189 |  |  | human_review_then_possible_accept |
| `model_landscape/model_comparison/compare_models_for_task` | likely_duplicate | 4.283 | `model_landscape/model_comparison/compare_models_for_task` | `model_landscape/compare_models_for_task` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Etechlead | 3 | 1 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow`<br>`model_landscape/compare_models_for_task` |
| Polyakov | 3 | 1 | 2 | `ai_product_pm/plan_ai_product_feature`<br>`coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Doronin | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Tech_AI_grabli | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Akimov | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Ilia Izmailov | 2 | 0 | 2 | `ai_product_pm/plan_ai_product_feature`<br>`coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Elkornacio | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |

## Taxonomy Flags

No candidate taxonomy extensions.

## Limitations

- Diagnostic-only report; it does not make a final admission decision.
- Comparison is deterministic over passport matrix_export cells and matrix rollups.
- It does not inspect raw posts, runtime retrieval behavior, embeddings, or source_bundle quality.
- LLM arbitration is still useful for borderline duplicate-vs-complement cases.

## Next Action

Candidate is promising but overlap-heavy; require stronger human review before admission.

Density caveat:
- At least half of candidate cells overlap existing accepted coverage.
- Two or more candidate cells touch dense accepted rollups or exact cells.
- At least one candidate cell is an exact likely duplicate.
