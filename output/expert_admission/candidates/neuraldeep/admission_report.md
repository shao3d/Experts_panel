# Candidate Admission Report: neuraldeep

## Verdict

accept

## Short Rationale

Neuraldeep remains accepted as an early seed expert in the Experts Panel
knowledge matrix.

This backfill records Neuraldeep's value under the current doctrine: the
passport shows strong technical coverage for local LLM infrastructure, inference
cost/latency, SGR-style agent architecture, deployment debugging, and practical
MCP limitations.

## Candidate Data

- Expert ID: `neuraldeep`
- Display name: Neuraldeep
- Normalized passport: `output/expert_admission/semantic_passports/neuraldeep/output/neuraldeep_semantic_passport.normalized.json`
- Decision mode: `current_roster_seed_backfilled_semantic_review`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `ai_engineering_infra/local_hardware/optimize_inference_cost_latency` | Primary seed value: local model hardware economics and inference optimization. |
| `agent_ops/architecture/design_agentic_dev_workflow` | Primary seed value: SGR/agent architecture and structured-output/tool-calling mechanics. |
| `ai_engineering_infra/deployment_observability/manage_security_privacy_governance` | Primary seed value: inference engine debugging and deployment observability. |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | Supporting value: practical MCP limitations and alternatives. |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | Supporting value: practical realities of AI-assisted coding workflows. |

## Representative Source Evidence

Representative source refs from the normalized passport:

- `P0070`, `P0236`, `P0455`: local hardware economics and inference optimization.
- `P0220`, `P0204`, `P0471`: SGR/agent architecture and structured tool use.
- `P0506`, `P0265`, `P0380`: deployment/inference debugging.
- `P0133`, `P0434`: MCP limitations and alternatives.
- `P0181`, `P0450`, `P0126`: practical AI-assisted development workflow realities.

## Query Probe Results

No runtime-equivalent query probe was run for this seed backfill.

This is acceptable because the current task is service-info normalization, not a
new admission decision. If broad production routing weight is added later, run
probes against PashaZloy and Rinat for local-LLM/agent-architecture overlap.

## Operational Cost and Risks

Accepted with these caveats:

- Strong fit for local LLM infrastructure, SGR/agent architecture, inference
  debugging, and technical deployment questions.
- Do not route as a beginner/no-code or broad business-adoption source.
- Open-source infrastructure posts age quickly; prefer recent evidence for tool
  versions, pricing, and deployment recommendations.

## Decision Notes

Backfilled on 2026-05-12 to align the early seed entry with the current
admission-control doctrine.

No retroactive arbitration report was created because the seed value is clear
from the normalized semantic passport and matrix cells.

## Next Action

Keep Neuraldeep accepted in the semantic knowledge matrix with the manifest
routing caveat.
