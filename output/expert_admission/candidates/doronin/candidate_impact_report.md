# Candidate Impact Report: Doronin

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `doronin`
- Display name: Doronin
- Channel username: `@kdoronin_blog`
- Passport cells: 4
- Passport: `output/expert_admission/semantic_passports/doronin/doronin_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 13
- Baseline experts: 13
- Baseline exact cells: 37
- Baseline domain + intent rollups: 22

## Impact Summary

- Candidate cells: 4
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 3
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 3
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | likely_duplicate | 4.925 | `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.792 | `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/mcp_tooling/build_human_ai_workflow` | fills_gap | 4.708 |  |  | human_review_then_possible_accept |
| `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | likely_duplicate | 4.292 | `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | `rag_retrieval_knowledge/design_rag_knowledge_base` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Tech_AI_grabli | 3 | 1 | 2 | `coding_agents/design_agentic_dev_workflow` |
| Akimov | 3 | 1 | 2 | `coding_agents/design_agentic_dev_workflow` |
| Ilia Izmailov | 3 | 1 | 2 | `coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 3 | 1 | 2 | `coding_agents/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 2 | 1 | 1 | `rag_retrieval_knowledge/design_rag_knowledge_base` |
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
