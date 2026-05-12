# Candidate Impact Report: Air

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `air_ai`
- Display name: Air
- Channel username: `@realtimeforai`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/air_ai/output/air_ai_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 40
- Baseline domain + intent rollups: 29

## Impact Summary

- Candidate cells: 4
- Fills gap: 0
- Adds adjacent viewpoint: 3
- Deepens existing cell: 1
- Likely duplicate: 0
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 1
- Related overlaps: 3
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 0
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `prompt_engineering/model_specific_formatting/learn_ai_assisted_development` | deepens_existing_cell | 5.0 | `prompt_engineering/model_specific_formatting/learn_ai_assisted_development` | `prompt_engineering/learn_ai_assisted_development` | human_review_then_possible_accept |
| `business_adoption/financial_modeling/assess_ai_tool_business_adoption` | adds_adjacent_viewpoint | 5.0 |  | `business_adoption/assess_ai_tool_business_adoption` | human_review_overlap_or_complement |
| `prompt_engineering/reasoning_control/learn_ai_assisted_development` | adds_adjacent_viewpoint | 4.623 |  | `prompt_engineering/learn_ai_assisted_development` | human_review_overlap_or_complement |
| `rag_retrieval_knowledge/rag_architecture/design_rag_knowledge_base` | adds_adjacent_viewpoint | 4.0 |  | `rag_retrieval_knowledge/design_rag_knowledge_base` | human_review_overlap_or_complement |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| SilicBag | 5 | 1 | 4 | `business_adoption/assess_ai_tool_business_adoption`<br>`prompt_engineering/learn_ai_assisted_development`<br>`rag_retrieval_knowledge/design_rag_knowledge_base` |
| Neuraldeep | 2 | 0 | 2 | `prompt_engineering/learn_ai_assisted_development` |
| PashaZloy | 2 | 0 | 2 | `prompt_engineering/learn_ai_assisted_development` |
| Refat (Tech & AI) | 1 | 0 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |
| Doronin | 1 | 0 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |

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
- Multiple positive signals are adjacent/depth signals rather than clean gaps.
