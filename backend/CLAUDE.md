# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and Reddit integration.

## Narrative Summary
The backend implements a sophisticated 10-phase query processing system. It uses a **Gemini-only** strategy through **OpenRouter**. `vertex_llm_client.py` is retained as an import-compatibility filename, but its canonical runtime client is OpenRouter.

## Key Files & Responsibilities

### Core Pipeline Services
| Service | Phase | Model (Default) | Responsibility |
|---------|-------|-----------------|----------------|
| `ai_scout_service.py` | **0. Scout** | `google/gemini-3.1-flash-lite` | Generates FTS5 MATCH queries (OR-only Entity Clouds). Runs **parallel** with Embedding. |
| `embedding_service.py`| **0. Embed**| `google/gemini-embedding-001` | Pre-computes query embedding once for all experts. Runs **parallel** with Scout. |
| `hybrid_retrieval_service.py` | **0. Retrieval** | *None (SQLite)* | Embs&Keys Hybrid Search (Vector KNN + FTS5 + RRF). Freshness from SQL directly (no extra DB query). |
| `fts5_retrieval_service.py` | **Internal** | *None* | Provides FTS5 query sanitization utils used by Hybrid Service. |
| `map_service.py` | **1. Map** | `gemini-2.5-flash-lite` | Chunks posts (50), scores relevance (HIGH/MEDIUM/LOW). 3-layer retry system. |
| `medium_scoring_service.py` | **2. Score** | `google/gemini-3.1-flash-lite` | Reranks MEDIUM posts. Keeps top 5 with score ≥ 0.7. |
| `simple_resolve_service.py` | **3. Resolve** | *None (DB)* | Expands HIGH posts context (Depth 1). Bypassed for Medium posts. |
| `reduce_service.py` | **4. Reduce** | `gemini-3-flash-preview` | Synthesizes final answer. Max 50 posts context. Validates references. |
| `language_validation_service.py` | **5. Validate** | `google/gemini-3.1-flash-lite` | Ensures response language matches query (RU/EN). |
| `comment_group_map_service.py` | **6. Comments** | `google/gemini-3.1-flash-lite` | Drift scoring runs **parallel** with Reduce. `score_drift_groups()` + `merge_with_main_sources()`. |
| `comment_synthesis_service.py` | **7. Synthesis** | `gemini-3-flash-preview` | Extracts insights into 4 sections (Expert/Community). Runs after Reduce + Drift complete. |
| `video_hub_service.py` | **Video Sidecar** | `gemini-3.1-pro-preview` | **Digital Twin**. 4-phase video analysis (Map -> Resolve -> Synthesis -> Validation). |
| `reddit_enhanced_service.py` | **8. Reddit** | DeepSeek V4.1 Flash via local `dsh` (`REDDIT_LLM_BACKEND`, default `dsh`) + HTTP Proxy | **Sidecar Orchestrator**. Reddit Search V2 runs precision-first candidate generation, early comment enrichment, and answerability-first reranking. |
| `reddit_synthesis_service.py` | **Synthesis** | `dsh` (default) \| `gemini` \| `opencode` (`REDDIT_SYNTH_BACKEND`) | **Staff Engineer Persona**. Finds Hidden Gems & Minority Reports. No Fluff. |
| `meta_synthesis_service.py` | **Meta-Synthesis** | `gemini-3-flash-preview` | Cross-expert unified analysis. Runs parallel with Reddit after all experts complete (≥2). |

### Infrastructure
- `src/api/simplified_query_endpoint.py`: **Main Orchestrator**. Manages parallel expert tasks, SSE streaming with `pipeline_state` tracking, and Reddit Sidecar (120s timeout).
- `src/api/pipeline_state_tracker.py`: **Pipeline State Tracker**. Tracks aggregate phase statuses across all experts (per-expert + cross-cutting). Monotonic priority: pending→active→error/skipped→completed.
- `src/config.py`: **Configuration Hub**. Reads all env vars.
- `src/services/vertex_llm_client.py`: **Canonical OpenRouter LLM Client** (legacy filename). Handles retries, provider capability routing, and rate limits.
- `src/services/google_ai_studio_client.py`: Compatibility shim for legacy imports.
- `src/utils/error_handler.py`: **Error System**. Maps exceptions to user-friendly messages.

## API Endpoints
- `POST /api/v1/query`: Main streaming endpoint.
- `GET /api/v1/experts`: List experts.
- `GET /health`: Cheap cached health diagnostics.
- `GET /health/live`: Forced live diagnostics (admin-protected via `X-Admin-Secret`).

## Reddit Integration
- **Active Client**: `src/services/reddit_enhanced_service.py` (Proxy Client).
- **LLM engine**: все Reddit-роли (формулировка, Scout-план, answerability-судья, reflection, синтез) идут через **DeepSeek V4.1 Flash локальным `dsh` CLI** (`src/services/dsh_client.py`, `dsh --profile headless`), выбор — `REDDIT_LLM_BACKEND` (default `dsh`). Tool-free оверлей профиля: `backend/deploy/dsh/reddit-llm.patch.yml`. Автофолбэка между движками нет: сбой `dsh` — деградация. OpenRouter/Gemini остаётся только для отката (`REDDIT_LLM_BACKEND=gemini`). Контейнер панели везёт `dsh` с собой: `Dockerfile` (`ARG DSH_VERSION`, npm-пакет `@deepseek-ai/dsh`) плюс профиль `headless` из `backend/deploy/dsh/profile-headless/`; ключ приходит переменной `COMMANDCODE_API_KEY`. Предусловие и проверка после релиза — `docs/operations.md`, раздел про движок `dsh`.
- **Synthesis backends**: `reddit_synthesis_service.py` dispatches on `REDDIT_SYNTH_BACKEND` - `dsh` (default, DeepSeek через локальный CLI), `gemini` (OpenRouter, откат), или free headless opencode serve via pure-HTTP `opencode_synth_client.py` (no binary needed; works from the panel container and any host reaching the VM). opencode failures/timeouts always fall back to Gemini; `shadow` mode runs both and logs `[shadow]` telemetry without delaying the user.
- **Architecture**: Hybrid Sidecar.
    - **Search**: via Proxy `POST /search` (direct Reddit OAuth API inside the sidecar).
    - **Details**: via Proxy `POST /details` (deep fetch of 100 comments / depth 5).
- **Search V2 (Precision-First)**:
    - **Soft Subreddit Hints**: Scout still proposes target communities, but backend no longer hard-locks retrieval to them by default.
    - **Tiny Targeted Channel**: For narrow `how_to` / `troubleshooting` / `comparison` intents, backend may add a very small targeted retrieval on the strongest subreddit hints, while keeping global search active.
    - **Smaller Candidate Set**: Backend favors literal query + scout query + freshness/quality channels instead of many additive search hacks.
    - **Early Enrichment**: Top candidates fetch comments before final rerank so answer-bearing comments can influence ranking.
    - **Answerability Rerank**: the judge (DeepSeek V4.1 Flash via `dsh`) scores "does this answer the question?" rather than mere topical similarity. On rerank LLM failure (outage, provider 402) candidates fall back to heuristic scoring with a neutral AI component — ranking degrades, results never collapse to a false "nothing found".
    - **Stronger Comparison Gate**: `comparison` queries prefer direct title/body matches and explicit comparison markers instead of comment-only overlaps.
    - **Confidence Thresholds**: Low-confidence Reddit results are dropped instead of filling the UI with adjacent noise.
    - **Coverage Scope**: the synthesizer reserves `coverage=insufficient` (the canonical abstain) for a question's CENTRAL request; an unsupported secondary constraint (version, region, price, extra example) makes the answer `partial` instead, which renders the explicit "The evidence supports only a partial answer." plus "Not established by the sources:". `partial` carries up to `REDDIT_SYNTH_PARTIAL_MAX_FINDINGS` findings and never any actions.
    - **Disclosed Degradation**: `abstain_reason` (`no_verified_sources` / `insufficient_coverage` / `degraded`), `degraded` and `verified_count` are returned by the agent API; the CLI prints `kept N of M ranked candidates, all quote-verified` and `status: abstained [reason]`, so an outage is never paraphrased as "Reddit has nothing".
    - **Debug Trace**: Optional structured trace via `REDDIT_SEARCH_DEBUG=true`.
- **Logic**: 
    - **Scout as Hint, not Gate**: topic detection shapes retrieval, but global search always remains available.
    - **Precision > Recall**: Returning fewer high-confidence threads is preferred over broad but noisy recall.
- **Legacy**: `reddit_client.py` removed 2026-08-25 (dead asyncpraw client; manual/legacy scripts that imported it are non-runtime artifacts).

## Configuration (Environment Variables)

### Models
Defined in `.env`, loaded in `config.py`.
- `MODEL_MAP`: `google/gemini-2.5-flash-lite`
- `MODEL_SYNTHESIS`: `google/gemini-3-flash-preview`
- `MODEL_ANALYSIS`: `google/gemini-3.1-flash-lite`
- `MODEL_MEDIUM_SCORING`: `google/gemini-3.1-flash-lite`
- `MODEL_COMMENT_GROUPS`: `google/gemini-3.1-flash-lite`
- Drift analysis has no separate model env: engine is headless OpenCode with hardcoded `OPENCODE_MODEL` (`commandcode/z-ai/glm-5.3-flash`) in `src/services/opencode_drift_client.py`; SSOT — `docs/guides/drift-analysis.md`.
- `MODEL_SCOUT`: `google/gemini-3.1-flash-lite` (AI Scout / FTS5)
- `MODEL_META_SYNTHESIS`: `google/gemini-3-flash-preview` (Cross-expert unified analysis)
- `MODEL_EMBEDDING`: `google/gemini-embedding-001` (Hybrid Retrieval embeddings)
- `MODEL_VIDEO_PRO`: `gemini-3.1-pro-preview` (Video Hub Digital Twin)
- `MODEL_VIDEO_FLASH`: `gemini-3-flash-preview` (Video Hub validation)

### OpenRouter Runtime Notes
- Required auth: `OPENROUTER_API_KEY` (or the compatibility fallback `OPENAI_API_KEY`)
- JSON-producing calls use `provider.require_parameters=true`; providers that cannot honour the requested response format are excluded.
- The Video Hub remains out of the normal runtime health probe and is not part of this migration.
- Backend/API startup and operational CLI scripts explicitly load `backend/.env`; do not rely on the current working directory.

### Env Vars / Tunables
- `MAP_MAX_PARALLEL`: 25 (Tier 1) / 8 (Free)
- `MAP_CHUNK_SIZE`: 50
- `MAX_CONCURRENT_EXPERTS`: 5
- `MEDIUM_MAX_SELECTED_POSTS`: 5
- `MEDIUM_SCORE_THRESHOLD`: 0.7
- `MEDIUM_MAX_POSTS`: 50
- `HYBRID_VECTOR_TOP_K`: 150
- `HYBRID_FTS5_TOP_K`: 100
- `HYBRID_RRF_K`: 60
- `MAX_FTS_RESULTS`: 300
- `USE_SUPER_PASSPORT_DEFAULT`: false
- `FTS5_CIRCUIT_BREAKER_THRESHOLD`: 3
- `META_SYNTHESIS_TIMEOUT_SECONDS`: 120
- `QUERY_RESULTS_DIR`: optional durable UI query result directory
- `QUERY_RESULTS_TTL_DAYS`: 7
- `QUERY_RATE_LIMIT_ENABLED`: true — per-IP sliding-window guard on the public `POST /api/v1/query`
- `QUERY_RATE_LIMIT_PER_HOUR`: 12 — queries per client IP per hour (0 disables)
- `DAILY_QUERY_BUDGET`: 200 — global queries per UTC day on `POST /api/v1/query` (0 disables); both guards are in-process, reset on restart, and 429 responses carry `Retry-After` (`src/services/query_rate_limit_service.py`)
- `CITATION_VERIFICATION_ENABLED`: true — verify that `[post:ID]` claims are supported by the cited post text (`src/services/citation_verification_service.py`)
- `CITATION_VERIFICATION_USE_LLM`: true — batched LLM judge (MODEL_ANALYSIS) on top of the lexical layer; on failure falls back to lexical-only
- `CITATION_VERIFICATION_MAX_PAIRS`: 24 — claim/source pairs per answer in one judge call
- `CITATION_VERIFICATION_SOURCE_CHAR_CAP`: 4000 — source text chars per pair in the judge prompt
- `AGENT_CONTEXT_RESULTS_DIR`: optional backend-saved Panex artifact directory
- `AGENT_CONTEXT_RESULTS_TTL_DAYS`: 7
- `REDDIT_SEARCH_CLIENT_TOKENS`: optional comma-separated Reddit-only client tokens; authorize only `POST /api/v1/agent/reddit-search`
- `AGENT_CONTEXT_DIGEST_MAX_*`: optional `expert_digest` evidence caps; `0` means all selected evidence for count/char caps
- `AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS`: 16384
- `PANEX_ARTIFACT_DIR`: optional local Panex CLI artifact directory
- `PANEX_ARTIFACT_TTL_DAYS`: 7
- `REDDIT_SEARCH_DEBUG`: false
- `REDDIT_RERANK_CANDIDATES`: 18 (median search has ~134 unique candidates, so this cut decides what the judge can see)
- `REDDIT_RERANK_DIVERSITY_SLOTS`: 0 (reserve that many rerank slots for strategies/subreddits the heuristic top misses; 0 = plain heuristic cut)
- `REDDIT_COMPARISON_ENTITY_PAIR`: true (adds the `comparison_entity_pair` channel for `comparison` intent — the compared products as the query, e.g. "GLM-5.3 Flash DeepSeek V4.1 Flash", instead of the anchor pair "glm-5.3 v4.1 benchmark". Additive: the anchor channel keeps running. Measured 2026-10-18: 2x candidate precision, 1.7–2.2x judged selection among its own posts; roadmap 0.6, probe `scripts/reddit_comparison_entities_probe.py`)
- `REDDIT_SERPER_ENTITY_QUERY`: true (`comparison` intent sends a quoted entity pair to Serper instead of the plan query: 59% vs 36% of returned threads mention both products; empty result retries once with the plan query)
- `ARCTIC_SHIFT_ENABLED`: true — archive channel (complete per-subreddit index). Keyword search needs a subreddit, is AND-based, times out (HTTP 422) without a bounded window, and is unsupported on very active subreddits
- `ARCTIC_WINDOW_DAYS` / `ARCTIC_NARROW_WINDOW_DAYS`: 30 / 7 (bounded window, narrowed after a timeout)
- `ARCTIC_LIMIT_PER_SUB`: 12 (clamped to ≤25), `ARCTIC_MAX_REQUESTS`: 4 per search, `ARCTIC_REQUEST_PAUSE_S`: 0.5 (free service, load-dependent limits)
- `ARCTIC_MAX_SUBSCRIBERS`: 1000000 (skip keyword search on bigger subreddits; cached per process), `ARCTIC_429_MAX_WAIT_S`: 20 (honors `X-RateLimit-Reset` once)
- `REDDIT_PRE_RERANK_ENRICH_LIMIT`: 18 (aligned with RERANK_CANDIDATES; undated Serper discovery candidates are force-enriched on top)
- `REDDIT_MIN_CONFIDENCE`: 0.52
- `REDDIT_SOFT_CONFIDENCE`: 0.44
- `REDDIT_SYNTH_COMMENT_TOP_K`: 12 (top-scored comment roots per source in synthesis context)
- `REDDIT_SYNTH_SOURCE_CHAR_CAP`: 15000 (per-source char cap shared between body and comment tree)
- `REDDIT_SYNTH_MAX_TOKENS`: 4096 (synthesis output cap; finish_reason=length triggers ONE automatic retry at 2x)
- `REDDIT_REFLECTION_MIN_POSTS`: 2 (retry when the confidence filter keeps fewer posts than this; `1` restores the zero-only trigger — synthesis abstains on 32% of one-post shortlists)
- `REDDIT_SYNTH_PARTIAL_MAX_FINDINGS`: 5 (findings on the partial-coverage branch; the 600-char budget and the ban on actions stay)
- `REDDIT_SYNTH_GAP_FORCES_PARTIAL`: false (`true` restores the older "any non-empty gap downgrades coverage to partial")
- `REDDIT_LLM_BACKEND`: `dsh` (default) | `gemini` — движок всех Reddit-ролей; `gemini` оставлен только для отката
- `REDDIT_SYNTH_BACKEND`: `dsh` (default) | `gemini` | `opencode` | `auto` | `shadow` - Reddit synthesis backend
- `DSH_PATCH_PATH`: путь к tool-free оверлею профиля (в репозитории: `backend/deploy/dsh/reddit-llm.patch.yml`)
- `REDDIT_DSH_BIN` / `REDDIT_DSH_PROFILE`: `dsh` / `headless` (имена с префиксом намеренно: харнесс экспортирует `DSH_PROFILE` и `DSH_SESSION_ID` в каждый дочерний процесс, и их наследование поднимает интерактивный TUI-профиль)
- `REDDIT_DSH_TIMEOUT_S`: 90 (таймаут одного вызова dsh), `REDDIT_DSH_CONCURRENCY`: 2 (вызов = отдельный процесс)
- `OPENCODE_URL`: `http://127.0.0.1:4096` (headless opencode serve on the VM; from docker use `host.docker.internal:4096` via extra_hosts host-gateway)
- `OPENCODE_SYNTH_MODEL`: `opencode/x-preview-f-free`
- `OPENCODE_SYNTH_TIMEOUT_S`: 60 (budget before falling back to Gemini)
- `OPENCODE_SYNTH_HEADSTART_S`: 20 (`auto` mode: free model runs alone this long, then Gemini joins the race; first complete answer wins)
- `OPENCODE_SYNTH_CONCURRENCY`: 2 (serve is shared with drift workers)
- `DRIFT_BACKEND`: `opencode` (only allowed value) - drift analysis runs via headless opencode; Gemini/OpenRouter drift generation is disabled, and an unreachable serve leaves groups `pending` instead of falling back
- `OPENCODE_DRIFT_MODEL`: deprecated and not read — drift model is hardcoded as `OPENCODE_MODEL = commandcode/z-ai/glm-5.3-flash` in `src/services/opencode_drift_client.py` (versioned selection; stale env must not restore Muse/MiMo; SSOT: `docs/guides/drift-analysis.md`)
- `OPENCODE_DRIFT_BATCH_SIZE`: 12 - groups per batched opencode drift call
- `DRIFT_CONCURRENCY`: 3 - parallel opencode batch workers (serve budget shared with Reddit synthesis)
- Manual A/B check: `app/backend/manual/manual_reddit_opencode_ab.py`
- Session hygiene: synth/drift clients delete their opencode sessions on completion; daily systemd timer `opencode-janitor.timer` runs `scripts/opencode_serve_janitor.py --apply` (kills quota-retry-stuck sessions, deletes stale machine sessions)

### Hardcoded Runtime Limits
- `Reddit wait after experts`: 120s hard limit in `simplified_query_endpoint.py`
- `Reddit HTTP client timeout`: 60s default in `reddit_enhanced_service.py`

## Development
- **Run**: `./quickstart.sh`
- **Logs**: `backend/data/backend.log`
- **Ingest Video (stage 1)**: `backend/.venv/bin/python backend/scripts/ingest_video.py --video <mp4> --audio <m4a> --video-id <id> --out <dir> --chunk-minutes 5` (chunked ASR + frames + windows; no DB/LLM). `--combine` merges chunk `segments.json`.
- **ASR helper**: `python3.11 backend/scripts/asr_whisper.py <audio> --out <json> [--initial-prompt <glossary>]` (faster-whisper int8 CPU, auto language).
- **Import Video**: `python3 backend/scripts/import_video_json.py <path_to_json>` (upsert by canonical YouTube URL; supports structured `visual` + `frames` + `published_at`; `--replace-video` deletes the old segments of the same video with their embeddings before importing; duplicate virtual IDs abort)
- **Embed Fresh Posts**: `python3 backend/scripts/embed_posts.py --continuous` (run after video import so segments join vector search)
- **Run Drift Batch**: `python3 backend/run_drift_service.py` (auto-loads `backend/.env`)
- **Analyze One Drift Group**: `python3 backend/analyze_specific_drift.py <post_id>` (auto-loads `backend/.env`)
- **Eval Reddit Search V2**: `python3 backend/scripts/eval_reddit_search_v2.py`
