# Knowledge Matrix Health Review After 17 Experts

Generated: 2026-05-12

## Scope

This is a top-down health review of the accepted expert-admission knowledge matrix after all 17 current human experts were accepted into the matrix.

This review does not rerun semantic-passport generation, representative-post arbitration, or runtime Panex probes. It checks whether the resulting matrix is coherent, useful, and aligned with the lightweight admission doctrine.

## Evidence Checked

- `output/expert_admission/admission_manifest.json`
- `output/expert_admission/knowledge_matrix/knowledge_matrix.json`
- `output/expert_admission/knowledge_matrix/knowledge_matrix.md`
- `output/expert_admission/candidate_calibration/leave_one_out_summary.md`

## Current State

- Accepted matrix experts: 17
- Matrix cells: 43
- Domain rollups: 10
- Domain + intent rollups: 29
- Taxonomy extensions currently proposed: 0
- Strong single-source cells: 18
- Strong multi-source cells: 13
- Total single-source cells: 30
- Related-cell overlaps: 9
- Strong domain + intent multi-source rollups: 10

## Short Verdict

The matrix is healthy enough to serve as the admission and routing map.

It is not a final judge. Its strongest current value is to show:

- where the panel is already dense;
- where a new expert is only adding another voice in a crowded area;
- where a new expert might deepen a weak or single-source area;
- where LLM/human arbitration must compare real posts before accepting or rejecting.

The process is not leaky at the conceptual level: accepted experts have semantic passports, admission records, routing caveats, and matrix placement. The leave-one-out calibration found no duplicate-only expert under current heuristics.

## Strong Areas

The panel is now meaningfully strong in these areas:

- Coding-agent workflows and AI-assisted development process.
- Claude Code / Cursor / Windsurf / Codex tool-choice and workflow practice.
- Agent operations: MCP, tool calling, multi-agent workflow, reasoning control.
- Prompt engineering: model-specific formatting, reasoning control, context compression.
- RAG / knowledge-base design / retrieval-quality discussions.
- Local LLM and inference-practicality cluster.
- Early but useful product/business adoption layer.

## Crowded Areas

These areas are overlap-heavy and should be strict for future candidates:

- `coding_agents/agentic_dev_process/design_agentic_dev_workflow`
- `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool`
- `agent_ops/mcp_tooling/design_agentic_dev_workflow`
- `coding_agents/choose_ai_coding_tool` rollup
- `coding_agents/design_agentic_dev_workflow` rollup
- `agent_ops/design_agentic_dev_workflow` rollup

Future experts in these zones should not be accepted just because they talk about Claude Code, Cursor, Codex, agents, MCP, or vibe coding. They need a clearly different angle, stronger evidence, unusually good source posts, or a distinct audience/use case.

## Brittle Areas

Single-source coverage is not automatically bad, but it means the panel depends on one voice for that cell. These are the areas to treat carefully:

- Security/privacy/governance is thin and mostly moderate.
- Evals/reliability has strong voices, but is concentrated.
- Deployment/observability for AI-dev systems is concentrated.
- Product-management and AI-product workflow coverage is useful but still narrow.
- Business adoption has useful coverage, but it is not yet broad.
- Codex-specific workflow coverage is still narrower than Claude/Cursor coverage.
- Model-comparison and current tool-choice guidance can age quickly.

These are good target areas for future genuinely complementary experts.

## Calibration Reading

Leave-one-out calibration shows:

- 17 cases checked.
- 66 candidate cells total.
- 28 positive impact signals.
- 36 exact overlaps.
- 12 related overlaps.
- 12 cases marked `overlap_heavy_needs_stronger_review`.
- 4 cases marked `probe_needed`.
- 1 case marked `promising_needs_human_review`.
- 0 duplicate-only cases.

Important: a low mechanical impact score does not mean an expert should be removed. It means the deterministic matrix alone cannot prove uniqueness. Under the current doctrine, overlap-heavy cases need semantic arbitration over representative posts.

## Main Process Risks

1. Overlap can look worse than it is.
   Two experts can share a cell but differ by audience, depth, practical stance, or evidence quality.

2. Overlap can also look safer than it is.
   The matrix can miss that two experts are repeating the same claims in different words.

3. Passport quality depends on corpus selection.
   If comment/post sampling is uneven, a passport can overrepresent noisy or recent material.

4. Current model/tool advice decays quickly.
   Tool-choice and model-comparison cells should be refreshed or probed more often than durable workflow cells.

5. Zero taxonomy extensions is acceptable now, but should not become dogma.
   It suggests the current vocabulary is stable, but future experts may expose genuinely new domains.

## Doctrine Check

The current system matches the intended doctrine:

- Semantic passport is the grounded expert profile.
- Knowledge matrix is the map and overlap detector.
- Deterministic preflight gives an initial signal, not a final verdict.
- Overlap-heavy or high-impact cases require LLM/human arbitration over real posts.
- Runtime query probes are optional escalation, not mandatory bureaucracy.
- `post_metadata` is legacy/offline advisory data; runtime retrieval relies on source text, FTS, embeddings, and reranking.

## Recommended Next Step

Freeze this matrix as `v0.3` baseline and add a small routing-probe suite.

The probe suite should be lightweight: about 20 representative user queries, covering crowded areas, brittle single-source areas, and cross-domain questions. Its purpose is not to re-judge admission. Its purpose is to verify that Panex/runtime retrieval actually routes to the right experts and source posts according to the matrix.

Suggested probe groups:

- coding-agent workflow and tool-choice overlap;
- Codex-specific workflow;
- Claude Code workflow;
- RAG / knowledge-base design;
- evals and reliability;
- local LLM / inference cost;
- AI-product / PM workflow;
- business adoption / ROI;
- security/privacy/governance.

## Bottom Line

The matrix is coherent and useful. The main danger is not that it is too poor; the main danger is trusting it too mechanically.

The right next move is not to add more admission artifacts. It is to test routing behavior with a small query-probe suite and keep LLM/human arbitration for real overlap decisions.
