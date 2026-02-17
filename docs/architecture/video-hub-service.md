# Video Hub Sidecar: Architecture & Integration

**Status:** Stable / Production-Ready
**Role:** Parallel pipeline for deep video transcript analysis using the "Digital Twin" approach.
**Date:** 2026-02-16

---

## 🏗️ Architecture Concept (Sidecar Pattern)

The Video Hub operates as an **isolated sidecar**, running in parallel with the main Expert Pipeline and Reddit Service. This ensures that the specificity of video data (long transcripts, timestamps, conversational style) does not introduce noise into the search for concise Telegram posts.

### Core Principles for Fullness & Style:
1.  **Semantic Boundaries**: Transcripts are segmented only at logical completion points (complete arguments).
2.  **The "Author's Voice" Mandate**: The system is strictly required to reconstruct the expert's original reasoning flow, vocabulary, and rhetorical style.
3.  **Dual-Layer Overlap**: 15-20% physical text overlap between segments + `context_bridge` metadata for narrative continuity.
4.  **Isolation of Themes**: `topic_id` is a composite key: `hash(video_url) + topic_slug`. This ensures narrative continuity within a single video.
5.  **Differential Retrieval (Narrative Logic)**:
    - **HIGH Relevance**: Fetch **Full Content**. These are the "meat" of the answer.
    - **MEDIUM Relevance**: Fetch **Summary only**. These act as "narrative bridges" to maintain the flow between HIGH segments.
    - **LOW Relevance**: Discard entirely.

---

## 🛠️ Phase 1: Data Preparation (Smart Segmenting)

Transcripts undergo pre-processing via **Gemini 3.0 Pro (Structured Output)** before ingestion into the `posts` table.

### Data Schema (The "Fullness" Contract):
```json
{
  "video_metadata": {
    "title": "Video Title",
    "url": "https://youtube.com/watch?v=...",
    "author": "Expert Name",
    "channel_id": "video_hub_internal" 
  },
  "segments": [
    {
      "segment_id": 1001, 
      "topic_id": "topic_slug", 
      "title": "Segment Title",
      "summary": "Concise semantic summary for Map phase",
      "content": "Full, unedited transcript text for Synthesis phase",
      "timestamp_seconds": 312,
      "context_bridge": "Logical link to previous/next context"
    }
  ]
}
```

---

## 🔄 Phase 2: Video Pipeline Logic (The 4-Phase Flow)

The Video Hub runs as a dedicated stream in `event_generator_parallel`.

### 1. Video Map (Classification)
-   **Model**: `gemini-2.5-flash-lite` (Config: `MODEL_MAP`).
-   **Task**: Scans `title` + `summary` to find relevant segments. It scores each segment individually as `HIGH`, `MEDIUM`, or `LOW`.
-   **Optimization**: Strictly ignores full content during mapping to save tokens.

### 2. Video Resolve (Semantic Context Expansion)
-   **Model**: **None (SQL Only)**.
-   **Task**: 
    1. Identifies "Winning Threads" (all `topic_id`s containing at least one `HIGH` segment).
    2. Fetches **Full Content** for all `HIGH` segments in those threads.
    3. Fetches **Summary only** for all `MEDIUM` segments in those threads.
-   **Goal**: To reconstruct the full arc of the expert's thought, even if scattered.

### 3. Video Synthesis (The Digital Twin)
-   **Model**: `gemini-3.0-pro` (The "Frontier Beast").
-   **Persona**: "Expert's Digital Twin".
-   **Instruction**: "Synthesize a full-text response in the expert's original style. Use [FULL TRANSCRIPT] for details and [SUMMARY] to bridge the gaps. Maintain specific metaphors and technical depth."
-   **Citations**: MANDATORY `[post:ID]` format for deep-links.

### 4. Style-Preserving Validation/Translation
-   **Model**: `gemini-3.0-flash`.
-   **Task**: Ensures response language matches user query (RU/EN).
-   **Specialty**: Preserves metaphors and 'vibe' during translation using transcript-derived glossary.

---

## 🖥️ Phase 3: SSE & UI Integration

### Streaming (SSE):
-   Events: `video_map`, `video_resolve`, `video_synthesis`, `video_validation`.

### UI Integration:
-   **Expert ID**: `video_hub` (Mapped to "Video_Hub" in `expertConfig.ts`).
-   **Visuals**: Uses 🎥 icon and specialized `PostCard` rendering for YouTube links with `&t=XXXs` parameters.
-   **Group**: Lives in "Knowledge Hub" expert group.

---

## ⚙️ Model Configuration (Env Vars)

| Phase | Variable | Recommended Model |
|-------|----------|-------------------|
| Video Map | `MODEL_MAP` | `gemini-2.5-flash-lite` |
| Video Synthesis | `MODEL_VIDEO_PRO` | `gemini-1.5-pro` |
| Video Validation | `MODEL_VIDEO_FLASH` | `gemini-2.0-flash` |
