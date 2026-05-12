# Semantic Arbitration Report: elkornacio

## Verdict

`limited_scope`

Elkornacio is useful, but he is not a clean new-gap expert for the current
Experts Panel matrix. The right admission mode, if accepted, is limited-scope
depth for advanced AI coding tool/harness judgment and contrarian agent-workflow
practice.

This report is an arbitration recommendation only. It does not add Elkornacio
to the admission manifest.

## Short Rationale

The deterministic report is strongly cautious:

- candidate cells: 4
- clean gaps: 0
- adjacent viewpoint: 0
- deepens existing cell: 1
- likely duplicate: 2
- needs probe: 1
- exact overlaps: 3
- related overlaps: 0
- recommendation: `overlap_heavy_needs_stronger_review`

That caution is correct. Elkornacio is technically strong, but most of the
machine-comparable value lands in already accepted dense areas: coding-agent
tool choice, agentic development workflow, and MCP/tooling critique.

The strongest positive signal is not novelty. It is depth: his `Model vs
Harness vs UI` framing and native-harness argument are useful for advanced
tool-selection questions, and the deterministic evaluator classifies the Cursor
/ IDE-agent cell as `deepens_existing_cell`.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/elkornacio/output/elkornacio_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/elkornacio/candidate_impact_report.md`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`
- Corpus packet:
  `output/expert_admission/semantic_passports/elkornacio/input/run_manifest.json`

## Corpus And Run

- corpus used: 449 posts and 5576 comments
- comment cap: none
- date range: 2025-01-10 to 2026-05-01
- Vertex input tokens: 898163
- Vertex output tokens: 10550
- thoughts tokens: 2924
- finish reason: `STOP`
- normalized passport validation: passed
- normalized `matrix_export_incomplete`: false

Note: the raw generation omitted one matrix-worthy MCP cell from
`matrix_export` and missed five refs in `source_ref_index_used`. The normalizer
repaired both issues, and normalized validation passed.

## Candidate Signal

Positive signal:

- `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool`
  - deterministic class: `deepens_existing_cell`
  - aggregate score: 5.0
  - exact overlap with an accepted cell already covered by Ilia Izmailov and
    Glebkudr
  - accepted value, if any: much sharper tool architecture lens around
    `Model`, `Harness`, and `UI`, plus the argument for native harnesses

Overlap / duplicate signal:

- `agent_ops/agentic_dev_process/design_agentic_dev_workflow`
  - deterministic class: `likely_duplicate`
  - exact overlap with AI Architect
  - broader rollup already dense across Rinat, Neuraldeep, Polyakov, Refat,
    PashaZloy, Ostrikov, and others
- `agent_ops/mcp_tooling/design_agentic_dev_workflow`
  - deterministic class: `likely_duplicate`
  - exact overlap with PashaZloy and Neuraldeep
  - useful contrarian color, but not a new admission basis

Probe/supporting signal:

- `agent_ops/mcp_tooling/manage_security_privacy_governance`
  - deterministic class: `needs_probe`
  - no exact overlap, but only moderate/supporting strength and one evidence
    ref
  - should not be counted as a clean security/governance gap without a runtime
    probe or additional source review

## Unique Value

Elkornacio's strongest contribution is a very advanced practitioner lens on AI
coding tools:

- separates model, harness, and UI, which helps explain why the same model
  behaves differently in Cursor, Codex, Claude Code, OpenCode, JetBrains, or
  Conductor-like setups;
- argues for native harnesses as an important quality driver;
- emphasizes deterministic workflows over prompt-described "repeatable"
  workflows;
- provides a concrete hyper-customization pattern using Git branches,
  per-client `PATCH.md`, modified `AGENTS.md`, and agent-assisted merges;
- gives a pointed MCP security critique around authorization, RBAC/ABAC,
  read/write scoping, API keys in config, and alternatives such as restricted
  APIs or CLI tools.

Existing matrix comparison matters here:

- Coding-agent tool choice is already strong and multi-source.
- Agent-ops workflow is already one of the densest matrix areas.
- MCP/tooling is already represented by PashaZloy and Neuraldeep.
- Elkornacio still improves practical depth for a specific advanced audience,
  but does not materially expand the map.

## Routing Contract

Good fit:

- "Why does the same model behave differently in Cursor, Codex, and Claude
  Code?"
- "How should we compare model vs harness vs UI in coding agents?"
- "When should we prefer native harnesses?"
- "How can AI agents help maintain per-client product customizations?"
- "How do deterministic workflows differ from prompt-only repeatable
  workflows?"
- "What are the practical security problems with MCP implementations?"

Poor fit:

- beginner-friendly AI-assisted coding onboarding;
- enterprise-safe executive summaries without tone filtering;
- broad AI strategy or business adoption;
- primary source for new matrix coverage;
- neutral MCP advocacy or generic MCP tutorial;
- governance beyond agent-tooling security.

## Risks

- No clean matrix gaps.
- Strong overlap with existing accepted experts.
- Heavy informal/profane style may require filtering in production-facing
  outputs.
- Some model/tool comparisons age quickly.
- MCP security cell is promising but evidence-thin and should be probed before
  receiving production routing weight.

## Decision

Recommended final status:

`limited_scope`

Accept only if the system wants additional advanced depth in AI coding tool
architecture and contrarian workflow/security critique. Do not count Elkornacio
as a new map-expanding expert.

If accepted, the manifest should include:

`limited-scope depth for advanced AI coding tool/harness judgment and
contrarian agent workflow critique; no clean matrix gaps, avoid broad duplicate
routing`

## Follow-Up Probe

Probe is useful before admission if the process wants to be strict about
overlap-heavy candidates:

- 2 model/harness/UI comparison queries against Ilia, Glebkudr, AI_Grabli, and
  Polyakov;
- 1 hyper-customization / per-client branch workflow query;
- 1 MCP security query against PashaZloy, Neuraldeep, and Rinat;
- 1 beginner/general coding-agent query where Elkornacio should not be the
  primary source.
