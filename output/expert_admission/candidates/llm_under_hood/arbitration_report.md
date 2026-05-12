# Semantic Arbitration Report: llm_under_hood

## Verdict

`accept`

Rinat looks strongly admission-worthy. He adds high-value coverage for
Schema-Guided Reasoning, AI reliability engineering, eval loops, and engineering
harnesses for AI-assisted development.

This report is an arbitration recommendation only. It does not add Rinat to the
admission manifest.

## Short Rationale

The deterministic report is positive:

- candidate cells: 3
- clean gaps: 2
- adjacent viewpoint: 1
- deepens existing cell: 0
- likely duplicate: 0
- needs probe: 0
- exact overlaps: 0
- related overlaps: 1
- recommendation: `promising_needs_human_review`

This is a strong signal. The only overlap is not an exact duplicate: SGR lands
inside the already dense `agent_ops/design_agentic_dev_workflow` rollup, but it
adds a genuinely distinct reasoning-control subdomain. The other two exported
cells are clean gaps.

Source spot checks support the passport's strongest claims: SGR as typed,
schema-driven reasoning; eval-first reliability engineering; engineering
harnesses for coding agents; and feedback loops with measurable quality
improvement.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/llm_under_hood/output/llm_under_hood_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/llm_under_hood/candidate_impact_report.md`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`
- Corpus packet:
  `output/expert_admission/semantic_passports/llm_under_hood/input/run_manifest.json`

## Corpus And Run

- corpus used: 321 posts and 5410 comments
- comment cap: 20 comments per post
- full DB corpus before cap: 321 posts and 12190 comments
- first cap trial: 25 comments per post, `1054653` input tokens, above the
  target working range
- selected cap: 20 comments per post, `915914` input tokens
- Vertex output tokens: 10954
- thoughts tokens: 3146
- finish reason: `STOP`
- normalized passport validation: passed
- normalized `matrix_export_incomplete`: false

Note: the first generation attempt at cap 20 hit `429 RESOURCE_EXHAUSTED`.
After a pause, retry succeeded with the same packet.

## Candidate Signal

Accepted-like signal:

- `evals_quality/llm_evals/build_ai_dev_eval`
  - deterministic class: `fills_gap`
  - aggregate score: 4.849
  - clean gap for continuous evals, ground truth, heatmaps, feedback loops, and
    AI reliability engineering
- `agent_ops/agentic_dev_process/learn_ai_assisted_development`
  - deterministic class: `fills_gap`
  - aggregate score: 4.849
  - clean gap for engineering harnesses around AI coding agents: AGENTS.md,
    strict docs, test loops, and maintainability guardrails
- `agent_ops/reasoning_control/design_agentic_dev_workflow`
  - deterministic class: `adds_adjacent_viewpoint`
  - aggregate score: 5.0
  - no exact overlap; related overlap only because the broader
    `agent_ops/design_agentic_dev_workflow` area is already dense
  - strongest distinctive contribution: Schema-Guided Reasoning as a typed,
    testable, transparent reasoning-control pattern

Non-exported supporting signal:

- `rag_retrieval_knowledge/rag_architecture/improve_retrieval_quality`
  - normal-weight matrix cell around RAG retrieval bottlenecks
  - useful supporting signal, but not a primary admission basis

## Unique Value

Rinat's strongest contribution is reliability engineering for LLM systems:

- formalizes Schema-Guided Reasoning as a practical production pattern, not
  just structured-output formatting;
- frames AI development as reliability engineering: start with evals, build
  ground truth, measure quality trajectories, and make pipeline failures
  visible;
- gives concrete feedback-loop patterns: error heatmaps, test harnesses,
  measurable quality deltas, and iterative agent improvement;
- bridges production LLM systems and AI-assisted coding through the same
  principle: agents need harnesses, docs, tests, and observable feedback;
- adds an anti-hype counterweight to autonomous-agent enthusiasm, especially
  around tool calling, MCP, and black-box frameworks.

Existing matrix comparison matters here:

- Agent-ops workflow is already dense, but not specifically around
  `reasoning_control` / SGR.
- Accepted roster has some eval coverage, but not a strong primary
  `evals_quality/llm_evals/build_ai_dev_eval` cell.
- Accepted roster has coding-agent workflow coverage, but Rinat adds the
  reliability-harness learning angle rather than another tool-choice angle.

## Routing Contract

Good fit:

- "How should we design reliable agentic workflows?"
- "When should we use SGR vs Tool Calling?"
- "How do we make LLM reasoning observable and testable?"
- "How do we build evals, ground truth, heatmaps, and feedback loops?"
- "How do we move from vibe coding to an engineering harness?"
- "How should coding agents work on large or legacy codebases?"
- "Why is AI product quality a trajectory rather than a one-time score?"

Poor fit:

- beginner-friendly LangChain/LangGraph tutorial;
- neutral MCP advocacy or standard MCP setup guide;
- broad model-release news;
- creative writing or multimodal content generation;
- teams explicitly looking for off-the-shelf framework adoption rather than
  custom reliability-oriented architecture.

## Risks

- Strong framework skepticism may underweight standard ecosystem paths like
  LangChain, LangGraph, or MCP when a team specifically wants those tutorials.
- SGR framing is distinctive and valuable, but should be compared against tool
  calling and hybrid patterns rather than treated as universally superior.
- Cap 20 preserved a large comment sample but not the full 12190-comment corpus.
- Some local-model and framework details may age quickly.

## Decision

Recommended final status:

`accept`

Accept as a strong reliability/evals/SGR and engineering-harness expert. If
accepted, the manifest should include:

`accepted as SGR, AI reliability/evals, and engineering-harness depth expert;
strong framework skepticism, avoid routing as generic LangChain/MCP tutorial
source`

## Follow-Up Probe

Runtime probes are useful before broad production routing:

- 2 SGR vs Tool Calling / MCP architecture queries;
- 2 evals / ground-truth / feedback-loop queries;
- 1 coding-agent engineering-harness query against Akimov, AI_Grabli, and
  Ostrikov;
- 1 RAG retrieval-quality query where Rinat should be supporting, not primary
  unless the question is eval/bottleneck focused.
