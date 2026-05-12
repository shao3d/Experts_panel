# Candidate Impact Report: Tech_AI_grabli

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `ai_grabli`
- Display name: Tech_AI_grabli
- Channel username: `@oestick`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/ai_grabli/output/ai_grabli_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 41
- Baseline domain + intent rollups: 27

## Impact Summary

- Candidate cells: 4
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 1
- Noise risk: 0
- Exact overlaps: 2
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 2

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.811 | `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality` | fills_gap | 4.792 |  |  | human_review_then_possible_accept |
| `prompt_engineering/reasoning_control/build_ai_dev_eval` | needs_probe | 4.387 |  |  | run_deeper_candidate_probe |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | likely_duplicate | 4.519 | `coding_agents/claude_code_workflows/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Etechlead | 3 | 1 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Doronin | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Akimov | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Ilia Izmailov | 2 | 0 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Kornishev | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Elkornacio | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |
| Polyakov | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |
| AI Architect | 1 | 1 | 0 | `coding_agents/choose_ai_coding_tool` |

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
