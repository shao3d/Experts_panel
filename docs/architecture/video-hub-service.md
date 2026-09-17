# Video Hub Sidecar: Architecture & Integration

**Status:** Stable / Production-Ready (query-time branch dormant in the UI, see "Current Operating Mode")
**Role:** Parallel pipeline for deep video transcript analysis using the "Digital Twin" approach.
**Date:** 2026-04-12 (operating-mode note 2026-09-17)

---

## Current Operating Mode (2026-09-17)

Owner decision: Video Hub is **not** part of the panel and Panex. Frontend hides it
(`HIDDEN_EXPERT_IDS = {'video_hub'}`), the orchestrator keeps video segments out of
Hybrid Retrieval, and the Agent Context API rejects `video_hub` (`501`). Search over
video segments goes through **Expert Scout** (`docs/guides/expert-scout.md`), which
returns `video_link` deep-links into YouTube.

The query-time 4-phase pipeline below still exists and remains reachable by a direct
`POST /api/v1/query` with `expert_id="video_hub"`; it is kept for a possible return
to the panel but is otherwise dormant.

---

## 🏗️ Architecture Concept (Sidecar Pattern)

The Video Hub operates as an **isolated sidecar**, running in parallel with the main Expert Pipeline and Reddit Service. This ensures that the specificity of video data (long transcripts, timestamps, conversational style) does not introduce noise into the search for concise Telegram posts.

### Core Principles for Fullness & Style:
1.  **Semantic Boundaries**: Transcripts are segmented only at logical completion points (complete arguments).
2.  **The "Author's Voice" Mandate**: The system is strictly required to reconstruct the expert's original reasoning flow, vocabulary, and rhetorical style. No dry summaries allowed.
3.  **Dual-Layer Overlap**: 15-20% physical text overlap between segments + `context_bridge` metadata for narrative continuity.
4.  **Isolation of Themes**: `topic_id` is a composite key: `hash(video_url) + topic_slug`. This ensures narrative continuity within a single video.
5.  **Differential Retrieval (Narrative Logic)**:
    - **HIGH Relevance**: Fetch **Full Content**. These are the "meat" of the answer.
    - **MEDIUM Relevance**: Fetch **Summary only**. These act as "narrative bridges" to maintain the flow between HIGH segments.
    - **LOW Relevance**: Discard entirely.

---

## 🛠️ Phase 1: Data Preparation (Smart Segmenting)

Segmentation is produced by the **automated ingest pipeline** (stage 1 script + an LLM pass, see "Automated Ingest Pipeline" below). The legacy manual pass through Google AI Studio still works and uses the same output contract.

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

### Keyframe Criteria ("On-Screen Moments")

On-screen moments are captured per segment as `[НА ЭКРАНЕ: ...]` markers, with `timestamp_seconds` set to the second the frame appears (not the segment start). A moment counts as key when readable text (prompt/title/metric), a UI/settings panel or modal, a table/chart/code/formula, a generation result, a before/after, or an action/notification appears. Cadence is ≈1 keyframe per ~15s with recall-bias (capture when in doubt); partially unreadable text is tagged `[НА ЭКРАНЕ (неуверенно): ...]`. Adapted from `kdoronin/video_analyzer` (MIT).

### Extended Segment Schema (Automated Ingest)

The automated pipeline optionally adds two blocks to a segment:

```json
{
  "segment_id": 1006,
  "topic_id": "sound_crime_robbery",
  "title": "Segment Title",
  "summary": "Russian summary (RU) used by the Map phase and lexical search",
  "content": "Original speech, verbatim",
  "timestamp_seconds": 258,
  "visual": {
    "kind": "prompt_panel",
    "app": "Higgsfield",
    "model": "Seedance 2.5",
    "settings": "30s / 16:9 / 720p / Bitrate High",
    "showcase_prompt_verbatim": "A 30-second landscape 16:9 cinematic crime-action sequence..."
  },
  "frames": [
    {"time_s": 260.0, "path": "/abs/path/c01f_00002600.jpg"}
  ]
}
```

- `visual` is stored in `media_metadata.visual` and **also appended to `message_text` as a `VISUAL:` block**, so FTS5, vector search and the synthesis context all see prompts/settings/slides. Retrieval indexes `message_text` only, hence the duplication. Unknown scalar keys (e.g. `seed`, `negative_prompt`) are rendered into the block too; container values stay in `media_metadata.visual` only.
- `frames` are copied to `backend/data/video_frames/<video_hash>/` and recorded in `media_metadata.frames` as `{time_s, file}`. Frames are a stage-2 working artifact: `backend/data/` and the frame directory are gitignored and **not** shipped with the DB promotion, so in production `media_metadata.frames` are inert metadata (the UI uses YouTube deep-links, not local files).
- `video_metadata.published_at` (optional) drives `created_at`, so freshness reflects the video date instead of the import date.
- `import_video_json.py` upserts by `telegram_message_id` (row identity preserved), so re-imports do not orphan embeddings. When `message_text` changes, stale `post_embeddings`/`vec_posts` rows are dropped so the next `embed_posts.py` run regenerates them.
- **Video identity is canonical**: every YouTube URL form (`youtu.be/ID`, `shorts/`, `embed/`, `live/`, `watch?v=ID` with extra params) is canonicalized to `https://www.youtube.com/watch?v=ID` before deriving virtual IDs and topic hashes, so the same video cannot be imported twice under different URLs.
- **`segment_id` must be unique across the whole video** (chunk numbering is continuous). `--combine` fails loudly on duplicates instead of silently overwriting segments; `import_video_json.py` fails on duplicate virtual IDs inside one JSON.
- **Re-segmentation:** `import_video_json.py --replace-video` deletes all existing segments of the same video (matched by canonical URL) together with their embeddings before importing the new segmentation. Without the flag, changed `segment_id` values leave old rows in place.
- A reused transcript (`--transcript`) and the ASR output are validated for the ASR schema (`{start: <seconds>, end: <seconds>, text: <str>}`); a foreign format fails the ingest instead of producing empty transcript slices.

### Automated Ingest Pipeline

Three steps, dev-safe (no production writes):

1. **Stage 1 — `backend/scripts/ingest_video.py`**: media probe → audio → ASR (`backend/scripts/asr_whisper.py`, faster-whisper int8, glossary-biased, auto language) → chunked processing (`--chunk-minutes`, overlap) → per-chunk coarse grid, contact sheets, per-second change curve (numpy), speech-cue windows, adaptive dense frames with dedup and hard caps (`--max-windows-per-chunk`, `--max-dense-frames-per-chunk`) → artifacts under `chunks/chunk_NN/`.
2. **Stage 2 — LLM pass**: one chunk at a time; the model reads the transcript slice plus sheets/native frames and writes `chunks/chunk_NN/segments.json`. Disk is the memory, so long videos never load more than one chunk into context. `segment_id` must continue across chunks (no restart from 1001 per chunk).
3. **Combine, import, embed**: `ingest_video.py --combine` merges chunk JSONs (dedup by topic + time inside overlaps, chunk-local metadata stripped) into `segments.json` and fails on duplicate `segment_id`; `import_video_json.py` writes to the DB (`--replace-video` for re-segmentation); `embed_posts.py` adds vectors.

**YouTube download constraint**: the VM datacenter IP is blocked by YouTube, so media is fetched on the Mac over the reverse SSH tunnel (see `docs/guides/video-hub-operator.md`) and copied to the VM before stage 1.

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
-   **Model**: `gemini-3.1-pro-preview` (Config: `MODEL_VIDEO_PRO`).
-   **Persona**: "Expert's Digital Twin".
-   **Instruction**: "Reconstruct the expert's original reasoning flow and vocabulary. Use [FULL TRANSCRIPT] for details and [SUMMARY] to bridge the gaps."
-   **Language**: The synthesis prompt requires output in the detected query language (Russian by default, English for English queries) — generating in the right language up front avoids a second, style-losing translation pass.
-   **Visual Elements (`[НА ЭКРАНЕ]`)**: The synthesis prompt splits on-screen markers into two cases. **Ambient** context (speaker, browser, generic slide) is woven organically into the narrative rather than mechanically quoted. **Informational** payload (prompt text, model/generation settings, code, formulas, exact figures, slide titles) is preserved and surfaced verbatim — prompts quoted, settings as a short list — never paraphrased, translated, rounded, or hidden. Unreadable on-screen text is reported as unreadable instead of guessed.
-   **Citations**: MANDATORY `[post:ID]` format for deep-links. **All** segments provided in the context (both HIGH and MEDIUM) are included in the `main_sources` list, ensuring every cited link is clickable on the frontend.
-   **Output Token Limit**: `max_tokens=8192` — increased from 4096 to prevent truncation on videos with 50+ segments (where the "DO NOT SUMMARIZE" instruction produces long outputs with many citations).

### 4. Style-Preserving Validation/Translation
-   **Service**: Shared `TranslationService` singleton (Model: `google/gemini-3.1-flash-lite`, Config: `MODEL_ANALYSIS`); results come from the persistent translation cache.
-   **Task**: Safety net after synthesis — if the answer language does not match the query language (either direction), the answer is translated. With language-aware synthesis (Phase 3) this rarely triggers.

---

## 🏗️ Technical Constraints & Safety
-   **ID Limits**: Virtual `telegram_message_id` for video segments can reach up to **1,000,000,000** (hashed MD5). Backend validation is increased to support this.
-   **Storage**: Video segments are stored in the same `posts` table but isolated by `expert_id="video_hub"`.

---

## 🖥️ Phase 3: SSE & UI Integration

### Streaming (SSE):
-   **Service Events**: `VideoHubService` emits the generic service phases `map`, `resolve`, `reduce`, `language_validation`.
-   **Tracker Remap**: `PipelineStateTracker` remaps those events into dedicated aggregate states:
    -   `map` -> `video_map`
    -   `resolve` -> `video_resolve`
    -   `reduce` -> `video_synthesis`
    -   `language_validation` -> `video_validation`
-   **Frontend Rendering**: `ProgressSection` renders these remapped states as a separate **Video** group in the global progress bar.
-   **Human Messages**: SSE text keeps the `🎥` prefix (e.g., "🎥 Synthesizing digital twin response...") to distinguish video operations.

### UI Integration:
-   **Expert ID**: `video_hub` (Mapped to "Video_Hub" in `expertConfig.ts`); listed in `HIDDEN_EXPERT_IDS`, so the expert never appears in the panel selection and the "Knowledge Hub" group collapses away.
-   **Visuals**: Uses 🎥 icon and specialized `PostCard` rendering for YouTube links with `?t=`/`&t=` parameters.
-   **Display Order**: Video Hub appears **after all regular experts** but **before Reddit Community Insights** (last in `EXPERT_UI_CONFIG.order`); dormant while hidden.
-   **Roster Boundary**: `video_hub` is a synthetic expert for video segments. It is not part of Telegram sync, and its original video authors must not be treated as active Telegram experts unless they also exist in `expert_metadata` and `expertConfig.ts`.

---

## ⚙️ Model Configuration (Env Vars)

| Phase | Variable | Working Model (Feb 2026) |
|-------|----------|-------------------|
| Video Map | `MODEL_MAP` | `gemini-2.5-flash-lite` |
| Video Synthesis | `MODEL_VIDEO_PRO` | `gemini-3.1-pro-preview` |
| Video Validation | *none (reuses `LanguageValidationService`)* | `MODEL_ANALYSIS` (`google/gemini-3.1-flash-lite`) |

`MODEL_VIDEO_FLASH` still exists in `config.py`/`.env.example` but is not read by any runtime code; the validation phase has always run through `LanguageValidationService`.
