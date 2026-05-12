# Expert Coverage Calibration Review

Generated: `2026-05-09`

Scope: manual review of the current coverage-map calibration packet for five
experts: `akimov`, `kornish`, `neuraldeep`, `refat`, and `silicbag`.

Reviewed artifacts:

- `output/expert_admission/current_coverage.md`
- `output/expert_admission/calibration/calibration_sample.md`
- `output/expert_admission/calibration/calibration_sample.json`

## Short Verdict

The map is now more grounded than the first version because coverage labels are
derived from raw `posts.message_text`, not hidden `post_metadata`.

It is representative enough for a current-roster baseline and candidate
preflight, but not yet decision-grade for admitting or rejecting a candidate.

Use it to answer:

- what broad areas the current corpus visibly talks about;
- which experts dominate broad areas;
- where candidate overlap is obvious;
- which posts should be inspected next.

Do not use it alone to answer:

- whether a broad area is truly solved;
- whether a candidate adds real source utility;
- whether a top-count expert is the best evidence source for a query.

## What Was Calibrated

### 1. `post_metadata` no longer proves coverage

Problem found: some labels were not auditable from the visible excerpt because
they could be introduced by `post_metadata`.

Change made:

- `post_metadata` remains in passports as advisory metadata signals.
- Coverage labels now use raw post text only.
- A regression test verifies that metadata-only `RAG` / `MCP` / `eval` terms do
  not create coverage labels.

Impact:

- Representative posts are easier to audit.
- Coverage is less semantically rich, but more source-grounded.

### 2. Generic `поиск` no longer proves RAG/retrieval

Problem found: `поиск` was too broad and could match ordinary search, business
search, product discovery, or information search without real RAG/retrieval
content.

Change made:

- Removed generic `поиск` from `rag_retrieval_knowledge`.
- Kept stronger terms such as `rag`, `retrieval`, `vector search`,
  `embedding`, `fts`, `search quality`, `вектор`, `эмбеддинг`, and
  `база знаний`.

Impact:

- `rag_retrieval_knowledge` count dropped to a more conservative baseline:
  `428` matching posts in the current report.

### 3. Generic `анонс` / `релиз` / `новость` no longer prove AI news

Problem found: generic announcement terms could classify non-AI hardware news as
`general_ai_news`.

Change made:

- Removed `новость`, `анонс`, and `релиз` from `general_ai_news`.
- Kept AI-specific terms such as `ai news`, `искусственный интеллект`, and
  `нейросет`.

Impact:

- `general_ai_news` count dropped to a more conservative baseline:
  `54` matching posts in the current report.

### 4. Calibration sample now includes matched terms

Problem found: reviewing labels without knowing what triggered them is too
opaque.

Change made:

- `expert_coverage_calibration.py` now emits matched terms for each coverage
  and depth label.

Impact:

- Future review can pinpoint whether an error came from a broad keyword,
  taxonomy design, or source text ambiguity.

## Manual Findings

### Coverage labels

Overall coverage labels are grounded at the broad-topic level, but they still
over-label multi-topic posts.

Strongest labels:

- `model_landscape`: usually grounded when model/vendor names are present.
- `coding_agents`: usually grounded when Codex, Claude Code, Cursor, Windsurf,
  Copilot, coding, or agentic coding terms are present.
- `rag_retrieval_knowledge`: improved after removing generic `поиск`.

Useful but broad labels:

- `agent_ops`: often grounded, but broad Russian stems like `агент` can make
  the label too easy to trigger.
- `ai_product_pm`: grounded for product/adoption posts, but broad terms like
  `продукт` can conflate product-market analysis, product usage, and PM craft.
- `business_adoption`: generally useful, but economics/adoption terms can catch
  broad market commentary.

Weakest labels:

- `evals_quality`: grounded when a benchmark or metric is mentioned, but it
  currently conflates model benchmark news with actual eval/quality practice.
- `security_privacy_governance`: grounded when regulation/security terms appear,
  but sometimes too broad for admission decisions.
- `general_ai_news`: now safer, but still a bucket for broad AI mentions rather
  than a reason to admit an expert.

### Depth labels

Depth labels are less reliable than coverage labels.

Main issue:

- `benchmark_or_eval` fires whenever a benchmark/metric is mentioned. This is
  grounded as a signal, but it does not prove deep eval expertise.

Current interpretation:

- Treat depth labels as advisory sort keys for manual review.
- Do not use them as proof of source quality without inspecting the post.

## Current Representativeness

| Use case | Verdict | Reason |
|---|---|---|
| Current-roster inventory | Good | Counts come from real DB rows and raw text. |
| Broad topical map | Acceptable | Coarse categories are visible and explainable. |
| Thin/gap detection | Partial | Coarse taxonomy can hide narrow gaps. |
| Per-expert passport | Useful preflight | Representative posts and matched terms are auditable. |
| Candidate admission verdict | Not enough | Needs overlap, candidate passport, and source-level query probes. |

## Current Baseline Facts

From the regenerated current coverage report:

- human experts included: `17`
- posts: `7049`
- text posts: `6622`
- post embeddings: `6622`
- FTS rows: `6622`
- experts without valid `post_metadata`: `kornish`, `pashazloy`
- no embedding gaps detected

The current coarse map still shows all major areas as `strong`, but this should
be read as broad corpus density, not as proof that every area is productively
covered.

## Remaining Risks

- Coarse categories can hide narrow gaps like coding-agent evals, agent failure
  modes, AI observability, governance for coding copilots, or human review
  workflows.
- Broad stems such as `агент`, `продукт`, `модель`, `эконом`, and `регулир`
  can inflate category counts.
- High-count experts are not necessarily the best query sources.
- News/model-release posts can look strong by keyword count while contributing
  little practical source utility.

## Recommended Next Step

Proceed to `evaluate_expert_candidate.py`, but make it depend on this calibrated
baseline:

1. Generate candidate text-only passport from Telegram Desktop JSON.
2. Compare candidate labels and matched terms against `current_coverage.json`.
3. Flag broad-news/model overlap as weak novelty by default.
4. Require representative candidate posts for every claimed novelty.
5. Defer final `accept` / `reject` to source-level query probes when the
   candidate passes cheap preflight.

Do not expand the taxonomy too much before the first candidate pass. The next
useful signal is how a real candidate behaves against this baseline.
