# Semantic Arbitration Report: doronin

## Verdict

`accept_with_routing_caveat`

Doronin looks admission-worthy for the Experts Panel matrix, but not as a broad
new-gap expert. His useful role is a strong practitioner voice for disciplined
AI-assisted development, Claude Code / Cursor workflow judgment, custom/narrow
MCP practice, and temporal-graph agent memory.

This report is an arbitration recommendation only. It does not add Doronin to
the admission manifest.

## Short Rationale

The deterministic report is cautious:

- candidate cells: 4
- clean gaps: 1
- adjacent viewpoint: 0
- deepens existing cell: 0
- likely duplicate: 3
- needs probe: 0
- exact overlaps: 3
- related overlaps: 0
- recommendation: `overlap_heavy_needs_stronger_review`

The caution is correct at the taxonomy level: most exported cells touch already
accepted coverage in coding agents and RAG / knowledge-base design.

However, the qualitative source review shows that Doronin is not just repeating
generic Cursor / Claude Code / MCP content. His strongest value is a coherent,
grounded operating doctrine: anti-vibe coding, BDD / rules / documentation as
agent constraints, custom narrow MCP servers, Claude Code migration experience,
and temporal-graph memory patterns.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/doronin/doronin_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/doronin/candidate_impact_report.md`
- Overlap report:
  `output/expert_admission/candidates/doronin/overlap_report.json`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`
- Corpus packet:
  `output/expert_admission/semantic_passports/doronin/input/run_manifest.json`

## Corpus And Run

- corpus used: 687 posts and 4026 comments
- comment cap: 10 per post
- date range: 2024-06-11 to 2026-05-04
- Vertex input tokens: 908955
- Vertex output tokens: 13951
- thoughts tokens: 5219
- finish reason: `STOP`
- normalized passport validation: passed
- normalized `matrix_export_incomplete`: false

Note: the raw generation omitted one matrix-worthy RAG / temporal-graph cell
from `matrix_export` and missed 20 refs in `source_ref_index_used`. The
normalizer repaired both issues, and normalized validation passed.

## Candidate Signal

Clean positive signal:

- `agent_ops/mcp_tooling/build_human_ai_workflow`
  - deterministic class: `fills_gap`
  - aggregate score: 4.708
  - no exact or related overlap in the accepted matrix
  - accepted value: practical custom/narrow MCP tooling as part of reliable
    human-AI workflow, not generic MCP hype

Overlap with qualitative lift:

- `coding_agents/claude_code_workflows/design_agentic_dev_workflow`
  - deterministic class: `likely_duplicate`
  - exact overlap with Ilia Izmailov, but existing coverage is single-source
  - Doronin score is higher in the candidate report and his angle is different:
    migration from Cursor/Roo/Windsurf to Claude Code, Claude Code Skills vs
    MCP tools, cost/context concerns, and practical operating workflow

- `coding_agents/agentic_dev_process/design_agentic_dev_workflow`
  - deterministic class: `likely_duplicate`
  - exact overlap with AI_Grabli, Akimov, and Ostrikov
  - accepted value is not a new cell; it is a strong anti-vibe engineering
    doctrine with concrete guardrails: BDD, small steps, rules, documentation,
    and keeping the operator responsible for high-cognitive-load decisions

- `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base`
  - deterministic class: `likely_duplicate`
  - exact overlap with Refat
  - qualitatively adjacent: Refat's strongest angle is file-first / Unix-like
    knowledge-base practice, while Doronin's angle is temporal graph memory
    through Graphiti / Hindsight style systems

## Unique Value

Doronin's strongest contribution is a practical, anti-hype AI development
operating model:

- distinguishes vibe coding from disciplined AI-agent development;
- treats code as business liability and business logic as the real asset;
- argues that AI-assisted development raises the importance of architecture,
  analysis, agent management, and stakeholder interaction;
- gives concrete control mechanisms for agents: BDD, Gherkin-like specs,
  Cursor / Claude rules, navigator rules, stage-specific rules, and layered
  documentation;
- has hands-on MCP practice and critique: public MCP servers can be stale,
  bloated, or poorly maintained; custom narrow MCPs are often safer and more
  reliable;
- provides lived tool-selection signal across ChatGPT, Cursor, Windsurf, Roo
  Code, Claude Code, Codex CLI, and Gemini CLI;
- adds a temporal-graph memory viewpoint for agent knowledge bases.

Existing matrix comparison matters:

- AI_Grabli already covers spec-driven / anti-vibe development and RAG
  skepticism, but Doronin is more focused on developer operating discipline and
  concrete agent-control rules.
- Akimov already covers anti-vibe / agentic engineering from an enterprise
  adoption lens, but Doronin is more hands-on in coding-agent setup and MCP.
- Ilia already covers Claude Code workflows, but Doronin adds migration,
  context/cost, Skills-vs-MCP, and process discipline.
- Refat already covers pragmatic agentic engineering and knowledge-base design,
  but Doronin adds temporal-graph memory as a different architectural route.

## Routing Contract

Good fit:

- "How do we avoid turning AI coding into unmaintainable vibe-code debt?"
- "How should we structure rules, BDD, docs, and small steps for Cursor or
  Claude Code?"
- "When should we use Claude Code instead of Cursor / Windsurf / Roo Code?"
- "How should we think about Claude Code Skills vs MCP tools?"
- "When are public MCP servers too broad or stale, and when should we build a
  narrow custom MCP?"
- "How can Graphiti / Hindsight / temporal graphs support agent memory?"

Poor fit:

- beginner-only prompt engineering;
- neutral broad news about every model release;
- primary source for enterprise AI adoption roadmaps, where Akimov is a better
  fit;
- primary source for file-first / Unix-like knowledge-base design, where Refat
  is a better fit;
- primary source for embedding-less RAG/retrieval quality, where AI_Grabli is
  a better fit;
- broad routing for all coding-agent questions without considering overlap.

## Risks

- Overlap is real: 3 of 4 cells are exact overlaps.
- Tool preference and pricing/limit posts age quickly; recent-source weighting
  matters.
- The author is opinionated; outputs should balance him with contrary sources
  for contentious tool-choice questions.
- The RAG/knowledge-base cell was repaired from `matrix_cells`, so it should be
  treated as useful but not over-weighted without query probes.

## Decision

Recommended final status:

`accept_with_routing_caveat`

Accept if the system wants a strong, grounded practitioner source for
disciplined AI-assisted development and custom agent tooling. Do not accept him
as a clean map-expanding expert, and do not route him broadly for every
coding-agent query.

If accepted, the manifest should include:

`accepted as disciplined AI-assisted development / Claude Code workflow / custom
MCP and temporal-agent-memory depth expert; overlap-heavy with coding-agent and
RAG cells, avoid broad duplicate routing`

## Follow-Up Probe

Probe is not required before manual admission, but is useful before production
routing:

- 2 anti-vibe / disciplined AI-assisted development workflow queries against
  AI_Grabli, Akimov, Ostrikov, and Refat;
- 1 Claude Code migration / Skills-vs-MCP query against Ilia and Elkornacio;
- 1 custom narrow MCP workflow query against PashaZloy, Neuraldeep, and Rinat;
- 1 temporal-graph agent memory query against Refat and Air;
- 1 beginner/general coding-agent query where Doronin should not be selected by
  default if a simpler source is enough.
