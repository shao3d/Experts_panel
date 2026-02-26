# Pipeline Architecture Guide

**The Single Source of Truth** for the Experts Panel 8-phase pipeline.
*Last Verified against Codebase: 2026-02-16*

## 🏗️ High-Level Overview

The system processes user queries through an **eight-phase pipeline** using a **Gemini-only** strategy. It features parallel expert processing, differential context expansion, a dedicated side-pipeline for Reddit analysis, and a specialized **Video Hub Sidecar** for video transcript analysis.

### Core Principles
1.  **Multi-Expert Isolation**: Each expert is processed independently (Map -> Reduce).
2.  **Differential Processing**: HIGH relevance posts get deeper context (Resolve) than MEDIUM posts.
3.  **Cost Optimization**: Uses `Gemini 2.5 Flash Lite` for heavy lifting (Map) and `Gemini 3 Flash Preview` for intelligence (Reduce).
4.  **Date Filtering**: Optional "Recent Only" mode (last 3 months).
5.  **Reddit-Only Mode**: Ability to bypass expert analysis entirely for broad community searches.
6.  **Parallel Multi-Stream**: Telegram Experts, Reddit Community, and Video Hub Insights run in parallel for maximum recall.

---

## 🔄 Phase-by-Phase Detail

### 1. Map Phase (Relevance Scoring)
**Goal**: Identify relevant posts from the expert's history.
- **Service**: `MapService` (`backend/src/services/map_service.py`)
- **Model**: `gemini-2.5-flash-lite` (Config: `MODEL_MAP`)
- **Input**: All posts for expert (or filtered by date).
- **Chunking**: **100 posts** per chunk.
- **Concurrency**: Dynamic, up to `MAP_MAX_PARALLEL` (Default: 25).
- **Retry Logic (3-Layer Protection)**:
    1.  **Client-Level Retry (Tenacity)**: `AsyncRetrying` with jitter (5 attempts, max ~15s). Handles TPM spikes and network glitches. Only retries rate limit/timeout errors (Auth/BadRequest fail immediately).
    2.  **Service-Level Retry (Tenacity Decorator)**: Up to 3 retries with exponential backoff for JSON/network errors.
    3.  **Global Chunk Retry**: Pipeline re-queues failed chunks once after 45s cooldown (crosses RPM window boundary).
- **Output**: List of posts marked `HIGH`, `MEDIUM`, or `LOW`.

### 2. Medium Scoring Phase (Hybrid Reranking)
**Goal**: Rescue valuable content from "MEDIUM" purgatory without overwhelming the context window.
- **Service**: `MediumScoringService` (`backend/src/services/medium_scoring_service.py`)
- **Model**: `gemini-2.0-flash` (Config: `MODEL_MEDIUM_SCORING`)
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
- **Model**: `gemini-2.0-flash` (Config: `MODEL_ANALYSIS`)
- **Logic**: If Query is EN and Response is RU -> Translate to EN (preserving formatting).

### 6. Comment Groups Phase
**Goal**: Find relevant discussions in comments.
- **Service**: `CommentGroupMapService` (`backend/src/services/comment_group_map_service.py`)
- **Model**: `gemini-2.0-flash` (Config: `MODEL_COMMENT_GROUPS`)
- **Sources (Priority Order)**:
    1.  **Author Clarifications**: Expert's own comments on Main Source posts (Bypass LLM, `HIGH` relevance).
    2.  **Community on Main Sources**: Community comments on Main Source posts (Bypass LLM, `HIGH` relevance).
    3.  **Drift Groups**: Topic-drift discussions from other posts (Filtered by LLM).

### 7. Comment Synthesis Phase
**Goal**: Extract unique insights from comments.
- **Service**: `CommentSynthesisService` (`backend/src/services/comment_synthesis_service.py`)
- **Model**: `gemini-3-flash-preview` (Config: `MODEL_SYNTHESIS`)
- **Output Structure (4 Sections)**:
    1.  **Notes from the expert** (Author clarifications)
    2.  **Notes from community** (On main sources)
    3.  **Additional comments from the expert** (From drift groups)
    4.  **Community opinions** (From drift groups)
- **Localization**: Section titles adapt to query language (RU/EN).

### 8. Reddit Pipeline (Parallel Sidecar)
**Goal**: Provide community reality-check and engineering insights.
- **Service**: `RedditEnhancedService` (`backend/src/services/reddit_enhanced_service.py`)
- **Architecture**: **Hybrid Sidecar Pattern**.
    - **Search**: Uses MCP (`reddit-mcp-buddy`) via Proxy for smart discovery.
    - **Deep Dive**: Uses **Direct Reddit API (OAuth)** via Proxy to bypass MCP pagination limits and fetch full trees.
- **UX Integration**: Internal Reddit phases (`scout`, `search`, `reranking`, `synthesis`) are dynamically mapped to standard frontend phases (`map`, `resolve`, `reduce`) to animate the global UI progress bar, accented with a 🌐 icon.

#### Phase 1: Search & Scout
- **Query Translation & Formulation**:
    - **Model**: `gemini-3-flash-preview` (Upgraded from 2.0 Flash).
    - **Logic**: Analyzes user intent to distinguish between **Building AI** (Architecture/RAG) and **Using AI** (Workflow/Coding).
    - **Anti-Hallucination**: Strictly forbids architecture terms (Vector DB, RAG) for workflow queries (e.g., "docs for Copilot").
- **AI Scout v3 (Temporal & Intent Aware)**:
    - **Model**: `Gemini 3 Flash Preview`.
    - **Capabilities**:
        - **Temporal Awareness**: Detects "Fast-moving" topics (AI, News -> `time="month"`) vs "Evergreen" (Theory -> `time="all"`).
        - **Intent Classification**: Identifies if user needs "How-to", "Comparison", or "Troubleshooting".
    - **Strategies**:
        1.  `Targeted`: Combined search in specific subreddits (OR logic).
        2.  `AI Intent`: Specific queries generated by LLM.
        3.  `Sniper`: "Guide", "Tutorial", "Benchmark" markers.
        4.  `Timeless Classic`: `time="all"` search for "Bible/Best Practice" threads.

#### Phase 2: Deduplication & Cleanup
- **Smart Deduplication**: Filters duplicates by normalized URL and fuzzy title match.
- **Goal**: Prevent same content from appearing multiple times (e.g. cross-posts).

#### Phase 3: AI Reranking (The Brain)
- **Model**: `Gemini 3 Flash Preview` (Config: `MODEL_SYNTHESIS`).
- **Logic**:
    - Takes top **40** candidates from heuristic sort.
    - AI assesses semantic relevance on 0.0-1.0 scale.
    - **Final Score**: `80% AI Relevance + 20% Engagement`.
    - **Benefit**: Filters out viral but irrelevant memes/clickbait.

#### Phase 4: Deep Drill & Synthesis
- **Deep Drill Capabilities (+500% Data)**:
    - **Scope**: Top **15** posts (after AI Reranking).
    - **Depth**: **100 comments** per post, **Depth 5**.
- **Synthesis Strategy ("Staff Engineer Persona")**:
    - **Role**: "Staff Engineer analyzing for a colleague".
    - **Features**:
        - **Hidden Gems**: Digs for specific configs/flags in deep comments.
        - **Minority Report**: Explicitly highlights competent dissenting opinions.
        - **Pivot Alert**: Detects "Consensus Shift" (e.g., "Airflow -> Dagster").
        - **Comparison Tables**: Mandatory for "vs" queries.
- **Execution**: Runs in parallel with Expert Pipeline.
    - **Timeout**: **120 seconds**.

### 9. Video Hub Sidecar (Digital Twin)
**Goal**: Analyze long-form video content without losing narrative context.
- **Service**: `VideoHubService` (`backend/src/services/video_hub_service.py`)
- **Expert ID**: `video_hub` (Aggregate expert).
- **Architecture**: **Parent-Child Indexing with Summary Bridging**.
- **UX Integration**: Emits UI progress events mapped to standard phases (`map`, `resolve`, `reduce`) with a 🎥 icon for visual distinction.

#### Phase 1: Segment Map
- **Model**: `gemini-2.5-flash-lite`.
- **Unit**: Individual video segments (~2-5 mins).
- **Scoring**: Identifies `HIGH` relevance segments based on query.

#### Phase 2: Resolve (Summary Bridging)
**The Core Innovation**: Solves the "Lost Middle" problem.
- **Logic**:
    - **HIGH Segments**: Loaded as **Full Transcript** (Parent).
    - **Topic Neighbors**: If a segment is `HIGH`, all other segments with the same `topic_id` are loaded as **Summaries** (Child).
- **Result**: The LLM sees a continuous narrative where key moments are detailed, and gaps are bridged by summaries.
- **Requirement**: `topic_id` must change every 10-15 minutes (logical chapters).

#### Phase 3: Synthesis (Digital Twin)
- **Model**: `gemini-3.0-pro` (High reasoning).
- **Persona**: "Expert's Digital Twin".
- **Instruction**: "Do not summarize. Reconstruct the expert's reasoning flow using the transcripts."
- **Visual Elements Context**: Intelligently extracts meaning from screen metadata (e.g., `[НА ЭКРАНЕ: ...]`) and **organically weaves** it into the narrative as if spoken by the expert, completely hiding the technical markers from the user.
- **Citations**: ALL segments passed into the context (both HIGH and MEDIUM) are registered in `main_sources`, ensuring every `[post:ID]` reference generated by the model is clickable and highlights the exact video segment in the UI.

#### Phase 4: Validation
- **Model**: `gemini-3.0-flash`.
- **Goal**: Ensure style consistency and language matching.

---

## 📊 Model Configuration (Env Vars)

| Phase | Variable | Default Model | Rationale |
|-------|----------|---------------|-----------|
| Map | `MODEL_MAP` | `gemini-2.5-flash-lite` | Best instruction following for classification. |
| Reduce | `MODEL_SYNTHESIS` | `gemini-3-flash-preview` | Best reasoning for synthesis. |
| Scoring | `MODEL_MEDIUM_SCORING` | `gemini-2.0-flash` | Fast, accurate scoring. |
| Comments | `MODEL_COMMENT_GROUPS` | `gemini-2.0-flash` | Fast group analysis. |
| Validation | `MODEL_ANALYSIS` | `gemini-2.0-flash` | Fast translation/check. |
| Drift (Offline) | `MODEL_DRIFT_ANALYSIS` | `gemini-3-flash-preview` | Deep offline analysis. |

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