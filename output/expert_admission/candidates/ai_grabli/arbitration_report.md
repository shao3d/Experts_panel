# Semantic Arbitration Report: ai_grabli

## Verdict

`accept_with_routing_caveat`

AI_Grabli looks admission-worthy, but not as another broad coding-agents
source. The admission basis is the distinctive retrieval-quality / RAG
engineering angle, with a secondary structured-output / logprobs eval signal.

This report is an arbitration recommendation only. It does not add AI_Grabli to
the admission manifest.

## Short Rationale

The deterministic report is intentionally cautious:

- candidate cells: 4
- clean gaps: 1
- adjacent viewpoint: 0
- deepens existing cell: 0
- likely duplicate: 2
- needs probe: 1
- exact overlaps: 2
- related overlaps: 0
- recommendation: `overlap_heavy_needs_stronger_review`

That caution is correct. Half of the candidate cells overlap existing accepted
coverage, especially Ostrikov, Ilia Izmailov, AI Architect, Polyakov, and
Glebkudr. However, one cell is a clean matrix gap with high score and strong
source evidence: `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality`.

The passport also shows a useful "grabli" style: practical failure analysis,
anti-hype framing, concrete implementation details, and comments with technical
pushback.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/ai_grabli/output/ai_grabli_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/ai_grabli/candidate_impact_report.md`
- Current accepted matrix:
  `output/expert_admission/knowledge_matrix/knowledge_matrix.json`
- Corpus packet:
  `output/expert_admission/semantic_passports/ai_grabli/input/run_manifest.json`

## Corpus And Run

- corpus used: 355 posts and 2650 comments
- comment cap: none
- date range: 2024-01-10 to 2026-05-01
- Vertex input tokens: 539505
- Vertex output tokens: 12361
- thoughts tokens: 3193
- finish reason: `STOP`
- normalized passport validation: passed
- normalized `matrix_export_incomplete`: false

Note: the raw generation omitted one matrix-worthy cell from `matrix_export`.
The normalizer repaired it from `matrix_cells`, and the normalized validation
passed.

## Candidate Signal

Accepted-like signal:

- `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality`
  - deterministic class: `fills_gap`
  - aggregate score: 4.792
  - no exact or related overlap in the accepted matrix
  - strongest source evidence: embedding-less RAG, LLM-based page filtering,
    large-context retrieval, structured intermediate steps, and source-line
    traceability

Probe/supporting signal:

- `prompt_engineering/reasoning_control/build_ai_dev_eval`
  - deterministic class: `needs_probe`
  - aggregate score: 4.387
  - useful angle: logprobs and thresholds for LLM classification
  - should not be counted as fully proven matrix expansion without a targeted
    probe or routing test

Overlap / duplicate signal:

- `coding_agents/agentic_dev_process/design_agentic_dev_workflow`
  - exact overlap with Ostrikov
  - related multi-source rollup already covered by Ostrikov and Ilia Izmailov
- `coding_agents/claude_code_workflows/choose_ai_coding_tool`
  - exact overlap with AI Architect
  - related multi-source rollup already covered by Polyakov, Ilia, AI Architect,
    and Glebkudr

## Unique Value

AI_Grabli's strongest contribution is not "yet another Claude Code/Codex
expert." The unique value is closer to AI-engineering troubleshooting:

- embedding-less or LLM-first retrieval when vector similarity gives wrong
  factual relevance;
- practical RAG failure taxonomy: logical operators, aggregation, tables,
  short-query-vs-long-chunk mismatch, and source traceability;
- concrete alternatives: LLM filtering, large-context page selection, structured
  SQL/tag extraction, and no-generation retrieval modes;
- probabilistic structured output with logprobs and thresholds;
- spec-driven development and tool-boundary discipline as supporting patterns,
  not the main admission basis.

Existing matrix comparison matters here:

- Refat and Air already cover `design_rag_knowledge_base`.
- AI_Grabli adds `improve_retrieval_quality`, which is a different query
  intent and a cleaner operational angle.
- Coding-agent workflow coverage is already dense; accepting AI_Grabli should
  not increase broad coding-agent routing weight by default.

## Routing Contract

Good fit:

- "Why does embedding/vector search fail on this RAG task?"
- "How can we improve factual relevance in retrieval?"
- "When should we use LLM filtering or large-context retrieval instead of
  embeddings?"
- "How should we handle tables, logical operators, aggregation, and source
  traceability in RAG?"
- "How do we use logprobs and thresholds for LLM classification?"
- "How do we turn AI-development mistakes into safer workflow rules?"

Poor fit:

- broad AI news;
- business adoption or executive AI strategy;
- primary source for Claude Code / Codex tool choice;
- primary source for general agentic development workflow when Ostrikov, Ilia,
  AI Architect, or Polyakov are better matches;
- beginner-friendly non-technical AI onboarding.

## Risks

- Overlap-heavy candidate: two of four cells are likely duplicates.
- Strong personal-practitioner lens may overgeneralize from his own consulting
  and tool preferences.
- The retrieval angle is valuable but may be cost-sensitive: LLM retrieval can
  be much more expensive than embeddings at large scale.
- The `reasoning_control/build_ai_dev_eval` cell needs a probe before being
  treated as a strong standalone matrix expansion.

## Decision

Recommended final status:

`accept_with_routing_caveat`

Accept if the system wants stronger practical coverage of RAG/retrieval-quality
failure modes and LLM-first retrieval alternatives. Do not accept him merely as
another coding-agent expert.

If accepted, the manifest should include:

`accepted for retrieval-quality / embedding-less RAG and practical AI-engineering
failure analysis; coding-agent coverage overlaps existing experts, avoid broad
duplicate routing`

## Follow-Up Probe

Probe is not required before manual admission, but is useful before broad
production routing:

- 2 RAG failure / retrieval-quality queries against Refat and Air;
- 1 embedding-less RAG vs hybrid/vector retrieval query;
- 1 logprobs/thresholds LLM-classification query;
- 1 coding-agent workflow query where AI_Grabli should be supporting, not the
  primary source.
