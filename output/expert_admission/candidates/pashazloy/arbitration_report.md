# Semantic Arbitration Report: pashazloy

## Verdict

`accept`

PashaZloy looks admission-worthy, but only as a deep technical complement to
the existing infrastructure and agent-tooling cluster. He should not be treated
as a clean new-gap expert.

This report was written before final admission. PashaZloy has since been
accepted in the admission manifest with a strong routing caveat.

## Short Rationale

The deterministic report is deliberately cautious:

- candidate cells: 3
- clean gaps: 0
- adjacent viewpoint: 1
- deepens existing cell: 1
- likely duplicate: 1
- exact overlaps: 2
- related overlaps: 1
- recommendation: `overlap_heavy_needs_stronger_review`

That is the right mechanical signal. All candidate cells touch already accepted
coverage, especially Neuraldeep. However, the passport shows unusually strong
hands-on value: local LLM deployment, hardware optimization, vLLM/llama.cpp
setups, MCP/ACP/SGR tooling, OpenAPI-to-MCP/CLI conversion, and test-driven
vibe-coding practice.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/pashazloy/output/pashazloy_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/pashazloy/candidate_impact_report.md`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`

## Corpus And Run

- corpus used: 400 posts and 5992 comments
- comment cap: 38 comments per post
- Vertex input tokens: 950102
- Vertex output tokens: 11055
- finish reason: `STOP`
- normalized passport validation: passed
- `matrix_export_incomplete`: false

## Candidate Signal

Accepted-like signal:

- `ai_engineering_infra/local_agent_setup/optimize_inference_cost_latency`
  - adjacent viewpoint against existing inference-cost/local-hardware coverage
  - strong practical value for local/on-prem LLM setup
- `agent_ops/mcp_tooling/design_agentic_dev_workflow`
  - exact overlap with Neuraldeep, but candidate score is stronger
  - good depth for MCP/ACP/tooling internals and OpenAPI wrappers

Overlap / duplicate signal:

- `prompt_engineering/agentic_dev_process/learn_ai_assisted_development`
  - exact overlap with Neuraldeep's vibe-coding realities cell
  - useful but not a separate admission basis

## Unique Value

PashaZloy's strongest contribution is the open-source infra-builder angle:

- exact hardware and Docker/vLLM/llama.cpp setups for local models;
- concrete local inference cost/latency and VRAM trade-offs;
- OpenAPI-to-MCP and OpenAPI-to-CLI as context-compression tooling for agents;
- MCP/ACP/tool-calling internals, including vLLM parser issues;
- SGR and strict orchestration for reliable agents;
- BDD/TDD framing for vibe-coding, where tests act as project long-term
  memory.

This overlaps heavily with Neuraldeep, but the emphasis differs:

- Neuraldeep is broader as Head-of-AI / local LLM infra / SGR / enterprise
  deployment source.
- PashaZloy is more open-source-builder and implementation-artifact oriented:
  tools, scripts, CLI wrappers, hardware logs, and reproducible local setups.

## Routing Contract

Good fit:

- "How do I run local LLMs on consumer GPUs?"
- "How should we expose a huge OpenAPI surface to an agent without blowing the
  context window?"
- "When should I use MCP, ACP, CLI tools, or direct REST wrappers?"
- "How do I structure local agent tooling around vLLM/llama.cpp?"
- "How should tests/BDD protect vibe-coding from regressions?"

Poor fit:

- business adoption or ROI strategy;
- non-technical AI onboarding;
- governance/compliance;
- broad AI news;
- primary routing when Neuraldeep is already the stronger general infra source.

## Risks

- Heavy overlap with Neuraldeep.
- Strong open-source/local-first bias may underweight managed/cloud/vendor
  solutions.
- Highly technical source; poor fit for beginner or executive audiences.
- Some claims are fast-moving and may age quickly with tooling changes.

## Decision

Recommended final status:

`accept`

Accept only if the system wants more depth in local LLM infrastructure,
open-source agent tooling, MCP/ACP wrappers, and hardware/practical deployment.
Do not count him as a new-gap expert. If accepted, the manifest should include:

`accepted as local-LLM and open-source agent-tooling depth expert; heavy overlap
with Neuraldeep, avoid broad duplicate routing`

## Follow-Up Probe

Runtime probes are useful before broad production routing:

- 2 local LLM deployment / hardware queries;
- 2 MCP/OpenAPI-to-tooling queries;
- 1 overlap query against Neuraldeep;
- 1 vibe-coding/TDD query where he should be supporting, not the only source.
