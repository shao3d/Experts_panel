# Candidate Impact Report: Миша Карпов — AI, продукты и рост ⛳

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `control_misha_karpov`
- Display name: Миша Карпов — AI, продукты и рост ⛳
- Channel username: `@unknown_misha_karpov`
- Passport cells: 4
- Passport: `output/expert_admission/semantic_passports/control_misha_karpov/output/control_misha_karpov_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 6
- Baseline experts: 6
- Baseline exact cells: 17
- Baseline domain + intent rollups: 12

## Impact Summary

- Candidate cells: 4
- Fills gap: 1
- Adds adjacent viewpoint: 2
- Deepens existing cell: 0
- Likely duplicate: 1
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 1
- Related overlaps: 2
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/cursor_windsurf_copilot/learn_ai_assisted_development` | adds_adjacent_viewpoint | 4.434 |  | `coding_agents/learn_ai_assisted_development` | human_review_overlap_or_complement |
| `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow` | adds_adjacent_viewpoint | 4.396 |  | `agent_ops/design_agentic_dev_workflow` | human_review_overlap_or_complement |
| `ai_product_pm/pm_workflow/build_human_ai_workflow` | fills_gap | 4.189 |  |  | human_review_then_possible_accept |
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | likely_duplicate | 3.849 | `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | `ai_product_pm/plan_ai_product_feature` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Polyakov | 4 | 1 | 3 | `agent_ops/design_agentic_dev_workflow`<br>`ai_product_pm/plan_ai_product_feature`<br>`coding_agents/learn_ai_assisted_development` |
| AI Architect | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/learn_ai_assisted_development` |
| Neuraldeep | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Ilia Izmailov | 1 | 0 | 1 | `ai_product_pm/plan_ai_product_feature` |

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
- Multiple positive signals are adjacent/depth signals rather than clean gaps.
