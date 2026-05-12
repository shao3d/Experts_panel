# Candidate Impact Report: Refat (Tech & AI)

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `refat`
- Display name: Refat (Tech & AI)
- Channel username: `@nobilix`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/refat/output/refat_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 40
- Baseline domain + intent rollups: 28

## Impact Summary

- Candidate cells: 4
- Fills gap: 1
- Adds adjacent viewpoint: 1
- Deepens existing cell: 0
- Likely duplicate: 1
- Taxonomy extension: 0
- Needs probe: 1
- Noise risk: 0
- Exact overlaps: 1
- Related overlaps: 1
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 2

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `agent_ops/claude_code_workflows/design_agentic_dev_workflow` | adds_adjacent_viewpoint | 4.925 |  | `agent_ops/design_agentic_dev_workflow` | human_review_overlap_or_complement |
| `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | likely_duplicate | 4.462 | `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | `rag_retrieval_knowledge/design_rag_knowledge_base` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/llm_evals/build_ai_dev_eval` | needs_probe | 4.311 |  |  | run_deeper_candidate_probe |
| `ai_engineering_infra/deployment_observability/build_ai_dev_eval` | fills_gap | 4.311 |  |  | human_review_then_possible_accept |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| SilicBag | 2 | 1 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |
| Doronin | 2 | 1 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |
| Rinat | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Neuraldeep | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Polyakov | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| PashaZloy | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Ostrikov | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Air | 1 | 0 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |

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
