# Candidate Impact Report: Sergei Notevskii

## Preliminary Recommendation

- Recommendation: `overlap_heavy_needs_stronger_review`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `sergei_notevskii`
- Display name: Sergei Notevskii
- Channel username: `@sergeinotevskii`
- Passport cells: 4
- Passport: `output/expert_admission/semantic_passports/sergei_notevskii/output_with_comments/sergei_notevskii_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 18
- Baseline experts: 18
- Baseline exact cells: 47
- Baseline domain + intent rollups: 30

## Impact Summary

- Candidate cells: 4
- Fills gap: 0
- Adds adjacent viewpoint: 1
- Deepens existing cell: 0
- Likely duplicate: 3
- Taxonomy extension: 0
- Needs probe: 0
- Noise risk: 0
- Exact overlaps: 3
- Related overlaps: 1
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 0
- Dense overlap cells: 4

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | likely_duplicate | 5.0 | `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | `ai_engineering_infra/optimize_inference_cost_latency` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | likely_duplicate | 4.623 | `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | `ai_engineering_infra/optimize_inference_cost_latency` | check_representative_posts_before_counting_as_unique |
| `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | likely_duplicate | 4.245 | `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/context_compression/optimize_inference_cost_latency` | adds_adjacent_viewpoint | 4.189 |  | `ai_engineering_infra/optimize_inference_cost_latency` | human_review_overlap_or_complement |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Neuraldeep | 7 | 3 | 4 | `agent_ops/design_agentic_dev_workflow`<br>`ai_engineering_infra/optimize_inference_cost_latency` |
| PashaZloy | 3 | 0 | 3 | `ai_engineering_infra/optimize_inference_cost_latency` |
| Polyakov | 2 | 1 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Rinat | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Aimasters.Me | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 1 | 0 | 1 | `agent_ops/design_agentic_dev_workflow` |

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
