# Candidate Impact Report: Glebkudr

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `glebkudr`
- Display name: Glebkudr
- Channel username: `@gleb_pro_ai`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/glebkudr/output/glebkudr_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 41
- Baseline domain + intent rollups: 27

## Impact Summary

- Candidate cells: 4
- Fills gap: 2
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 2
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 2
- Dense overlap cells: 2

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/context_compression/optimize_inference_cost_latency` | fills_gap | 5.0 |  |  | human_review_then_possible_accept |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 4.0 | `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/model_comparison/compare_models_for_task` | fills_gap | 4.189 |  |  | human_review_then_possible_accept |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Polyakov | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool` |
| Elkornacio | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool` |
| Etechlead | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool` |
| Rinat | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Neuraldeep | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| PashaZloy | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Ostrikov | 1 | 1 | 0 | `agent_ops/design_agentic_dev_workflow` |
| Tech_AI_grabli | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |
| Ilia Izmailov | 1 | 1 | 0 | `coding_agents/choose_ai_coding_tool` |
| Kornishev | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |

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
