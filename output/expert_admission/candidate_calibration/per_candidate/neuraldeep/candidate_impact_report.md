# Candidate Impact Report: Neuraldeep

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `neuraldeep`
- Display name: Neuraldeep
- Channel username: `@neuraldeep`
- Passport cells: 5
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/neuraldeep/output/neuraldeep_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 41
- Baseline domain + intent rollups: 28

## Impact Summary

- Candidate cells: 5
- Fills gap: 1
- Adds adjacent viewpoint: 1
- Deepens existing cell: 1
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 3
- Related overlaps: 1
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 1
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | adds_adjacent_viewpoint | 5.0 |  | `ai_engineering_infra/optimize_inference_cost_latency` | human_review_overlap_or_complement |
| `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | likely_duplicate | 5.0 | `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/deployment_observability/manage_security_privacy_governance` | fills_gap | 5.0 |  |  | human_review_then_possible_accept |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.434 | `agent_ops/mcp_tooling/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | deepens_existing_cell | 4.66 | `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | `prompt_engineering/learn_ai_assisted_development` | human_review_then_possible_accept |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| PashaZloy | 6 | 2 | 4 | `agent_ops/design_agentic_dev_workflow`<br>`ai_engineering_infra/optimize_inference_cost_latency`<br>`prompt_engineering/learn_ai_assisted_development` |
| Polyakov | 3 | 1 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Rinat | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Ostrikov | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Air | 1 | 0 | 1 | `prompt_engineering/learn_ai_assisted_development` |
| Etechlead | 1 | 1 | 0 | `agent_ops/design_agentic_dev_workflow` |
| SilicBag | 1 | 0 | 1 | `prompt_engineering/learn_ai_assisted_development` |
| Elkornacio | 1 | 1 | 0 | `agent_ops/design_agentic_dev_workflow` |

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
