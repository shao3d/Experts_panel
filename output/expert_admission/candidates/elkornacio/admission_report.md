# Candidate Admission Report: elkornacio

## Verdict

accept

## Short Rationale

Elkornacio is accepted as an advanced AI coding tool/harness depth expert for
the Experts Panel knowledge matrix.

The acceptance is based on a valid normalized semantic passport, deterministic
matrix preflight, qualitative arbitration, source spot checks, and manual human
approval. This is an explicit human decision to accept him despite an
overlap-heavy machine signal. He is not accepted as a clean new-gap expert. His
strongest value is deep practical judgment around coding-agent tools, model vs
harness vs UI, native harness quality, deterministic workflows, and
hyper-customization via Git branches.

## Candidate Data

- Expert ID: `elkornacio`
- Display name: Elkornacio
- Channel username: `@elkornacio`
- Corpus used for passport: 449 posts and 5,576 comments
- Comment cap: none
- Passport prompt tokens: 898,163
- Passport output tokens: 10,550
- Passport thoughts tokens: 2,924
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/elkornacio/output/elkornacio_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/elkornacio/candidate_impact_report.md`
- Arbitration report: `output/expert_admission/candidates/elkornacio/arbitration_report.md`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | Accepted as the primary value: strong depth for advanced coding-agent tool choice, especially model/harness/UI separation and native-harness judgment. |
| `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | Accepted as overlap/supporting depth only; exact overlap with AI Architect and dense related coverage across agent_ops. |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | Accepted as overlap/supporting contrarian MCP/tooling critique; exact overlap with PashaZloy and Neuraldeep. |
| `agent_ops/mcp_tooling/manage_security_privacy_governance` | Accepted as probe-needed supporting signal around MCP security; do not raise production routing weight without targeted probe. |

Candidate preflight summary:

- Candidate cells in `matrix_export`: 4
- Fills gap: 0
- Adds adjacent viewpoint: 0
- Deepens existing cell: 1
- Needs probe: 1
- Likely duplicate: 2
- Taxonomy extensions after taxonomy update: 0
- Exact overlaps: 3
- Related overlaps: 0
- Preliminary recommendation: `overlap_heavy_needs_stronger_review`

## Closest Existing Experts

Closest overlap is broad and expected:

- Polyakov, AI_Grabli, Ilia Izmailov, AI Architect, and Glebkudr already cover
  coding-agent tool choice.
- AI Architect already covers the exact
  `agent_ops/agentic_dev_process/design_agentic_dev_workflow` cell.
- PashaZloy and Neuraldeep already cover
  `agent_ops/mcp_tooling/design_agentic_dev_workflow`.
- Rinat, Neuraldeep, Polyakov, Refat, PashaZloy, Ostrikov, Glebkudr, and others
  make `agent_ops/design_agentic_dev_workflow` a dense rollup.

Accepted differentiation:

- Elkornacio is sharper on model/harness/UI separation and native harness
  selection than the existing accepted sources.
- He contributes advanced practitioner detail on deterministic workflows and
  per-client Git-branch customization.
- His MCP security critique is useful, but evidence-thin and should remain
  supporting until probed.

## Representative Source Areas

Representative source refs from the normalized passport and spot checks:

- `P0427`: model vs harness vs UI framing and native harness argument.
- `P0382`: guaranteed workflows vs prompt-described repeatable workflows.
- `P0439`, `P0440`: per-client hyper-customization via Git branches, `PATCH.md`,
  `AGENTS.md`, and agent-assisted merges.
- `P0388.C0032`: MCP security critique around authorization, RBAC/ABAC,
  read/write scoping, API keys in config, and restricted API / CLI alternatives.

## Query Probe Results

No runtime-equivalent query probe was run for this acceptance.

This is acceptable in the current manual mode because the human decision is to
accept him as an overlap-heavy depth source. If Elkornacio later receives broad
production routing weight, run probes focused on:

- model/harness/UI comparison against Ilia, Glebkudr, AI_Grabli, and Polyakov;
- hyper-customization / per-client branch workflow;
- MCP security against PashaZloy, Neuraldeep, and Rinat;
- beginner/general coding-agent queries where Elkornacio should not be primary.

## Source Depth Review

The passport shows strong source depth for advanced AI-assisted development:

- `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool`: strong,
  deep-practitioner, primary role, exact overlap but score-lifting depth.
- `agent_ops/agentic_dev_process/design_agentic_dev_workflow`: strong,
  deep-practitioner, primary role, duplicate/supporting.
- `agent_ops/mcp_tooling/design_agentic_dev_workflow`: strong but repaired from
  `matrix_cells`; duplicate/supporting.
- `agent_ops/mcp_tooling/manage_security_privacy_governance`: moderate,
  supporting role, probe-needed.

## Operational Cost and Risks

Accepted with these caveats:

- Do not count Elkornacio as a clean map-expanding expert.
- Do not route him broadly for beginner-friendly AI-assisted development.
- Do not route him as neutral MCP advocacy or generic MCP tutorial source.
- Heavy informal/profane style may require filtering in production-facing
  outputs.
- Model/tool comparisons age quickly; recent source weighting matters.
- MCP security signal needs targeted probe before production routing weight is
  raised.

## Decision Notes

Human decision recorded on 2026-05-10 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- qualitative arbitration report;
- accepted 12-passport knowledge matrix before admission.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with Elkornacio as accepted in the semantic knowledge matrix. Keep the
routing caveat: he is primarily an advanced coding tool/harness depth expert,
not a broad duplicate source and not a clean new-gap expert.
