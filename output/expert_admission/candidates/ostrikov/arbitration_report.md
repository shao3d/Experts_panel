# Semantic Arbitration Report: ostrikov

## Verdict

`accept_with_routing_caveat`

Ostrikov looks admission-worthy, but not as a clean new-gap expert. He should
be treated as a high-signal complementary source for practical agent
architecture, AI-first development process, PRD-to-agent workflows, context
compaction, and community-tested coding-agent patterns.

This report was written before final admission. Ostrikov has since been
accepted in the admission manifest with a routing caveat.

## Short Rationale

The deterministic report is cautious:

- candidate cells: 4
- adjacent viewpoint: 1
- likely duplicate: 1
- needs probe: 2
- clean gaps: 0
- recommendation: `promising_but_probe_or_taxonomy_review`

That caution is correct. The accepted roster already has strong agentic
workflow coverage, especially after Glebkudr. Ostrikov's value is not broad
novelty. His value is a very practical, engineering-led viewpoint: how to
structure AI-first development, agent loops, PRDs, skills, context compaction,
and production trade-offs.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/ostrikov/output/ostrikov_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/ostrikov/candidate_impact_report.md`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`

## Corpus And Run

- corpus used: 68 posts and 1188 comments
- comment cap: none
- Vertex input tokens: 191845
- Vertex output tokens: 10117
- finish reason: `STOP`
- normalized passport validation: passed
- `matrix_export_incomplete`: false

## Candidate Signal

Accepted-like signal:

- `coding_agents/agentic_dev_process/design_agentic_dev_workflow`
  - adjacent viewpoint
  - strong/deep-practitioner
  - useful as AI-first development-process and PRD-to-agent workflow coverage

Overlap signal:

- `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow`
  - exact overlap with Glebkudr
  - should not be counted as a new gap

Probe-only / supporting signal:

- `ai_engineering_infra/rag_architecture/design_rag_knowledge_base`
  - useful RAG trade-off material, but not core enough for admission
- `business_adoption/human_ai_workflow/build_human_ai_workflow`
  - interesting AI-Fluency framing, but should not be the main admission basis

## Unique Value

Ostrikov's best contribution is an engineering operator's view of AI-first
software development:

- AI-optimized PRD structure for one-shot or low-iteration service generation;
- simple agent loop / REPL-loop thinking as an anti-hype alternative to overly
  complex agent frameworks;
- 3-level context compaction from practical agent architecture analysis;
- SKILL.md as a way to encode domain expertise for agents;
- community-tested hackathon and open-source agent examples.

This is close to Glebkudr, Refat, Neuraldeep, and Ilia, but not identical.
Glebkudr is stronger on context engineering and cost/attention management.
Ostrikov is stronger on practical AI-first development process, templates,
community demos, and readable architecture teardown.

## Routing Contract

Good fit:

- "How should we structure a PRD for an AI coding agent?"
- "What does an AI-first development process look like?"
- "How do agent loops, skills, context compaction, and tools fit together?"
- "What simple architecture should we use instead of an overcomplicated agent
  graph?"
- "What can we learn from hackathon/open-source coding agents?"

Poor fit:

- foundational ML or model training;
- neutral broad model comparison;
- enterprise governance/security policy;
- source of record for RAG architecture;
- beginner non-technical product leadership where Misha-like or PM-oriented
  sources would be more direct.

## Risks

- The corpus is compact: only 68 posts, though comments are active.
- Several posts are stream/hackathon announcements; some source depth may live
  outside the text corpus in video.
- He increases density in an already crowded agentic workflow area.
- If admitted too broadly, he may duplicate Glebkudr/Refat/Neuraldeep routing.

## Decision

Recommended final status:

`accept`

Do not admit Ostrikov as a gap expander. Admit him if the system wants a strong
engineering-practitioner voice for practical agent architecture and AI-first
development process. The manifest entry should include a routing caveat:

`accepted as complementary/depth expert for AI-first development process and
practical agent architecture; avoid counting agent_ops overlap as a new gap`

## Follow-Up Probe

Runtime probes are useful but not mandatory before manual admission. If run,
use:

- 2 PRD-to-agent workflow queries;
- 2 agent architecture / context compaction queries;
- 1 overlap query against Glebkudr;
- 1 RAG query where he should remain supporting, not primary.
