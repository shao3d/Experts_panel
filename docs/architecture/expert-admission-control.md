# Expert Admission Control

**Status:** Active admission doctrine and matrix workflow
**Last updated:** 2026-05-20
**Haft context:** `prob-20260509-71223b41`, `sol-20260509-ae57b368`

This document defines the decision process for admitting new Telegram experts
into Experts Panel. It sits before the operational import guide
`docs/guides/add-expert.md`.

The goal is not to make expert onboarding slower. The goal is to prevent the
roster from drifting into duplicate, shallow, or noisy sources as the number of
experts grows.

The target product shape is a compact, source-backed practitioner panel for
AI-assisted development. Roster size is not an objective. The objective is
better source selection, better coverage, and better evidence for future Panel
and Panex answers.

---

## 1. Why This Exists

Experts Panel is not just a list of interesting channels. It is a
source-backed retrieval and synthesis system for AI-assisted development.

A new expert is valuable only if they improve future source discovery and final
answers. That means they should add one or more of:

- new topical coverage;
- deeper evidence;
- a distinct practitioner angle;
- better sources for representative Panex questions;
- useful disagreement with existing experts;
- fresh coverage where the current roster is stale or thin.

The admission process must answer a product question:

> Will this candidate make Experts Panel and Panex better, or will they mostly
> duplicate existing experts and add noise?

---

## 2. Existing System Facts

Current local snapshot checked on 2026-05-20:

| Fact | Local evidence |
|------|----------------|
| Runtime roster source | `expert_metadata` + related SQLite rows |
| UI roster source | `frontend/src/config/expertConfig.ts` |
| Local DB path | `backend/data/experts.db` |
| Current metadata rows | 23, including `video_hub` |
| Human Telegram experts | 22 |
| Posts | 8334 rows in `posts` |
| FTS/embedding-eligible text posts | 7895 posts with text length > 30 |
| Embeddings | 7895 rows in `post_embeddings` / `vec_posts` |
| Valid post metadata | 4636 posts with valid `post_metadata` |

Important architecture constraints:

- The current search path uses Hybrid Retrieval: Vector KNN through
  `sqlite-vec`, FTS5/BM25, RRF, and AI Scout query expansion.
- Runtime FTS5 searches `posts.message_text`, not `post_metadata`.
- `post_metadata` is useful as an offline analysis aid, but it is incomplete in
  the current snapshot and is not the runtime retrieval source of truth.
- Panex / Agent Context is explicit-only and source-backed.
- Agent Context uses `source_bundle`, `expert_digest`, `source_key`, and
  `evidence_quality` as its evidence surface.
- Agent Context `source_bundle` / `expert_digest` runs a partial source
  discovery pipeline: retrieval, Map, MEDIUM scoring, HIGH resolve, source
  selection, main-source comment loading, and external-link extraction. It
  intentionally skips the full UI Reduce, language validation, drift scoring,
  comment synthesis, Reddit synthesis, and cross-expert meta-synthesis phases.
- Adding data to production is not the same as a normal code deploy, because
  the production SQLite DB lives on the Fly volume.
- `video_hub` is a separate runtime role, not a normal Telegram expert.

Implication: admission should use existing storage and retrieval primitives
first. Do not invent a separate knowledge base before the current corpus is
measured.

Snapshot caveats:

- Refresh the counts before using them in a decision report; they are not
  invariants.
- Some active experts can have zero valid `post_metadata` in the current local
  DB while still having searchable text posts and embeddings.
- Human-expert comparisons should exclude `video_hub` by default unless the
  candidate is being evaluated as a video-sidecar source.

Refresh commands:

```bash
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM expert_metadata;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM expert_metadata WHERE expert_id != 'video_hub';"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM posts;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM posts WHERE length(COALESCE(message_text,'')) > 30;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM post_embeddings;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM posts_fts;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM posts WHERE post_metadata IS NOT NULL AND json_valid(post_metadata);"
```

---

## 3. Evidence Hierarchy

Use stronger evidence before weaker evidence.

| Level | Evidence | How to use it |
|-------|----------|---------------|
| 1 | Raw post/comment text in `posts`, `comments`, and `links` | Ground representative examples and source review. |
| 2 | Runtime retrieval evidence from `source_bundle`, `source_key`, `source_expand`, and `evidence_quality` | Decide whether the candidate improves source discovery for real questions. |
| 3 | `posts_fts`, `post_embeddings`, `vec_posts`, and Hybrid Retrieval stats | Measure runtime readiness, overlap, and retrievability. |
| 4 | `post_metadata` fields such as `primary_topic`, `concepts`, and `keywords` | Use as a cheap helper for coverage mapping only; never as sole proof. |
| 5 | LLM-generated summaries, semantic passports, labels, and reviews | Use as evidence extraction only when grounded in exact source refs and marked as advisory until compared with the matrix. |

Admission reports must cite Level 1 or Level 2 evidence for every important
claim. A topic label without representative posts is not enough.

---

## 4. Scope

In scope:

- Build a current-roster coverage map.
- Generate expert passports for current experts and candidates.
- Evaluate a candidate from Telegram Desktop JSON before production import.
- Compare candidate coverage against the current roster.
- Run representative query probes only when passport/matrix/arbitration
  evidence is insufficient or production routing weight needs stronger proof.
- Produce a human-readable admission report.
- Return one of `accept`, `reject`, `watchlist`, or `limited_scope`.

Out of scope for MVP:

- Automatic production admission.
- Automatic UI roster mutation.
- Automatic production DB upload.
- A new vector database or external knowledge graph.
- Treating LLM summaries as proof without representative source posts.
- Background/ambient Panex calls.
- Fetching external URLs from posts during admission.
- Replacing `docs/guides/add-expert.md`; that guide starts after the admission
  decision is made.

---

## 5. Core Principle

Do not decide from one signal.

Static topic coverage is useful but insufficient. Query-level source utility is
stronger but more expensive. LLM review catches depth but can over-rationalize.
The admission process should be layered so cheap signals run first and
expensive/high-fidelity checks run only for promising candidates.

### Operating doctrine

The system must stay intentionally simple:

- The semantic passport is the rich, source-grounded description of one expert.
- The knowledge matrix is a compact map of current coverage, gaps, and
  overlaps.
- Deterministic comparison gives only the starting recommendation: clean gap,
  overlap, duplicate-like signal, needs-probe, or possible taxonomy extension.
- The matrix is not the final judge. It is a map and overlap detector.
- When a candidate overlaps existing accepted experts, the decision must move
  to LLM/human arbitration over the actual source evidence: representative
  posts, comments, signature claims, and the closest existing experts' source
  angles.
- The final decision is a product judgment: does this expert improve future
  Panex source selection and answers enough to justify admission?

Do not expand the process into a bureaucracy. Add artifacts only when they help
one of these jobs:

- understand what the expert really contributes;
- see where the current roster already covers the same territory;
- decide whether overlap is useless duplication or a valuable new angle;
- preserve the admission decision so future routing does not forget why the
  expert was accepted or rejected.

Default artifact discipline:

- `semantic_passport`: mandatory for serious candidates;
- `knowledge_matrix`: mandatory current-roster map;
- `candidate_impact_report`: mandatory deterministic preflight;
- `admission_report`: mandatory final decision record;
- `arbitration_report`: only for overlap-heavy, disputed, or strategically
  important cases where the reasoning would otherwise be lost;
- runtime query probes: only when the passport/matrix/arbitration evidence is
  insufficient, disputed, or needed before raising production routing weight.

Avoid introducing new persistent layers, profile indexes, or report families
unless a real runtime or decision need appears. A future routing-profile layer
is allowed only when the Panel/Panex router can actually consume it or when
manual admission decisions become hard to audit from the existing reports.

### Known matrix limits

The knowledge matrix is fit for continued use as the admission map, but only
inside these limits:

- It compresses a rich semantic passport into a small number of comparable
  cells. This is useful for coverage and overlap detection, but it can hide
  differences in audience, stance, source style, and practical depth.
- Coarse coverage can look saturated even when the roster still lacks a useful
  specialist angle. "No missing coarse area" is not the same as "no valuable
  future expert exists."
- Overlap is ambiguous by design. It can mean useless duplication, or it can
  mean a valuable complementary angle inside a dense area.
- The deterministic candidate preflight does not inspect raw posts, runtime
  retrieval behavior, embeddings, or `source_bundle` quality. It gives a
  starting signal only.
- Freshness matters unevenly. Tool-choice, model-comparison, and current
  coding-agent workflow cells should be treated as faster-decaying than durable
  process, governance, or architecture cells.
- Source references make passports auditable, but they do not by themselves
  prove that every model-written claim is semantically fair. Important claims
  still need representative-post review when the decision is consequential.

Therefore the safe operating rule is simple: live with the matrix, but never
delegate final admission authority to it. It is a map and warning system; the
final product decision remains LLM/human arbitration over source evidence when
the candidate is overlap-heavy, high-impact, or strategically important.

Recommended semantic-passport admission pipeline:

```text
candidate Telegram JSON
  -> export source-grounded semantic passport packet
  -> generate and normalize semantic passport
  -> compare passport matrix_export against current knowledge matrix
  -> deterministic candidate preflight
  -> LLM/human arbitration when overlap is non-trivial
  -> admission report
  -> accept / reject / watchlist / limited_scope
  -> only then docs/guides/add-expert.md
```

Escalation-only checks:

```text
uncertain admission or planned production routing weight
  -> staging DB import if runtime-equivalent evidence is needed
  -> embeddings/FTS readiness check
  -> representative source_bundle / expert_digest probes
  -> update or append the admission decision evidence
```

---

## 6. Verdicts

### `accept`

Use when the candidate clearly adds value across several dimensions.

Expected evidence:

- Covers at least one thin or missing area.
- Provides representative posts with practical depth.
- Shows useful source-selection value in the semantic passport, matrix
  comparison, and arbitration evidence.
- If query probes were run, contributes useful selected sources or a distinct
  source angle.
- Does not merely duplicate one existing expert, or clearly adds depth,
  freshness, disagreement, or a materially different practitioner angle.
- Operational cost is justified by expected source utility.
- Candidate is ready for the operational flow in `docs/guides/add-expert.md`.

### `reject`

Use when the candidate is mostly duplicate, shallow, off-scope, stale, or noisy.

Expected evidence:

- High overlap with existing experts.
- Mostly announcements/news without practical insight.
- Weak or no source utility in passport/matrix/arbitration evidence.
- If query probes were run, weak or no contribution in selected sources.
- Adds UI and runtime cost without clear product value.

### `watchlist`

Use when the channel is promising but not ready.

Typical reasons:

- Too few posts.
- Good direction but low cadence.
- Good niche, but not enough evidence yet.
- Useful posts exist, but no clear retrieval utility yet.

### `limited_scope`

Use when the candidate is valuable only for a narrow topic or mode.

Examples:

- Strong for `coding_agents`, weak elsewhere.
- Strong for `evals_quality`, not a general AI expert.
- Useful for `business_adoption`, but noisy for technical questions.
- Good as a hidden/internal expert before full UI exposure.

---

## 7. Candidate Passport

An expert passport is a structured evidence artifact. It should not be only a
LLM-written biography.

Minimum fields:

```json
{
  "expert_id": "candidate_id",
  "channel_username": "telegram_username",
  "post_count": 0,
  "text_post_count": 0,
  "metadata_valid_count": 0,
  "embedding_count": 0,
  "date_range": {
    "first_post": "YYYY-MM-DD",
    "last_post": "YYYY-MM-DD"
  },
  "runtime_readiness": {
    "posts_imported": false,
    "fts_ready": false,
    "embeddings_ready": false,
    "comments_synced": false,
    "drift_scored": false
  },
  "coverage": {
    "coding_agents": 0,
    "agent_ops": 0,
    "ai_product_pm": 0,
    "evals_quality": 0,
    "rag_retrieval_knowledge": 0,
    "business_adoption": 0,
    "security_privacy_governance": 0,
    "ai_ux_workflow": 0,
    "ai_engineering_infra": 0,
    "model_landscape": 0,
    "creative_multimodal": 0,
    "general_ai_news": 0
  },
  "depth_profile": {
    "practitioner_experience": 0,
    "case_study": 0,
    "architecture_analysis": 0,
    "benchmark_or_eval": 0,
    "howto_or_checklist": 0,
    "tool_release": 0,
    "announcement_or_news": 0,
    "low_signal": 0
  },
  "closest_existing_experts": [],
  "signature_topics": [],
  "representative_posts": [],
  "risks": [],
  "recommended_verdict": "watchlist"
}
```

Representative posts are mandatory. Each representative post should include:

- `expert_id`;
- `telegram_message_id`;
- `created_at`;
- short excerpt;
- coverage labels;
- depth label;
- reason it was selected.

Passport interpretation rules:

- A JSON-only passport can estimate coverage and depth, but cannot prove
  runtime retrieval utility.
- Query-probe passports require a staging/local DB with FTS and embeddings for
  the candidate.
- `comments_synced` and `drift_scored` are not required for the first cheap
  passport. They become relevant for high-fidelity probes and source-depth
  review.
- Existing `evidence_quality` labels are calibration, not proof. Map them into
  the broader admission depth taxonomy only with source examples attached.

### Semantic value passport v1.1

The keyword passport above is the cheap baseline. A semantic value passport is
the stronger full-corpus artifact used when we need to understand whether an
expert adds real system value rather than repeated AI vocabulary.

It is generated from:

- all usable `posts.message_text` rows for one expert;
- all available `comments.comment_text` rows nested under their source posts;
- a strict prompt that separates expert voice from community signal;
- a JSON output schema with source references for every important claim.

The semantic passport should describe:

- where the expert has real knowledge, not just frequent terms;
- how deep the coverage is: news, commentary, practical, or deep practitioner;
- which query types this expert is useful for in Panex / Agent Context;
- which subdomains and query intents the expert helps with;
- which practical patterns, warnings, claims, and decision heuristics can be
  reused by the system;
- which domains should get matrix weight from this expert;
- which claims still require matrix comparison against the current roster.

The semantic passport is allowed to be much more informative than the cheap
coverage passport, but it is still not a final admission verdict by itself. It
is evidence extraction over one expert. The final admission decision compares
the passport against the current knowledge matrix and only runs query probes for
borderline, high-value, or disputed cases.

Required semantic passport output groups:

- `corpus_audit`: what the model saw and what it could not know;
- `source_ref_index_used`: cited source refs mapped back to post/comment IDs;
- `expert_positioning`: role, audience, voice, worldview, distinctive angle;
- `knowledge_domains`: domain-level coverage, depth, value, and evidence refs;
- `value_dimensions`: comparable 0-5 scores for insight density, practical
  specificity, evidence quality, source utility, intrinsic distinctiveness,
  anti-hype signal, and domain depth;
- `matrix_cells`: domain x subdomain x query-intent cells with
  depth/practicality/intrinsic-distinctiveness/evidence/source-utility scores;
- `query_intent_fit`: what real Panex / Agent Context questions this expert is
  strong, weak, or bad for;
- `content_quality_distribution`: how much of the channel is deep practitioner
  material, case study, how-to, analysis, announcements, or low signal;
- `matrix_export`: the atomic machine-comparable payload that can be compared
  against the knowledge matrix;
- `signature_insights`: reusable insights or principles with source refs;
- `practical_patterns`: workflows, checklists, heuristics, and failure modes;
- `claims_and_positions`: repeated claims, stances, and dispute risk;
- `source_utility`: best/worst query types and retrieval/source-selection hints;
- `community_signal`: comment themes, questions, corrections, and practical
  feedback, explicitly separated from author voice;
- `admission_implications`: what must be checked against the matrix before a
  candidate verdict;
- `audit`: unsupported claims, abstentions, possible model errors, and most
  important source refs.

Interpretation rules:

- The semantic passport may reduce the number of expensive query probes, but it
  should not eliminate probes for uncertain admissions or production routing
  weight decisions.
- A passport with high `general_ai_news` and low practical/evidence scores is
  weak even if it mentions many AI topics.
- Comments can increase confidence about usefulness, confusion, disagreement,
  or audience fit, but comments do not prove expert knowledge.
- Every matrix-relevant claim must have exact source refs such as `P0042` or
  `P0042.C0003`.
- The passport must score intrinsic distinctiveness, not matrix-relative
  novelty. Matrix-relative novelty is computed only when the passport is
  compared with the current roster matrix.

### Knowledge matrix shape

The long-term matrix should not be a single table of broad topics. It should be
a set of atomic cells that can answer: "Do we already have enough good sources
for this kind of question?"

Recommended cell identity:

```text
<domain_id>/<subdomain_id>/<query_intent_id>
```

Example:

```text
coding_agents/claude_code_workflows/design_agentic_dev_workflow
```

Each cell should track:

- best current experts for the cell;
- coverage level: `none`, `thin`, `moderate`, `strong`;
- depth level: `news`, `commentary`, `practical`, `deep_practitioner`;
- source roles: `primary`, `supporting`, `niche`, `weak`, `avoid`;
- comparable scores for depth, practicality, evidence quality, source utility,
  intrinsic distinctiveness, anti-hype signal, and community signal;
- evidence refs back to source posts/comments;
- freshness and confidence;
- redundancy: whether the roster already has enough good sources for this cell.

Admission comparison should then be mostly matrix math plus human review:

```text
candidate matrix_export
  -> compare against current matrix cells
  -> classify each cell as fills_gap / deepens_existing_cell / adds_viewpoint /
     likely_duplicate / noise_risk / needs_probe
  -> aggregate to accept / limited_scope / watchlist / reject / probe_needed
```

The goal is not to eliminate probes completely. The goal is to make probes
rare: use them only for borderline, high-value, or low-confidence cells.

The matrix also needs rollups above the exact cell level. Exact cells are good
for precise coverage, but they can understate overlap when two experts cover the
same domain and query intent through different subdomains. For example:

```text
agent_ops/claude_code_workflows/design_agentic_dev_workflow
agent_ops/agentic_dev_process/design_agentic_dev_workflow
```

These are distinct exact cells, but both contribute to the broader
`agent_ops/design_agentic_dev_workflow` decision area. The rollup layer is
deterministic and should be used before treating a candidate cell as a genuinely
new gap.

---

## 8. Coverage Taxonomy

The taxonomy must be explicit enough to guide product decisions, but not so
large that every candidate looks unique.

Initial AI-assisted-development coverage areas:

| Area | Meaning |
|------|---------|
| `coding_agents` | Claude Code, Codex, Cursor, Copilot, agentic coding workflows |
| `agent_ops` | MCP, tools, skills, hooks, multi-agent orchestration, local agent setup |
| `evals_quality` | evals, benchmarks, regression tests, quality measurement, failure analysis |
| `rag_retrieval_knowledge` | RAG, embeddings, vector search, search quality, knowledge bases |
| `prompt_engineering` | prompt structure, model-specific formatting, reusable prompting patterns |
| `ai_product_pm` | AI product decisions, PM workflow, adoption strategy, user value |
| `business_adoption` | Business use cases, org rollout, economics, ROI, implementation patterns |
| `ai_ux_workflow` | Human workflow, UX, AI-assisted work design, collaboration patterns |
| `security_privacy_governance` | privacy, compliance, security, governance, risk boundaries |
| `ai_engineering_infra` | deployment, inference, cost, observability, backend/runtime concerns |
| `model_landscape` | model releases, model capabilities, vendor comparisons |
| `creative_multimodal` | image/video/audio generation when relevant to AI-assisted work |
| `general_ai_news` | broad AI news without clear practitioner or product depth |

Depth labels:

| Label | Meaning |
|-------|---------|
| `practitioner_experience` | "I/we tried this", production experience, lessons learned |
| `case_study` | Concrete implementation, project, failure, or adoption story |
| `architecture_analysis` | Trade-offs, system design, technical reasoning |
| `benchmark_or_eval` | Measurements, comparisons, tests, evals |
| `howto_or_checklist` | Reusable practical steps |
| `tool_release` | New tool/model/feature with useful details |
| `announcement_or_news` | Mostly announcement, repost, short news |
| `low_signal` | Thin commentary, hype, unclear value |

Rules:

- A post can have multiple coverage labels.
- A post should have one primary depth label.
- `general_ai_news` should not be enough to admit an expert.
- `tool_release` is useful only when the source adds analysis, context, or
  practical implications.
- Runtime `evidence_quality.source_type` currently uses labels such as
  `practitioner_experience`, `tool_release`, `announcement`, `analysis`,
  `mention`, and `unknown`. Admission reports may map those to the taxonomy
  above, but must keep raw source examples available.

---

## 9. Metrics

### Incremental Retrieval Utility

Question: does the candidate improve source discovery for representative
queries?

Measure:

- percentage of probe questions where candidate contributes selected sources;
- number of candidate sources with medium/high evidence quality;
- number of current-roster misses covered by candidate;
- number of probe answers where candidate adds a distinct angle.

This is the strongest product metric.

For admission probes, compare sources first:

- `experts[].main_sources` in `source_bundle`;
- `experts[].digest.source_refs` and `experts[].digest.source_index` in
  `expert_digest`;
- exact `source_key` handles;
- `evidence_quality.depth`, `source_type`, `comment_signal`, and `confidence`;
- warnings such as retrieval fallback or missing runtime posts.

Do not use final answer fluency as the primary metric.

### Coverage Gap Closure

Question: does the candidate close a thin or missing area?

Measure:

- candidate coverage in taxonomy areas;
- current-roster density in those same areas;
- representative posts for each claimed gap.

### Semantic Overlap

Question: is the candidate mostly a duplicate?

Measure:

- closest experts by embedding/topic distribution;
- shared selected sources/topics in query probes;
- percentage of candidate posts that map to already-dense areas.

High overlap is acceptable only when the candidate adds more depth, freshness,
or a materially different viewpoint.

Overlap should be measured against human Telegram experts by default. Exclude
`video_hub` unless the candidate is a video/transcript source.

### Source Depth Quality

Question: are the candidate's posts useful as evidence?

Measure:

- ratio of practitioner/case/architecture/eval/howto posts;
- ratio of announcements/news/low-signal posts;
- source-grounded sample review.

### Operational Cost

Question: what does this candidate cost to maintain?

Include:

- import time;
- embedding cost;
- Telegram comment sync time;
- optional drift/comment analysis cost;
- production DB deploy risk;
- UI roster complexity;
- future query latency and response size;
- cleanup/removal cost.

### Explainability

Question: can a human understand the recommendation?

Required:

- representative posts;
- closest overlaps;
- gaps addressed;
- probe query results, if probes were run;
- final verdict rationale.

No opaque single score is admissible.

### Reversibility

Question: can we undo this safely?

Preferred path:

- evaluate in local/staging DB first;
- keep candidate out of production UI until accepted;
- use `limited_scope` before full exposure when uncertain.

---

## 10. Query Probe A/B Gate

The query probe set should represent the real questions Experts Panel and
Panex are meant to answer.

Suggested probe groups:

- coding-agent workflow design;
- choosing between Claude Code, Codex, Cursor, Copilot;
- MCP/tools/skills/hooks architecture;
- evals and quality control for AI coding;
- RAG/retrieval/knowledge base design;
- PM/product adoption of AI features;
- enterprise rollout, ROI, governance;
- security/privacy boundaries;
- debugging AI-agent failures;
- cost/performance/latency trade-offs;
- human workflow and AI UX;
- AI-assisted development learning paths.

For each probe:

1. Run current human Telegram roster, excluding `video_hub` by default.
2. Run current roster plus candidate in staging/sandbox.
3. Prefer `response_mode=source_bundle` for audit because it exposes raw
   selected sources; use `expert_digest` only for compact human review.
4. Compare selected source handles and evidence quality.
5. Record whether candidate added:
   - a unique useful source;
   - a better source than existing experts;
   - a missing angle;
   - noise only.

Do not use only final answer fluency. Compare sources first.

Runtime-equivalent probes require the candidate to be present in a staging DB
with FTS and embeddings. A JSON-only candidate preflight cannot answer this
question.

---

## 11. Staging and Sandbox Rules

Candidates should not go straight into the production roster.

MVP staging options, from simplest to stronger:

1. Analyze Telegram JSON directly without DB import.
2. Import into a copied local DB and discard the copy after evaluation.
3. Import under a temporary candidate ID in a staging DB.
4. Add a hidden/internal group only after `accept` or `limited_scope`.

Production DB changes are allowed only after a positive admission decision.

Current tooling caveat:

- `scripts/add_new_expert.sh` is an operational onboarding script for the main
  project DB and currently exports `DATABASE_URL=sqlite:///backend/data/experts.db`.
- Do not use it as a candidate sandbox tool from the main checkout unless the
  target DB is an intentional disposable copy.
- A future candidate evaluator should accept an explicit DB path or create a
  copied staging DB before importing posts.

Stop gates:

- Do not run production DB deploy during admission.
- Do not call `scripts/update_production_db.sh` during admission.
- Do not mutate `frontend/src/config/expertConfig.ts` during candidate
  evaluation.
- Do not run paid/live Vertex-heavy probes until static preflight says the
  candidate is promising.
- Do not run drift analysis just to make a weak candidate look complete.
- Do not present LLM qualitative review as proof unless it cites exact sampled
  posts.

---

## 12. Admission Report

Every serious candidate decision should leave a deterministic decision trail.
The trail should be short enough to read, but complete enough to explain why the
expert was admitted, rejected, deferred, or limited.

Minimal artifact layout:

```text
output/expert_admission/
  admission_manifest.json
  knowledge_matrix/
    knowledge_matrix.json
    knowledge_matrix.md
  candidates/
    <candidate_id>/
      candidate_impact_report.json
      candidate_impact_report.md
      admission_report.md
      admission_report.json
  semantic_passports/
    <expert_id>/
      input/
        run_manifest.json
        semantic_passport_prompt.md
        expert_value_passport_schema_v1_1.json
        <expert_id>_source_ref_index.json
        <expert_id>_corpus.md
        <expert_id>_vertex_prompt.md
      output/
        <expert_id>_semantic_passport.json
        <expert_id>_semantic_passport.normalized.json
        <expert_id>_semantic_passport.md
        <expert_id>_semantic_passport_receipt.json
        <expert_id>_semantic_passport_validation.json
        <expert_id>_semantic_passport.normalized_validation.json
```

The admission manifest's `passport_path` is the SSOT for the accepted passport
location. Some early generated artifacts may use a flat
`semantic_passports/<expert_id>/...` layout instead of the `output/` subfolder;
do not infer acceptance from directory shape.

Optional artifacts:

- `arbitration_report.md/json`: use for overlap-heavy, disputed, or
  strategically important cases.
- `overlap_report.json`: use when the deterministic evaluator produces
  detailed overlap diagnostics.
- `probe_results.json/md`: use only when runtime-equivalent query probes were
  actually run.
- `current_coverage.json/md` and cheap `passports/`: keep as baseline
  diagnostics, not final admission truth.

Minimum `admission_report.md` sections:

```text
# Candidate Admission Report: <candidate_id>

## Verdict
accept | reject | watchlist | limited_scope

## Short Rationale

## Candidate Data

## Coverage Contribution

## Closest Existing Experts

## Representative Source Evidence

## Query Probe Results

## Source Depth Review

## Operational Cost and Risks

## Decision Notes

## Next Action
```

The next action must be one of:

- proceed to `docs/guides/add-expert.md`;
- keep in watchlist;
- reject and do nothing;
- run a deeper candidate probe;
- add as limited/hidden scope after an explicit decision.

---

## 13. Implementation Surface

This section tracks the intended implementation surface and the currently
available MVP slice.

### `backend/scripts/expert_coverage_report.py`

Purpose: build current-roster coverage map and current expert passports.

Status: implemented as a read-only local script.

Inputs:

- `backend/data/experts.db`;
- optional output directory.

Outputs:

- `output/expert_admission/current_coverage.json`;
- `output/expert_admission/current_coverage.md`;
- per-expert passport artifacts.

Implementation note: this script reads `posts.message_text`,
`expert_metadata`, `post_embeddings`, `posts_fts`, and optional
`post_metadata`. It must not depend on `post_metadata` being complete.

Current command:

```bash
backend/.venv/bin/python backend/scripts/expert_coverage_report.py
```

Current limitations:

- labels are heuristic keyword-density labels, not admission verdicts;
- current-roster coverage is useful as a baseline, but candidate value still
  requires a semantic candidate passport and matrix comparison; source-level
  query probes are escalation-only evidence;
- `post_metadata` is advisory only and missing for some experts.

### `backend/scripts/expert_coverage_calibration.py`

Purpose: build a deterministic manual-review packet for checking whether the
current coverage labels are actually grounded in representative source posts.

Status: implemented as a read-only local script.

Inputs:

- `backend/data/experts.db`;
- comma-separated expert IDs;
- posts-per-expert sample size;
- optional output directory.

Outputs:

- `output/expert_admission/calibration/calibration_sample.json`;
- `output/expert_admission/calibration/calibration_sample.md`.

Current command:

```bash
backend/.venv/bin/python backend/scripts/expert_coverage_calibration.py
```

Current calibration note:

- coverage labels are text-first and do not use `post_metadata` as proof;
- calibration sample includes matched terms for each label;
- broad terms still require human review before candidate admission.

### `backend/scripts/export_semantic_passport_packet.py`

Purpose: export the full-context input packet for a semantic value passport.

Status: implemented as a read-only local script. It prepares inputs for a
Vertex/Gemini run but does not call Vertex AI by itself.

Inputs:

- one existing `expert_id`;
- `backend/data/experts.db`;
- optional post/comment caps for smoke testing;
- target model label for the manifest.

Outputs:

- `run_manifest.json`;
- `semantic_passport_prompt.md`;
- `expert_value_passport_schema_v1_1.json`;
- `<expert_id>_source_ref_index.json`;
- `<expert_id>_corpus.md`;
- `<expert_id>_vertex_prompt.md`.

Current command:

```bash
backend/.venv/bin/python backend/scripts/export_semantic_passport_packet.py --expert-id refat
```

Implementation note: the script preserves a stable source-ref system where
`P0001` is a post and `P0001.C0001` is a comment under that post. The prompt
requires the model to keep author voice and community signal separate. The
packet also exports a full `source_ref_index` so passport evidence refs can be
mapped back to `post_id`, `telegram_message_id`, `comment_id`, and
`telegram_comment_id`.

### `backend/scripts/run_semantic_passport_vertex.py`

Purpose: run a prepared semantic passport packet through Vertex AI and validate
the returned passport.

Status: implemented for full semantic-passport runs.

Inputs:

- a packet directory produced by `export_semantic_passport_packet.py`;
- Vertex AI credentials from local env / ADC;
- target model, defaulting to the packet manifest model.

Outputs:

- `<expert_id>_count_tokens_response.json`;
- `<expert_id>_generate_content_response.json`;
- `<expert_id>_semantic_passport.raw.txt`;
- `<expert_id>_semantic_passport.json`;
- `<expert_id>_semantic_passport.normalized.json`;
- `<expert_id>_semantic_passport_receipt.json`;
- `<expert_id>_semantic_passport_validation.json`;
- `<expert_id>_semantic_passport.normalized_validation.json`.

Current preflight command:

```bash
backend/.venv/bin/python backend/scripts/run_semantic_passport_vertex.py --count-only
```

Current generation command:

```bash
backend/.venv/bin/python backend/scripts/run_semantic_passport_vertex.py
```

Current validation/normalization commands:

```bash
backend/.venv/bin/python backend/scripts/run_semantic_passport_vertex.py --validate-existing
backend/.venv/bin/python backend/scripts/run_semantic_passport_vertex.py --normalize-existing
backend/.venv/bin/python backend/scripts/run_semantic_passport_vertex.py --validate-existing --normalized
```

Implementation note: raw Gemini output is preserved as evidence. The normalized
passport is the preferred downstream matrix input because deterministic
post-processing can hydrate missing `source_ref_index_used` entries from the
packet's full source index, set `passport_meta.generated_at` from the packet
manifest, and repair missing strong/signature `matrix_export.cells` from
`matrix_cells` without changing the semantic judgments. Validation exposes
`matrix_export_incomplete` when matrix-worthy cells would otherwise be lost.

### `backend/scripts/build_knowledge_matrix.py`

Purpose: aggregate normalized semantic passports into the current knowledge
matrix and taxonomy review surface.

Status: implemented for the accepted semantic-passport roster.

Inputs:

- `output/expert_admission/admission_manifest.json`, which is the SSOT for
  which passports are part of the accepted knowledge matrix;
- normalized semantic passports referenced by `passport_path` in the admission
  manifest;
- each passport's `matrix_export.cells`.

Outputs:

- `output/expert_admission/knowledge_matrix/knowledge_matrix.json`;
- `output/expert_admission/knowledge_matrix/knowledge_matrix.md`.

Current command:

```bash
backend/.venv/bin/python backend/scripts/build_knowledge_matrix.py
```

Implementation note: the script is deterministic and does not call Vertex. It
uses `output/expert_admission/admission_manifest.json` by default, so generated
or rejected candidate passports do not silently become part of the system's
knowledge map. Explicit passport paths override the manifest, and
`--include-all-passports` is available for diagnostic/all-artifact inspection.
The matrix groups cells by `<domain_id>/<subdomain_id>/<query_intent_id>`,
computes coverage/redundancy summaries, ranks best experts per cell, and flags
domain, subdomain, or query-intent values that are outside the seed taxonomy as
`proposed_extension` items for taxonomy review.

Since `knowledge_matrix.v0.3`, the script also emits rollups:

- `domain`: broad domain-level coverage;
- `domain_query_intent`: the main near-overlap layer used for admission
  decisions;
- `query_intent`: cross-domain view of the kinds of questions the roster can
  answer.

The most important output for duplicate/complement detection is
`related_cell_overlaps`: cases where two or more experts cover the same
`domain_id + query_intent_id` through different exact cells. This catches
semantic overlap without using another LLM pass.

Current accepted-matrix snapshot after Doronin admission on 2026-05-10:

- 14 accepted passports;
- 38 active matrix cells;
- 28 single-source exact cells;
- 10 strong multi-source exact cells;
- 8 related-cell overlaps at the `domain + query_intent` level;
- 0 taxonomy extensions;
- 18 strong single-source cells;
- `output/expert_admission/admission_manifest.json` is the accepted-roster
  gate.

Important interpretation notes:

- The matrix is intentionally compact. Do not split cells just to make every
  overlap look unique.
- `routing_caveat` in the admission manifest is a short routing warning, not a
  second verdict and not a limited-access flag.
- Overlap-heavy accepted experts should be treated as depth/angle additions
  unless the admission report explicitly identifies a clean gap.
- Doronin adds the clean cell
  `agent_ops/mcp_tooling/build_human_ai_workflow` and strengthens Claude Code
  workflow plus temporal-graph memory coverage, but remains overlap-heavy.

### `backend/scripts/evaluate_expert_candidate.py`

Purpose: evaluate one normalized semantic passport against the current roster
baseline without production admission.

Status: implemented as deterministic JSON-only semantic preflight.

Inputs:

- candidate normalized semantic passport path;
- optional explicit baseline passport paths;
- admission manifest for accepted baseline selection;
- semantic-passport input root;
- output directory.

Outputs:

- `candidate_impact_report.json`;
- `candidate_impact_report.md`;
- `overlap_report.json`.

Current command example:

```bash
backend/.venv/bin/python backend/scripts/evaluate_expert_candidate.py \
  --candidate-passport output/expert_admission/semantic_passports/ai_architect/output/ai_architect_semantic_passport.normalized.json
```

Implementation note: this script does not call Vertex, does not inspect raw
posts, and does not mutate `backend/data/experts.db`. By default it builds the
baseline from accepted passports in `output/expert_admission/admission_manifest.json`,
then excludes the candidate's own passport/expert ID. Explicit
`--baseline-passport` values override the manifest, and
`--include-all-baseline-passports` restores all-passport diagnostic behavior. It
classifies candidate cells as:

- `fills_gap`;
- `adds_adjacent_viewpoint`;
- `deepens_existing_cell`;
- `likely_duplicate`;
- `taxonomy_extension`;
- `needs_probe`;
- `noise_risk`.

Confidence values are normalized before classification because older/LLM-shaped
passports may express confidence either as `0..1` or as `0..5`.

Since the density-policy update, the evaluator also computes whether the
candidate is overlap-heavy:

- share of candidate cells with exact or related accepted-roster overlap;
- number of cells touching dense accepted rollups;
- number of clean gaps outside accepted overlap;
- number of positive signals that are adjacent/depth signals rather than clean
  gaps.

When a candidate is useful but mostly lands in dense accepted areas, the
preliminary recommendation becomes `overlap_heavy_needs_stronger_review`
instead of plain `promising_needs_human_review`.

The output is a diagnostic impact report, not a final `accept/reject`
admission decision. Final admission still requires human review and, for
borderline cases where passport/matrix/arbitration evidence is insufficient,
runtime-equivalent probes.

### `backend/scripts/calibrate_candidate_evaluator.py`

Purpose: run leave-one-out calibration for the deterministic candidate
evaluator before using it on additional experts.

Status: implemented.

Inputs:

- normalized semantic passport paths, or the accepted passports from
  `output/expert_admission/admission_manifest.json`;
- output directory.

Outputs:

- `leave_one_out_summary.json`;
- `leave_one_out_summary.md`;
- per-candidate diagnostic reports under `per_candidate/<expert_id>/`.

Current command example:

```bash
backend/.venv/bin/python backend/scripts/calibrate_candidate_evaluator.py
```

Implementation note: this script does not call Vertex and does not mutate the
database. It treats each existing expert as a candidate while all other
accepted passports form the baseline. Explicit passport paths override the
manifest, and `--include-all-passports` restores all-artifact calibration. The
goal is to validate that `fills_gap`, `adds_adjacent_viewpoint`,
`likely_duplicate`, and `needs_probe` behave sensibly on known experts before
spending on more candidate passports.

Current accepted-roster leave-one-out result after Doronin admission on
2026-05-10:

- 14 cases;
- 52 candidate cells;
- 25 positive impact signals;
- 24 exact overlaps;
- 12 related overlaps;
- 0 duplicate-only cases;
- 10 cases return `overlap_heavy_needs_stronger_review`;
- 3 cases return `probe_needed`;
- 1 case returns `promising_needs_human_review`;
- `ai_architect`, `ai_grabli`, `elkornacio`, `ilia_izmailov`, `ostrikov`, and
  `refat` each include at least one `needs_probe` cell.

### `backend/scripts/expert_admission_probe.py`

Purpose: run representative query probes for current roster vs current plus
candidate.

Status: planned.

Inputs:

- probe set JSON;
- current DB or staging DB;
- candidate ID;
- selected experts/group policy;
- source mode (`source_bundle` preferred for audit).

Outputs:

- probe results JSON;
- source contribution table;
- recommendation inputs.

---

## 14. Relationship To Existing Docs

Use this document when deciding whether a candidate should enter the system.

Use `docs/guides/add-expert.md` only after the admission verdict is `accept` or
an explicit `limited_scope` decision says to import.

Use `docs/architecture/current-expert-roster.md` to update the official roster
after import.

Use `docs/architecture/pipeline.md` and
`docs/architecture/super-passport-search.md` when changing the runtime
retrieval/synthesis behavior used by probes.

Use `docs/architecture/agent-context-api.md` when candidate evaluation needs to
reuse `source_bundle`, `expert_digest`, `source_key`, or `evidence_quality`.

---

## 15. MVP Acceptance Checklist

Current-roster baseline slice is complete when:

- current-roster coverage can be generated from local SQLite;
- every current human expert has a basic passport;
- report includes representative posts, not only labels;
- no paid/live probes run unless explicitly requested;
- production roster and UI are unchanged during evaluation.

Candidate preflight slice is complete when:

- a candidate Telegram JSON can produce a candidate passport without production
  mutation;
- candidate report explains novelty, overlap, depth, and operational risk;
- report compares the candidate against the current coverage baseline.

The next slice can add query probes and stronger A/B source contribution
measurement.

The third slice can add hidden/limited-scope canary behavior if the product
needs it.
