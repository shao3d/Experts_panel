# Pipeline Architecture Guide

**The Single Source of Truth** for the Experts Panel 10-phase pipeline.
*Last Verified against Codebase: 2026-04-21*

## 🏗️ High-Level Overview

The system processes user queries through an **ten-phase pipeline** using a **Gemini-only** strategy on **Vertex AI**. It features parallel expert processing, differential context expansion, a dedicated side-pipeline for Reddit analysis, and a specialized **Video Hub Sidecar** for video transcript analysis.

### Core Principles
1.  **Multi-Expert Isolation**: Each expert is processed independently (Map -> Reduce).
2.  **Differential Processing**: HIGH relevance posts get deeper context (Resolve) than MEDIUM posts.
3.  **Cost Optimization**: Uses `Gemini 2.5 Flash Lite` for heavy lifting (Map) and `Gemini 3 Flash Preview` for intelligence (Reduce).
4.  **Vertex Routing**: All `Gemini 3*` models are sent through the Vertex `global` endpoint; `Gemini 2.5*` and embeddings stay on the configured regional endpoint.
5.  **Date Filtering**: Optional "Recent Only" mode (last 3 months).
6.  **Reddit-Only Mode**: Ability to bypass expert analysis entirely for broad community searches.
7.  **Parallel Multi-Stream**: Telegram Experts, Reddit Community, and Video Hub Insights run in parallel for maximum recall.

---

## 🔄 Phase-by-Phase Detail

### 1. Pre-filter & Map Phase (Relevance Scoring)
**Goal**: Identify relevant posts from the expert's history.
- **Pre-filter (Hybrid Retrieval: Vector KNN + FTS5 + AI Scout v3)**: If `use_super_passport` (UI: Embs&Keys Search) is enabled, an AI Scout generates an OR-only Entity-Centric FTS5 query. The system executes both Vector KNN (using `sqlite-vec`) and FTS5 BM25 search (optimized to avoid JOINs via UNINDEXED `expert_id`/`created_at`), fusing results with Reciprocal Rank Fusion (RRF). The scout is **aligned with a strict bilingual taxonomy**.
- **Parallel Scout + Embedding**: AI Scout and Embedding run **concurrently** via `asyncio.gather`. The embedding vector (`gemini-embedding-001`) is pre-computed **once** in the orchestrator while Scout generates FTS5 queries in parallel (~600ms saved vs sequential). Both results are then passed to all experts.
- **Smart Ranking (RRF + Soft Freshness)**: FTS5 and Vector results are re-scored with a linear soft freshness decay before RRF merge. Freshness dates are returned directly from Vector/FTS5 SQL queries (no separate DB round-trip).
- **Service**: `HybridRetrievalService` (`backend/src/services/hybrid_retrieval_service.py`), `AIScoutService`, `EmbeddingService`
- **Model**: `gemini-2.5-flash-lite` (Config: `MODEL_MAP`) for mapping.
- **Input**: Hybrid candidates (or all posts if Embs&Keys Search is off/fallback triggered).
- **Chunking**: **50 posts** per chunk (`MAP_CHUNK_SIZE`). The `max_tokens` for generation is set to 4096 to prevent JSON truncation issues.
- **Concurrency**: Dynamic, up to `MAP_MAX_PARALLEL` (Default: 25) globally limited by `MAX_CONCURRENT_EXPERTS` (Default: 5).
- **Retry Logic (3-Layer Protection)**:
    1.  **Client-Level Retry (Tenacity)**: `AsyncRetrying` with jitter (5 attempts, max ~15s). Handles TPM spikes and network glitches. Only retries rate limit/timeout errors (Auth/BadRequest fail immediately).
    2.  **Service-Level Retry (Tenacity Decorator)**: Up to 3 retries with exponential backoff for JSON/network errors.
    3.  **Global Chunk Retry**: Pipeline re-queues failed chunks once after 45s cooldown (crosses RPM window boundary).
- **Output**: List of posts marked `HIGH`, `MEDIUM`, or `LOW`.

### 2. Medium Scoring Phase (Hybrid Reranking)
**Goal**: Rescue valuable content from "MEDIUM" purgatory without overwhelming the context window.
- **Service**: `MediumScoringService` (`backend/src/services/medium_scoring_service.py`)
- **Model**: `gemini-2.5-flash` (Config: `MODEL_MEDIUM_SCORING`)
- **Input**: All `MEDIUM` posts from Map phase (capped at **50** for memory safety).
- **Process**:
    1.  LLM scores each post `0.0` to `1.0` based on query.
    2.  **Filter**: Keep only score **≥ 0.7** (`MEDIUM_SCORE_THRESHOLD`).
    3.  **Select**: Keep top **5** by score (`MEDIUM_MAX_SELECTED_POSTS`).
- **Output**: List of selected Medium posts.
- **Fallback**: Returns empty list on failure (graceful degradation).

### 3. Differential Resolve Phase (Context Expansion)
**Goal**: Add context (replies, previous posts) to HIGH relevance posts.
- **Service**: `SimpleResolveService` (`backend/src/services/simple_resolve_service.py`)
- **Model**: **None** (Database only).
- **Logic**:
    - **HIGH Posts**: Fetch all linked posts (Depth 1) where post is Source or Target.
    - **Selected MEDIUM Posts**: **Bypass** Resolve phase (passed directly to Reduce).
- **Filtering**: Linked posts adhere to `use_recent_only` date filter if active.

### 4. Reduce Phase (Synthesis)
**Goal**: Synthesize the final answer using all gathered context.
- **Service**: `ReduceService` (`backend/src/services/reduce_service.py`)
- **Model**: `gemini-3-flash-preview` (Config: `MODEL_SYNTHESIS`)
- **Context Limit**: Max **50** posts.
- **Sorting Order (Stable Sort)**:
    1.  **Relevance**: `HIGH` > `MEDIUM` > `LOW` > `CONTEXT`.
    2.  **Chronology**: Newest first (within relevance groups).
    *Effect*: The LLM sees the most relevant, most recent info first.
- **Features**:
    - **Personal Style**: Mimics expert's voice (if enabled).
    - **Fact Validation**: Checks that `[post:ID]` references exist in provided context.
    - **Sanitization**: Cleans JSON escape sequences to prevent frontend crashes.

### 5. Language Validation Phase
**Goal**: Ensure response language matches query language.
- **Service**: `LanguageValidationService` (`backend/src/services/language_validation_service.py`)
- **Model**: `gemini-2.5-flash` (Config: `MODEL_ANALYSIS`)
- **Logic**: If Query is EN and Response is RU -> Translate to EN (preserving formatting).

### 6. Comment Groups Phase (Drift Scoring runs parallel with Reduce)
**Goal**: Find relevant discussions in comments.
- **Service**: `CommentGroupMapService` (`backend/src/services/comment_group_map_service.py`)
- **Model**: `gemini-2.5-flash` (Config: `MODEL_COMMENT_GROUPS`)
- **Parallel Optimization**: Drift group LLM scoring (`score_drift_groups()`) runs **concurrently** with Reduce + Language Validation via `asyncio.gather`. Only the cheap main_source comment loading (`merge_with_main_sources()`, ~5ms) waits for Reduce to provide `main_sources`. This saves 8-17 seconds per expert.
- **Sources (Priority Order)**:
    1.  **Author Clarifications**: Expert's own comments on Main Source posts (Bypass LLM, `HIGH` relevance, **no comment limit**).
    2.  **Community on Main Sources**: Community comments on Main Source posts (Bypass LLM, `HIGH` relevance, **no comment limit**).
    3.  **Drift Groups**: Topic-drift discussions from other posts (Filtered by LLM, HIGH only).

### 7. Comment Synthesis Phase
**Goal**: Extract unique insights from comments.
- **Service**: `CommentSynthesisService` (`backend/src/services/comment_synthesis_service.py`)
- **Model**: `gemini-3-flash-preview` (Config: `MODEL_SYNTHESIS`)
- **Runs after** both Reduce (needs `validated_answer`) and Drift Scoring (needs `comment_group_results`) complete.
- **Output Structure (4 Sections)**:
    1.  **Notes from the expert** (Author clarifications)
    2.  **Notes from community** (On main sources)
    3.  **Additional comments from the expert** (From drift groups)
    4.  **Community opinions** (From drift groups)
- **Localization**: Section titles adapt to query language (RU/EN).

### 8. Reddit Pipeline (Parallel Sidecar)
**Goal**: Provide community reality-check and engineering insights.
- **Dedicated Architecture Document**: [See `reddit-service.md`](./reddit-service.md) for the full Single Source of Truth (SSOT).
- **High-Level Summary**: Runs in parallel with the main pipeline. Uses an AI Scout (Gemini 3 Flash) to generate intent-based queries, searches Reddit via a dedicated Node.js Proxy, performs semantic deduplication and AI reranking, and synthesizes a "Staff Engineer" response from deep comment trees.
- **UX Integration**: The backend emits dedicated Reddit phases (`reddit_search`, `reddit_synthesis`) into `pipeline_state`. The frontend groups them into a separate **Reddit** progress group; phase labels stay icon-free, while SSE message text is prefixed with `🌐 [Reddit] ...`.

### 9. Video Hub Sidecar (Digital Twin)
**Goal**: Analyze long-form video content without losing narrative context.
- **Dedicated Architecture Document**: [See `video-hub-service.md`](./video-hub-service.md) for the full Single Source of Truth (SSOT).
- **High-Level Summary**: Uses "Summary Bridging" to solve the Lost Middle problem. Extracts highly relevant video segments as full transcripts, and neighboring segments as summaries. Synthesizes a response from the perspective of the "Expert's Digital Twin" without summarizing, but by reconstructing reasoning.
- **UX Integration**: `VideoHubService` emits generic service phases (`map`, `resolve`, `reduce`, `language_validation`), and `PipelineStateTracker` remaps them into aggregate `video_map`, `video_resolve`, `video_synthesis`, and `video_validation` states. The frontend renders them as a dedicated **Video** progress group; SSE message text keeps the `🎥` prefix.

### 10. Meta-Synthesis Phase (Cross-Expert Analysis)
**Goal**: Synthesize unified answer from all expert responses, restructuring from "per-expert" to "per-topic" axis.
- **Condition**: Runs only when ≥2 experts returned answers.
- **Service**: `MetaSynthesisService` (`backend/src/services/meta_synthesis_service.py`)
- **Model**: `gemini-3-flash-preview` (Config: `MODEL_META_SYNTHESIS`)
- **Input**: Array of ExpertResponse objects (answer text + confidence + comment_insights).
- **Output**: Markdown string with: Direct Answer, Key Recommendations, Disagreements, Unique Insights.
- **Language**: Matches query language via `prepare_prompt_with_language_instruction`.
- **Fail-Safe**: Returns None on error — individual expert answers still displayed normally.
- **Parallelism**: Launched as `asyncio.create_task()` right after expert collection, runs IN PARALLEL with Reddit wait. Awaited after Reddit completes (typically already done by then).
- **Timeout**: 30s hard limit; if exceeded, cancelled gracefully.
- **UX Integration**: Displayed as "Сводный анализ" / "Cross-Expert Analysis" collapsible section ABOVE individual expert accordions.

---

## 📊 Model Configuration (Env Vars)

| Phase | Variable | Default Model | Rationale |
|-------|----------|---------------|-----------|
| Map | `MODEL_MAP` | `gemini-2.5-flash-lite` | Best instruction following for classification. |
| Reduce | `MODEL_SYNTHESIS` | `gemini-3-flash-preview` | Best reasoning for synthesis. |
| Scoring | `MODEL_MEDIUM_SCORING` | `gemini-2.5-flash` | Project-compatible replacement for historical `2.0-flash`. |
| Comments | `MODEL_COMMENT_GROUPS` | `gemini-2.5-flash` | Project-compatible replacement for historical `2.0-flash`. |
| Validation | `MODEL_ANALYSIS` | `gemini-2.5-flash` | Project-compatible replacement for historical `2.0-flash`. |
| Drift (Offline) | `MODEL_DRIFT_ANALYSIS` | `gemini-3-flash-preview` | Deep offline analysis. |
| AI Scout | `MODEL_SCOUT` | `gemini-3.1-flash-lite-preview` | Entity-centric FTS5 query expansion. |
| Meta-Synthesis | `MODEL_META_SYNTHESIS` | `gemini-3-flash-preview` | Cross-expert unified analysis (≥2 experts). |
| Embedding | `MODEL_EMBEDDING` | `gemini-embedding-001` | Pre-computed in Orchestrator for Vector KNN search. |

### Vertex Compatibility Notes
- Historical target models were preserved as much as possible during the Vertex migration.
- `gemini-3-flash-preview` and `gemini-3.1-flash-lite-preview` are active in production and require the Vertex `global` endpoint.
- `gemini-2.0-flash` is not exposed to the current GCP project, so `gemini-2.5-flash` is used in the three phases that previously depended on `2.0-flash`.
- `gemini-3-pro-preview` is replaced by `gemini-3.1-pro-preview` for Video Hub synthesis.

## 🛠️ Data Flow & Filtering

### Date Filtering (`use_recent_only`)
When enabled (UI checkbox):
1.  **Map**: Only loads posts from last 3 months.
2.  **Resolve**: Only follows links to posts from last 3 months.
3.  **Comments**: Only analyzes drift groups from last 3 months.

### Expert Isolation
All database queries are strictly filtered by `expert_id`. No data leakage between experts.

### Reddit-Only Execution Path
If no experts are selected but "Search Reddit" is enabled:
1.  **Pipeline Bypass**: Phases 1-7 (Map, Resolve, Reduce) are skipped entirely.
2.  **Reddit Execution**: Only Phase 8 (Reddit Sidecar) is executed.
3.  **Response**: Returns valid JSON with empty `expert_responses` list and populated `reddit_response`.
4.  **UI Handling**: Frontend displays "Community Insights" section while hiding empty expert placeholders.

### Resilience & Error Handling
- **Rate Limits**: The unified `google_ai_studio_client` handles `429 Too Many Requests` using exponential backoff and jitter (Tenacity).
- **Safety Filters (HARM_CATEGORY)**: If a model generation is blocked by safety filters (e.g., `finish_reason: SAFETY` on Reddit content), the system intercepts the empty response body to prevent leaking internal protobuf structures (`AsyncGenerateContentResponse`) to the UI. Instead, it gracefully degrades and returns a user-friendly error string explaining that safety filters were triggered.
