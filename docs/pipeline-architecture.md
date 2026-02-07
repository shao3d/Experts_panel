# Pipeline Architecture Guide

**The Single Source of Truth** for the Experts Panel 8-phase pipeline.
*Last Verified against Codebase: 2026-02-07*

## 🏗️ High-Level Overview

The system processes user queries through an **eight-phase pipeline** using a **Gemini-only** strategy. It features parallel expert processing, differential context expansion, and a dedicated side-pipeline for Reddit analysis.

### Core Principles
1.  **Multi-Expert Isolation**: Each expert is processed independently (Map -> Reduce).
2.  **Differential Processing**: HIGH relevance posts get deeper context (Resolve) than MEDIUM posts.
3.  **Cost Optimization**: Uses `Gemini 2.5 Flash Lite` for heavy lifting (Map) and `Gemini 3 Flash Preview` for intelligence (Reduce).
4.  **Date Filtering**: Optional "Recent Only" mode (last 3 months).

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
    1.  **Internal Rate Limit Handle**: If 429/Quota -> Sleep 65s -> Retry once.
    2.  **Tenacity Decorator**: Up to 3 retries with exponential backoff for network/JSON errors.
    3.  **Global Chunk Retry**: Pipeline re-queues failed chunks once after main execution.
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
- **Architecture**: Sidecar Pattern.
    - **Backend**: Calls `experts-reddit-proxy` microservice (HTTP).
    - **Proxy**: Uses MCP (`reddit-mcp-buddy`) to safely scrape Reddit.
- **Deep Analysis Capabilities (New in Round 3)**:
    - **Comment Trees**: Fetches nested discussions (Depth 3) to capture debates (Argument -> Counter-argument).
    - **Volume**: Analyzes top 50 comments per post (vs 25 flat previously).
    - **Context Window**: Synthesis limit increased to **15,000 chars** per post.
- **Synthesis Strategy ("Inverted Pyramid")**:
    - **Format**: Starts with Direct Solution -> Technical Details -> Nuance & Debate -> Edge Cases.
    - **Freshness**: Injects `Current Date` into prompt to penalize outdated info (e.g., distinguishing 2024 vs 2026 advice).
    - **Critical Filter**: Explicitly instructed to filter sarcasm ("Llama 5 released") and unverified rumors.
- **Execution**: Runs in parallel with Expert Pipeline.

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