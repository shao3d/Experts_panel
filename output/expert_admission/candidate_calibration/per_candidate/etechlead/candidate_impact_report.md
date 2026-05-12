# Candidate Impact Report: Etechlead

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `etechlead`
- Display name: Etechlead
- Channel username: `@etechlead`
- Passport cells: 6
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/etechlead/output/etechlead_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 41
- Baseline domain + intent rollups: 25

## Impact Summary

- Candidate cells: 6
- Fills gap: 2
- Adds adjacent viewpoint: 0
- Deepens existing cell: 2
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 4
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 2
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 5.0 | `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | deepens_existing_cell | 5.0 | `coding_agents/claude_code_workflows/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` | human_review_then_possible_accept |
| `model_landscape/model_comparison/compare_models_for_task` | deepens_existing_cell | 5.0 | `model_landscape/model_comparison/compare_models_for_task` | `model_landscape/compare_models_for_task` | human_review_then_possible_accept |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.623 | `agent_ops/mcp_tooling/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/context_compression/improve_retrieval_quality` | fills_gap | 5.0 |  |  | human_review_then_possible_accept |
| `ai_engineering_infra/agentic_dev_process/build_human_ai_workflow` | fills_gap | 4.585 |  |  | human_review_then_possible_accept |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Elkornacio | 4 | 2 | 2 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Kornishev | 4 | 1 | 3 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow`<br>`model_landscape/compare_models_for_task` |
| Polyakov | 3 | 0 | 3 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Tech_AI_grabli | 3 | 1 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Ilia Izmailov | 3 | 1 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Neuraldeep | 2 | 1 | 1 | `agent_ops/design_agentic_dev_workflow` |
| PashaZloy | 2 | 1 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Rinat | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Doronin | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Akimov | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| AI Architect | 1 | 1 | 0 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Glebkudr | 1 | 1 | 0 | `coding_agents/choose_ai_coding_tool` |

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
