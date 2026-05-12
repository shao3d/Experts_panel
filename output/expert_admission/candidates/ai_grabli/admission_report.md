# Candidate Admission Report: ai_grabli

## Verdict

accept

## Short Rationale

AI_Grabli is accepted as a high-value practical AI-engineering source for the
Experts Panel knowledge matrix.

The acceptance is based on a valid normalized semantic passport, deterministic
matrix preflight, qualitative arbitration, and manual human approval. He is not
accepted as another broad coding-agents expert. His strongest incremental value
is retrieval quality: embedding-less RAG, LLM-based filtering, large-context
retrieval, source traceability, and concrete failure analysis for cases where
vector similarity is not enough.

## Candidate Data

- Expert ID: `ai_grabli`
- Display name: Tech_AI_grabli
- Channel username: `@oestick`
- Corpus used for passport: 355 posts and 2,650 comments
- Passport prompt tokens: 539,505
- Passport output tokens: 12,361
- Passport thoughts tokens: 3,193
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/ai_grabli/output/ai_grabli_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/ai_grabli/candidate_impact_report.md`
- Arbitration report: `output/expert_admission/candidates/ai_grabli/arbitration_report.md`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality` | Accepted as the primary clean gap: practical retrieval-quality improvement, embedding-less RAG, LLM page filtering, large-context retrieval, and source traceability. |
| `prompt_engineering/reasoning_control/build_ai_dev_eval` | Accepted as supporting/probe-needed signal: logprobs and thresholds for LLM classification, not yet a broad standalone routing basis. |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | Accepted as overlap/supporting depth only; exact overlap with Ostrikov and related rollup overlap with Ilia. |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | Accepted as overlap/supporting depth only; exact overlap with AI Architect and related rollup overlap with Polyakov, Ilia, and Glebkudr. |

Candidate preflight summary:

- Candidate cells in `matrix_export`: 4
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Needs probe: 1
- Likely duplicate: 2
- Taxonomy extensions after taxonomy update: 0
- Exact overlaps: 2
- Related overlaps: 0
- Preliminary recommendation: `overlap_heavy_needs_stronger_review`

## Closest Existing Experts

Closest overlap is in the coding-agent area:

- Ostrikov: exact overlap for `design_agentic_dev_workflow`.
- Ilia Izmailov: related overlap for `design_agentic_dev_workflow` and
  `choose_ai_coding_tool`.
- AI Architect: exact overlap for Claude Code tool choice.
- Polyakov and Glebkudr: related overlap in the broader
  `choose_ai_coding_tool` rollup.

Accepted differentiation:

- Refat and Air already cover `design_rag_knowledge_base`.
- AI_Grabli adds the more operational `improve_retrieval_quality` intent.
- His best use is diagnosing retrieval failures and proposing LLM-first or
  hybrid alternatives when embeddings produce wrong factual relevance.

## Representative Source Areas

Representative source refs from the normalized passport and spot checks:

- `P0280`: embedding-less RAG, LLM page filtering, large-context retrieval,
  structured intermediate steps, and source traceability.
- `P0300`: logprobs and thresholds for robust LLM classification.
- `P0245`: spec-driven AI-assisted development and diff-based code generation.
- `P0289`: MCP/tool-boundary discipline and subagent-oriented workflow design.

## Query Probe Results

No runtime-equivalent query probe was run for this acceptance.

This is acceptable in the current manual mode because the candidate passport,
matrix preflight, source spot checks, and arbitration report already show one
clean high-value contribution. If AI_Grabli later receives broad production
routing weight, run probes focused on:

- RAG failure / retrieval-quality queries against Refat and Air;
- embedding-less RAG vs hybrid/vector retrieval;
- logprobs and thresholds for LLM classification;
- coding-agent workflow queries where AI_Grabli should be supporting, not the
  primary source.

## Source Depth Review

The passport shows strong source depth for practical AI engineering:

- `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality`: strong,
  deep-practitioner, primary role, clean gap.
- `prompt_engineering/reasoning_control/build_ai_dev_eval`: strong,
  deep-practitioner, supporting role, probe-needed before broad routing.

## Operational Cost and Risks

Accepted with these caveats:

- Do not route AI_Grabli as a general coding-agent expert by default.
- Do not count Claude Code / Codex tool-choice coverage as a new gap.
- LLM-first retrieval can be more expensive than embeddings at large scale; use
  him most strongly where factual relevance, logic, tables, aggregation, or
  traceability matter more than raw retrieval cost.
- Treat the logprobs/eval cell as promising but probe-needed before raising
  production routing weight.

## Decision Notes

Human decision recorded on 2026-05-10 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- qualitative arbitration report;
- accepted 9-passport knowledge matrix before admission.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with AI_Grabli as accepted in the semantic knowledge matrix. Keep the
routing caveat: he is primarily a retrieval-quality / embedding-less RAG and
practical AI-engineering failure-analysis expert, not a broad duplicate
coding-agent source.
