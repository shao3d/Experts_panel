# Candidate Impact Report: PashaZloy

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `pashazloy`
- Display name: PashaZloy
- Channel username: `@evilfreelancer`
- Passport cells: 3
- Passport: `output/expert_admission/semantic_passports/pashazloy/output/pashazloy_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 8
- Baseline experts: 8
- Baseline exact cells: 29
- Baseline domain + intent rollups: 16

## Impact Summary

- Candidate cells: 3
- Fills gap: 0
- Adds adjacent viewpoint: 1
- Deepens existing cell: 1
- Likely duplicate: 1
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 2
- Related overlaps: 1
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 0
- Dense overlap cells: 2

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `ai_engineering_infra/local_agent_setup/optimize_inference_cost_latency` | adds_adjacent_viewpoint | 4.811 |  | `ai_engineering_infra/optimize_inference_cost_latency` | human_review_overlap_or_complement |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | deepens_existing_cell | 4.857 | `agent_ops/mcp_tooling/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | human_review_then_possible_accept |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | likely_duplicate | 4.387 | `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | `prompt_engineering/learn_ai_assisted_development` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Neuraldeep | 5 | 2 | 3 | `agent_ops/design_agentic_dev_workflow`<br>`ai_engineering_infra/optimize_inference_cost_latency`<br>`prompt_engineering/learn_ai_assisted_development` |
| Polyakov | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Air | 1 | 0 | 1 | `prompt_engineering/learn_ai_assisted_development` |
| Refat (Tech & AI) | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Ostrikov | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| AI Architect | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |

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
