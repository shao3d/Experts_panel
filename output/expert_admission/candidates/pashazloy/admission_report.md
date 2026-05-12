# Candidate Admission Report: pashazloy

## Verdict

accept

## Short Rationale

PashaZloy is accepted as a strong technical depth expert for the Experts Panel
knowledge matrix.

The acceptance is based on a valid semantic passport, deterministic candidate
preflight, and qualitative arbitration. He is not accepted as a clean new-gap
expert. He is accepted because he adds practical, implementation-heavy depth in
local LLM infrastructure, open-source agent tooling, MCP/ACP/OpenAPI wrappers,
hardware setup, and BDD/TDD workflows for reliable vibe-coding.

## Candidate Data

- Expert ID: `pashazloy`
- Display name: PashaZloy
- Channel username: `@evilfreelancer`
- Corpus used for passport: 400 posts and 5,992 comments
- Comment cap: 38 comments per post
- Passport prompt tokens: 950,102
- Passport output tokens: 11,055
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/pashazloy/output/pashazloy_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/pashazloy/candidate_impact_report.md`
- Arbitration report: `output/expert_admission/candidates/pashazloy/arbitration_report.md`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `ai_engineering_infra/local_agent_setup/optimize_inference_cost_latency` | Accepted as adjacent depth for local/on-prem LLM setup, hardware, Docker/vLLM/llama.cpp, and cost/latency trade-offs. |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | Accepted as depth over Neuraldeep's existing MCP/tooling coverage, with stronger implementation-artifact signal. |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | Accepted as overlap/supporting only; not a separate admission basis. |

Candidate preflight summary before admission:

- Candidate cells: 3
- Fills gap: 0
- Adds adjacent viewpoint: 1
- Deepens existing cell: 1
- Likely duplicate: 1
- Needs probe: 0
- Taxonomy extensions: 0
- Exact overlaps: 2
- Related overlaps: 1
- Preliminary recommendation: `overlap_heavy_needs_stronger_review`

## Closest Existing Experts

Closest overlap:

- Neuraldeep: exact overlap on `agent_ops/mcp_tooling/design_agentic_dev_workflow`
  and `prompt_engineering/agentic_dev_process/learn_ai_assisted_development`,
  plus related overlap around `ai_engineering_infra/optimize_inference_cost_latency`.

Accepted differentiation:

- Neuraldeep remains the broader Head-of-AI / local infra / SGR / enterprise
  deployment source.
- PashaZloy is more open-source-builder and implementation-artifact oriented:
  reproducible local setups, Docker configs, CLI wrappers, OpenAPI-to-MCP/CLI,
  hardware logs, and hands-on tooling internals.

## Representative Source Areas

Representative source refs from the normalized passport:

- `P0231`, `P0240`, `P0270`, `P0338`: local LLM setup, hardware, vLLM/llama.cpp,
  and inference trade-offs.
- `P0296`, `P0314`, `P0334`, `P0347`, `P0376`: MCP/ACP/tooling internals,
  OpenAPI wrappers, and agent orchestration.
- `P0114`, `P0285`, `P0325`: BDD/TDD and vibe-coding reliability patterns.

## Query Probe Results

No runtime-equivalent query probe was run before admission.

This is acceptable in the current manual mode because the passport and
arbitration report show clear implementation depth. If PashaZloy becomes a
central source in production routing, run probes focused on:

- local LLM deployment and hardware queries;
- MCP/OpenAPI-to-tooling queries;
- overlap against Neuraldeep;
- vibe-coding/TDD queries where he should be supporting or paired with
  Neuraldeep/Polyakov/Ostrikov depending on the question.

## Operational Cost and Risks

Accepted with these caveats:

- Do not route PashaZloy as a broad new gap in infrastructure or agent tooling.
- Do not route him as a business adoption, ROI, governance, or beginner source.
- Avoid broad duplicate routing against Neuraldeep; prefer PashaZloy when the
  query needs implementation artifacts, local setup specifics, OpenAPI wrappers,
  or open-source tooling details.
- Strong local/open-source bias may underweight managed/cloud/vendor options.
- Fast-moving tooling claims may age quickly.

## Decision Notes

Human decision recorded on 2026-05-10 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- qualitative arbitration report;
- accepted 8-passport knowledge matrix before admission.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with PashaZloy as accepted in the semantic knowledge matrix. Keep the
routing caveat: local-LLM and open-source agent-tooling depth expert, heavy
overlap with Neuraldeep, avoid broad duplicate routing.
