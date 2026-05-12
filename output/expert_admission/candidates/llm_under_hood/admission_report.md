# Candidate Admission Report: llm_under_hood

## Verdict

accept

## Short Rationale

Rinat is accepted as a high-value SGR, AI reliability/evals, and engineering
harness expert for the Experts Panel knowledge matrix.

The acceptance is based on a valid normalized semantic passport, deterministic
matrix preflight, qualitative arbitration, source spot checks, and manual human
approval. He is not accepted as a generic LangChain/MCP tutorial source. His
strongest incremental value is production reliability: Schema-Guided Reasoning,
eval-first development, ground truth, error heatmaps, feedback loops, and
engineering harnesses for AI coding agents.

## Candidate Data

- Expert ID: `llm_under_hood`
- Display name: Rinat
- Channel username: `@llm_under_hood`
- Full DB corpus before cap: 321 posts and 12,190 comments
- Corpus used for passport: 321 posts and 5,410 comments
- Comment cap: 20 comments per post
- Rejected cap trial: 25 comments per post, 1,054,653 input tokens
- Passport prompt tokens: 915,914
- Passport output tokens: 10,954
- Passport thoughts tokens: 3,146
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/llm_under_hood/output/llm_under_hood_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/llm_under_hood/candidate_impact_report.md`
- Arbitration report: `output/expert_admission/candidates/llm_under_hood/arbitration_report.md`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `agent_ops/reasoning_control/design_agentic_dev_workflow` | Accepted as a distinct SGR / reasoning-control contribution inside an already dense agent-ops workflow rollup. |
| `evals_quality/llm_evals/build_ai_dev_eval` | Accepted as a clean evals/reliability gap: ground truth, heatmaps, feedback loops, and quality trajectory engineering. |
| `agent_ops/agentic_dev_process/learn_ai_assisted_development` | Accepted as a clean engineering-harness gap for AI coding agents: AGENTS.md, docs, tests, and feedback loops. |

Candidate preflight summary:

- Candidate cells in `matrix_export`: 3
- Fills gap: 2
- Adds adjacent viewpoint: 1
- Needs probe: 0
- Likely duplicate: 0
- Taxonomy extensions after taxonomy update: 0
- Exact overlaps: 0
- Related overlaps: 1
- Preliminary recommendation: `promising_needs_human_review`

## Closest Existing Experts

Closest overlap is only at the broad `agent_ops/design_agentic_dev_workflow`
rollup level:

- Neuraldeep, Polyakov, Refat, PashaZloy, and Ostrikov already cover nearby
  agent-ops workflow topics.
- Rinat adds a distinct `reasoning_control` / SGR lens rather than another MCP,
  tool-calling, multi-agent, or Claude Code workflow cell.

Accepted differentiation:

- Neuraldeep and Polyakov remain stronger for tool-calling/hooks/skills and
  lower-level agent architecture.
- PashaZloy remains stronger for local/open-source agent tooling and
  OpenAPI/MCP wrappers.
- Ostrikov and Glebkudr remain stronger for multi-agent orchestration and
  context-engineering workflow.
- Rinat is stronger for reliability framing: SGR, evals, ground truth, error
  heatmaps, and feedback loops.

## Representative Source Areas

Representative source refs from the normalized passport and spot checks:

- `P0130`: formalization of Schema-Guided Reasoning as typed, schema-driven
  reasoning with constrained decoding and visible intermediate steps.
- `P0149`: SGR vs Tool Calling comparison and production monitoring/debugging
  trade-offs.
- `P0076`, `P0123`: eval-first AI development, reliability engineering, and
  quality as a trajectory.
- `P0097`, `P0232`: moving from vibe coding to engineering harnesses with
  AGENTS.md, tests, feedback loops, and measurable quality deltas.

## Query Probe Results

No runtime-equivalent query probe was run for this acceptance.

This is acceptable in the current manual mode because the candidate passport,
matrix preflight, source spot checks, and arbitration report show strong
non-duplicate value. If Rinat later receives broad production routing weight,
run probes focused on:

- SGR vs Tool Calling / MCP architecture;
- evals, ground truth, heatmaps, and feedback loops;
- AI coding engineering harnesses against Akimov, AI_Grabli, and Ostrikov;
- RAG bottleneck/eval queries where Rinat should be supporting unless the
  question is explicitly about evaluation or quality bottlenecks.

## Source Depth Review

The passport shows strong source depth for production-grade AI engineering:

- `agent_ops/reasoning_control/design_agentic_dev_workflow`: strong,
  deep-practitioner, primary role, adjacent/new viewpoint in a dense area.
- `evals_quality/llm_evals/build_ai_dev_eval`: strong, deep-practitioner,
  primary role, clean gap.
- `agent_ops/agentic_dev_process/learn_ai_assisted_development`: strong,
  deep-practitioner, primary role, clean gap.

## Operational Cost and Risks

Accepted with these caveats:

- Do not route Rinat as a generic beginner-friendly LangChain/LangGraph source.
- Do not route him as neutral MCP advocacy or standard MCP setup guide.
- Treat SGR as a strong pattern to compare against Tool Calling and hybrid
  designs, not as universally superior in every context.
- The passport used a 20-comments-per-post cap; it preserved a large comment
  sample but not the full 12,190-comment corpus.
- Some local-model and framework details may age quickly.

## Decision Notes

Human decision recorded on 2026-05-10 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- qualitative arbitration report;
- accepted 11-passport knowledge matrix before admission.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with Rinat as accepted in the semantic knowledge matrix. Keep the
routing caveat: he is primarily an SGR, AI reliability/evals, and
engineering-harness depth expert, not a generic framework tutorial source.
