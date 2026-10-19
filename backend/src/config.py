"""Centralized runtime configuration for the backend."""

import logging
import os
from pathlib import Path
from typing import Optional


# --- Вспомогательные функции ---
def _mask_value(value: str) -> str:
    """Маскирует чувствительные значения для безопасного вывода в логи."""
    if not isinstance(value, str) or len(value) < 12:
        return "Not configured or too short to mask"
    return f"{value[:5]}...{value[-4:]}"


def _display_cap(value: int) -> str:
    return "all" if value <= 0 else str(value)


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_SQLITE_DB_PATH = (_BACKEND_DIR / "data" / "experts.db").resolve()


def _normalize_database_url(database_url: str) -> str:
    """Resolve relative SQLite URLs against the backend root."""
    if not database_url:
        return f"sqlite:///{_DEFAULT_SQLITE_DB_PATH}"

    if not database_url.startswith("sqlite:///"):
        return database_url

    sqlite_path = Path(database_url.replace("sqlite:///", "", 1)).expanduser()
    if not sqlite_path.is_absolute():
        sqlite_path = (_BACKEND_DIR / sqlite_path).resolve()
    else:
        sqlite_path = sqlite_path.resolve()
    return f"sqlite:///{sqlite_path}"


# --- API / Auth Configuration ---
# Runtime AI traffic goes through OpenRouter. ``OPENAI_API_KEY`` remains an
# intentional compatibility fallback for local/docker setups that used the
# OpenAI-compatible variable name before this migration.
OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
OPENROUTER_BASE_URL: str = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")

# Legacy Vertex settings are retained only for offline maintenance scripts
# that have not been migrated. The query-time runtime must not depend on them.
LEGACY_GOOGLE_AI_STUDIO_API_KEYS_STR = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
LEGACY_GOOGLE_AI_STUDIO_API_KEYS = [
    key.strip()
    for key in (LEGACY_GOOGLE_AI_STUDIO_API_KEYS_STR or "").split(",")
    if key.strip()
]
VERTEX_AI_SERVICE_ACCOUNT_JSON = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH")
GOOGLE_APPLICATION_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
VERTEX_AI_PROJECT_ID = os.getenv("VERTEX_AI_PROJECT_ID")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")

# --- Agent Context API ---
AGENT_CONTEXT_API_TOKEN: str | None = os.getenv("AGENT_CONTEXT_API_TOKEN")
REDDIT_SEARCH_CLIENT_TOKENS: list[str] = [
    token.strip()
    for token in os.getenv("REDDIT_SEARCH_CLIENT_TOKENS", "").split(",")
    if token.strip()
]
AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE: int = int(
    os.getenv("AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE", "10")
)
AGENT_CONTEXT_TIMEOUT_SECONDS: int = int(
    os.getenv("AGENT_CONTEXT_TIMEOUT_SECONDS", "3600")
)
AGENT_CONTEXT_MAX_RESPONSE_BYTES: int = int(
    os.getenv("AGENT_CONTEXT_MAX_RESPONSE_BYTES", "100000000")
)
AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS", "0")
)
AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS", "0")
)
AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE", "0")
)
AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS", "0")
)
AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE", "0")
)
AGENT_CONTEXT_DIGEST_MAX_SIGNALS: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_SIGNALS", "0")
)
AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS: int = int(
    os.getenv("AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS", "16384")
)
AGENT_CONTEXT_RESULTS_DIR: str | None = os.getenv("AGENT_CONTEXT_RESULTS_DIR")
QUERY_RESULTS_DIR: str | None = os.getenv("QUERY_RESULTS_DIR")
QUERY_RESULTS_TTL_DAYS: float = float(os.getenv("QUERY_RESULTS_TTL_DAYS", "7"))
AGENT_CONTEXT_RESULTS_TTL_DAYS: float = float(
    os.getenv("AGENT_CONTEXT_RESULTS_TTL_DAYS", "7")
)

# --- Public query endpoint protection ---
# The Panel UI endpoint is unauthenticated, so these in-process guards are the
# only protection for the OpenRouter budget. Both reset on restart; production
# runs a single uvicorn worker, so in-memory state is sufficient.
QUERY_RATE_LIMIT_ENABLED: bool = os.getenv(
    "QUERY_RATE_LIMIT_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
QUERY_RATE_LIMIT_PER_HOUR: int = int(os.getenv("QUERY_RATE_LIMIT_PER_HOUR", "12"))
DAILY_QUERY_BUDGET: int = int(os.getenv("DAILY_QUERY_BUDGET", "200"))

# --- Citation verification (trust badge on expert answers) ---
# Checks that claims citing [post:ID] are supported by the cited post text:
# deterministic lexical layer + optional cheap LLM judge. Fail-open: on any
# error the report is omitted and the UI shows no badge.
CITATION_VERIFICATION_ENABLED: bool = os.getenv(
    "CITATION_VERIFICATION_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
CITATION_VERIFICATION_USE_LLM: bool = os.getenv(
    "CITATION_VERIFICATION_USE_LLM", "true"
).strip().lower() in {"1", "true", "yes", "on"}
CITATION_VERIFICATION_MAX_PAIRS: int = int(
    os.getenv("CITATION_VERIFICATION_MAX_PAIRS", "24")
)
CITATION_VERIFICATION_SOURCE_CHAR_CAP: int = int(
    os.getenv("CITATION_VERIFICATION_SOURCE_CHAR_CAP", "4000")
)

# --- Model Configuration ---
# All query-time models are addressed by their OpenRouter slugs.

MODEL_MAP: str = os.getenv("MODEL_MAP", "google/gemini-2.5-flash-lite")

MODEL_SYNTHESIS: str = os.getenv("MODEL_SYNTHESIS", "google/gemini-3-flash-preview")

MODEL_ANALYSIS: str = os.getenv("MODEL_ANALYSIS", "google/gemini-3.1-flash-lite")

# Scout must use a Vertex-AI-available model. `gemini-3.1-flash-lite-preview`
# returned HTTP 404 on Vertex AI for this project and degraded every Scout
# call to a wide keyword fallback, which silently exploded downstream
# retrieval latency. Pin to the same lightweight family that powers Map.
MODEL_SCOUT: str = os.getenv("MODEL_SCOUT", "google/gemini-3.1-flash-lite")

MODEL_MEDIUM_SCORING: str = os.getenv("MODEL_MEDIUM_SCORING", "google/gemini-3.1-flash-lite")

MODEL_COMMENT_GROUPS: str = os.getenv("MODEL_COMMENT_GROUPS", "google/gemini-3.1-flash-lite")

# Drift analysis has no panel-side generation model: the engine is headless
# OpenCode with the hardcoded OPENCODE_MODEL in src/services/opencode_drift_client.py.
# --- Meta-Synthesis (Cross-Expert Analysis) ---
MODEL_META_SYNTHESIS: str = os.getenv("MODEL_META_SYNTHESIS", "google/gemini-3-flash-preview")
META_SYNTHESIS_TIMEOUT_SECONDS: float = float(
    os.getenv("META_SYNTHESIS_TIMEOUT_SECONDS", "120")
)

# --- Embedding Configuration ---
MODEL_EMBEDDING: str = os.getenv("MODEL_EMBEDDING", "google/gemini-embedding-001")
EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

# --- Reddit Search Configuration ---
REDDIT_SEARCH_DEBUG: bool = (
    os.getenv("REDDIT_SEARCH_DEBUG", "false").lower() == "true"
)
REDDIT_RERANK_CANDIDATES: int = int(os.getenv("REDDIT_RERANK_CANDIDATES", "18"))
# Candidate-cut diversity: this many of the rerank slots are reserved for the
# best posts from strategies and subreddits the heuristic top does not already
# cover. Measured 2026-10-18: the median search has 134 unique candidates and
# only REDDIT_RERANK_CANDIDATES of them are ever judged, so the cut decides
# what the answer can possibly be based on. 0 keeps the plain heuristic top.
REDDIT_RERANK_DIVERSITY_SLOTS: int = int(
    os.getenv("REDDIT_RERANK_DIVERSITY_SLOTS", "0")
)
# Google/Serper query form for comparison searches: a QUOTED pair of the
# compared products (Google honours quotes) instead of the plan query. Three
# measured runs on 12 comparison questions: 59% of returned threads mention
# both products versus 36% for the plan query, and twice as many explicitly
# compare them (p < 0.005). Falls back to the plan query when the quoted form
# returns nothing at all.
REDDIT_SERPER_ENTITY_QUERY: bool = (
    os.getenv("REDDIT_SERPER_ENTITY_QUERY", "true").lower() == "true"
)
# For comparison intent, ALSO send the compared products themselves as the
# query ("GLM-5.3 Flash DeepSeek V4.1 Flash") instead of relying only on the
# anchor pair heuristic ("glm-5.3 v4.1 benchmark"). Measured 2026-10-18 on the
# owner's own comparison questions: the anchor pair names one product at best
# ("5.3 good benchmark", "2.5 codex benchmark", "about agent benchmark"),
# while the entity query returned 2-3x more posts that mention both compared
# products and its posts were selected by the judge 1.7-2.2x more often.
# Additive on purpose: the anchor channel keeps running, because it wins where
# the anchors already happen to be the product names. Owner decision
# 2026-10-18: on by default. Set false to restore the previous plan.
REDDIT_COMPARISON_ENTITY_PAIR: bool = (
    os.getenv("REDDIT_COMPARISON_ENTITY_PAIR", "true").lower() == "true"
)
# Aligned with RERANK_CANDIDATES so every rerank candidate can carry
# full content + comments into the AI scoring pass.
REDDIT_PRE_RERANK_ENRICH_LIMIT: int = int(
    os.getenv("REDDIT_PRE_RERANK_ENRICH_LIMIT", "18")
)
REDDIT_MIN_CONFIDENCE: float = float(
    os.getenv("REDDIT_MIN_CONFIDENCE", "0.52")
)

# --- Reddit LLM engine: DeepSeek Harness (dsh) ---
# dsh    - local `dsh --profile headless` subprocess (DeepSeek V4.1 Flash);
#          the only engine the Reddit roles use, see services/dsh_client.py
# gemini - OpenRouter (legacy; requires credits, kept selectable for rollback)
# There is deliberately NO automatic cross-engine fallback: a dsh failure is
# reported as degradation instead of being hidden behind a second provider.
REDDIT_LLM_BACKEND: str = os.getenv("REDDIT_LLM_BACKEND", "dsh").lower()
if REDDIT_LLM_BACKEND not in {"dsh", "gemini"}:
    REDDIT_LLM_BACKEND = "dsh"
# Tool-free profile overlay; disables bash/fs/web/subagent tools so the model
# answers instead of browsing. Repo copy: backend/deploy/dsh/reddit-llm.patch.yml
DSH_PATCH_PATH: str = os.getenv("DSH_PATCH_PATH", "")
# Namespaced on purpose: the harness exports DSH_PROFILE/DSH_SESSION_ID into
# every process it starts, and inheriting them boots the interactive TUI
# profile instead of `headless` (see services/dsh_client.py).
DSH_BIN: str = os.getenv("REDDIT_DSH_BIN", "dsh")
DSH_PROFILE: str = os.getenv("REDDIT_DSH_PROFILE", "headless")
# One dsh call boots the whole plugin stack (~3 s), so calls are serialized.
REDDIT_DSH_TIMEOUT_S: float = float(os.getenv("REDDIT_DSH_TIMEOUT_S", "90"))
REDDIT_DSH_CONCURRENCY: int = int(os.getenv("REDDIT_DSH_CONCURRENCY", "2"))

# --- Reddit Search V2: reflection retry, telemetry, enrichment cache ---
# One reflection retry fires only when the confidence filter left 0 posts:
# the judge's top rejection reasons feed a short LLM replanner, whose query
# gets one bounded second retrieval pass.
REDDIT_REFLECTION_RETRY_ENABLED: bool = (
    os.getenv("REDDIT_REFLECTION_RETRY_ENABLED", "true").lower() == "true"
)
# The retry is worth spending on a thin shortlist, not only on a dead end:
# synthesis abstains on 32% of searches that reach it with a single post and
# on 0% of those with four or more, so one post is the expensive case.
REDDIT_REFLECTION_MIN_POSTS: int = int(
    os.getenv("REDDIT_REFLECTION_MIN_POSTS", "2")
)
# Evidence-span judge gate: the reranker must quote a verbatim span from the
# post/comments that answers the question; a rating without a quotable span
# is capped hard. Kills "hallucinated relevance" — an answer you cannot
# point to in the text is not an answer.
REDDIT_EVIDENCE_GATE_ENABLED: bool = (
    os.getenv("REDDIT_EVIDENCE_GATE_ENABLED", "true").lower() == "true"
)
REDDIT_NO_EVIDENCE_MAX_SCORE: float = float(
    os.getenv("REDDIT_NO_EVIDENCE_MAX_SCORE", "0.35")
)
# Statuses that can carry a post into the answer: exactly the two quote-verified
# tiers. The gate is an allowlist on purpose — "unrated" (never reached the
# judge) and any future status fail closed instead of leaking an unverified
# post into an answer.
EVIDENCE_GATE_ALLOWED_STATUSES = frozenset({"verified", "verified_normalized"})
# Kept for callers that need the complement (telemetry, diagnostics).
EVIDENCE_GATE_BLOCKED_STATUSES = frozenset(
    {"missing", "invalid_rating", "unavailable", "unrated"}
)
# Second, separately recorded tier of quote verification: identical words
# after stripping markdown emphasis and unifying typographic punctuation.
# Disabling it restores the strict exact-substring behaviour.
REDDIT_EVIDENCE_LOOSE_MATCH_ENABLED: bool = (
    os.getenv("REDDIT_EVIDENCE_LOOSE_MATCH_ENABLED", "true").lower() == "true"
)
# JSONL decision log (query, strategies, winners, abstain reason). Powers
# periodic strategy/subreddit effectiveness review instead of gut-feel tuning.
REDDIT_TELEMETRY_ENABLED: bool = (
    os.getenv("REDDIT_TELEMETRY_ENABLED", "true").lower() == "true"
)
REDDIT_TELEMETRY_PATH: str = os.getenv(
    "REDDIT_TELEMETRY_PATH", "data/reddit_search_telemetry.jsonl"
)
# In-memory cache for /details enrichment: iterative research sessions re-fetch
# the same threads, paying 10-20s and Reddit rate-limit budget every time.
REDDIT_ENRICH_CACHE_TTL_S: int = int(
    os.getenv("REDDIT_ENRICH_CACHE_TTL_S", "1800")
)
REDDIT_ENRICH_CACHE_MAX: int = int(
    os.getenv("REDDIT_ENRICH_CACHE_MAX", "512")
)
REDDIT_SOFT_CONFIDENCE: float = float(
    os.getenv("REDDIT_SOFT_CONFIDENCE", "0.44")
)
# Synthesis context budget (Step 2 of reddit search audit plan):
# top-K highest-scored comment roots per source and a hard per-source
# char cap shared between the post body and its comment tree.
REDDIT_SYNTH_COMMENT_TOP_K: int = int(os.getenv("REDDIT_SYNTH_COMMENT_TOP_K", "12"))
REDDIT_SYNTH_SOURCE_CHAR_CAP: int = int(
    os.getenv("REDDIT_SYNTH_SOURCE_CHAR_CAP", "15000")
)
# Synthesis output budget; finish_reason=length triggers one automatic
# retry with a doubled budget (see reddit_synthesis_service).
REDDIT_SYNTH_MAX_TOKENS: int = int(os.getenv("REDDIT_SYNTH_MAX_TOKENS", "4096"))
# Findings rendered on the partial branch. "Partial" must stay useful: three
# observations read as an empty answer even when the sources carry more.
REDDIT_SYNTH_PARTIAL_MAX_FINDINGS: int = int(
    os.getenv("REDDIT_SYNTH_PARTIAL_MAX_FINDINGS", "5")
)
# A stray advisory gap sentence next to coverage=sufficient is a prompt
# discipline issue, not a reason to relabel a sufficient answer as partial.
# true restores the previous "any gap downgrades" behaviour.
REDDIT_SYNTH_GAP_FORCES_PARTIAL: bool = (
    os.getenv("REDDIT_SYNTH_GAP_FORCES_PARTIAL", "false").lower() == "true"
)
# Reddit synthesis backend: dsh | gemini | opencode | auto | shadow.
#   dsh     - DeepSeek Harness via REDDIT_LLM_BACKEND (current default)
#   gemini  - OpenRouter MODEL_SYNTHESIS only (legacy; needs credits)
#   opencode - headless opencode serve first, Gemini as failure fallback
#   auto    - opencode within OPENCODE_SYNTH_TIMEOUT_S, else Gemini
#   shadow  - both run concurrently; user gets Gemini, opencode logged for A/B
REDDIT_SYNTH_BACKEND: str = os.getenv("REDDIT_SYNTH_BACKEND", "dsh").lower()
if REDDIT_SYNTH_BACKEND not in {"dsh", "gemini", "opencode", "auto", "shadow"}:
    REDDIT_SYNTH_BACKEND = "dsh"
OPENCODE_URL: str = os.getenv("OPENCODE_URL", "http://127.0.0.1:4096")
OPENCODE_SYNTH_MODEL: str = os.getenv("OPENCODE_SYNTH_MODEL", "opencode/x-preview-f-free")
OPENCODE_SYNTH_TIMEOUT_S: float = float(os.getenv("OPENCODE_SYNTH_TIMEOUT_S", "60"))
# auto mode: seconds the free model gets alone before Gemini joins the race
OPENCODE_SYNTH_HEADSTART_S: float = float(os.getenv("OPENCODE_SYNTH_HEADSTART_S", "20"))
OPENCODE_SYNTH_CONCURRENCY: int = int(os.getenv("OPENCODE_SYNTH_CONCURRENCY", "2"))
# Reddit proxy sidecar (docker compose service on the same host/network)
REDDIT_PROXY_URL: str = os.getenv("REDDIT_PROXY_URL", "http://reddit-proxy:3000")

# --- Arctic Shift (exhaustive per-subreddit archive search) ---
# Free community mirror with live ingestion; keyword search requires a
# subreddit scope, so it complements scout-targeted retrieval only.
ARCTIC_SHIFT_ENABLED: bool = (
    os.getenv("ARCTIC_SHIFT_ENABLED", "true").lower() == "true"
)
ARCTIC_SHIFT_ENDPOINT: str = os.getenv(
    "ARCTIC_SHIFT_ENDPOINT",
    "https://arctic-shift.photon-reddit.com/api/posts/search",
)
ARCTIC_TARGET_SUBREDDITS: int = int(os.getenv("ARCTIC_TARGET_SUBREDDITS", "2"))
# The archive times out server-side (HTTP 422 "Timeout. Maybe slow down a bit")
# on unbounded or expensive keyword queries; measured 2026-10-18: a 30-day
# window answers, a 90-day one does not, and r/ChatGPT fails even at 7 days.
# So every request carries a bounded window and the limit stays small.
ARCTIC_LIMIT_PER_SUB: int = int(
    min(25, max(1, int(os.getenv("ARCTIC_LIMIT_PER_SUB", "12"))))
)
ARCTIC_WINDOW_DAYS: int = int(os.getenv("ARCTIC_WINDOW_DAYS", "30"))
ARCTIC_NARROW_WINDOW_DAYS: int = int(
    os.getenv("ARCTIC_NARROW_WINDOW_DAYS", "7")
)
# "Not supported with very active users or subreddits": r/ChatGPT (9M members)
# times out even on a 7-day window, so subscriber count gates the channel.
# 0 disables the check (the endpoint that reports counts is itself flaky).
ARCTIC_MAX_SUBSCRIBERS: int = int(
    os.getenv("ARCTIC_MAX_SUBSCRIBERS", "1000000")
)
# This is a free service with load-dependent limits; requests are serialized
# and paced. Measured 2026-10-18, a 30-day window was refused (422) on every
# probed mid/large subreddit while a 7-day one answered, so the budget is kept
# small: two attempts per subreddit, no more.
ARCTIC_REQUEST_PAUSE_S: float = float(
    os.getenv("ARCTIC_REQUEST_PAUSE_S", "0.5")
)
ARCTIC_MAX_REQUESTS: int = int(os.getenv("ARCTIC_MAX_REQUESTS", "4"))
ARCTIC_429_MAX_WAIT_S: float = float(os.getenv("ARCTIC_429_MAX_WAIT_S", "20"))

# --- Serper.dev (Google SERP discovery: site:reddit.com via real Google) ---
# Optional; without a key the channel is silently skipped.
# 1 credit per search with <=10 results; free tier 2500 queries.
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
SERPER_ENDPOINT: str = os.getenv(
    "SERPER_ENDPOINT",
    "https://google.serper.dev/search",
)
SERPER_RESULTS: int = int(os.getenv("SERPER_RESULTS", "8"))

# --- Hybrid Retrieval ---
HYBRID_VECTOR_TOP_K: int = int(os.getenv("HYBRID_VECTOR_TOP_K", "150"))
HYBRID_FTS5_TOP_K: int = int(os.getenv("HYBRID_FTS5_TOP_K", "100"))
HYBRID_RRF_K: int = int(os.getenv("HYBRID_RRF_K", "60"))

# --- Video Hub Models ---
MODEL_VIDEO_PRO: str = os.getenv("MODEL_VIDEO_PRO", "gemini-3.1-pro-preview")
MODEL_VIDEO_FLASH: str = os.getenv("MODEL_VIDEO_FLASH", "gemini-3-flash-preview")

# --- Medium Scoring Configuration ---
# Threshold for accepting medium posts (0.0-1.0)
MEDIUM_SCORE_THRESHOLD: float = float(os.getenv("MEDIUM_SCORE_THRESHOLD", "0.7"))
# Max number of medium posts to include in context
MEDIUM_MAX_SELECTED_POSTS: int = int(os.getenv("MEDIUM_MAX_SELECTED_POSTS", "5"))
# Hard limit on posts processed to prevent OOM
MEDIUM_MAX_POSTS: int = int(os.getenv("MEDIUM_MAX_POSTS", "50"))

# --- Drift Embedding Scoring (replaces LLM chunked scoring) ---
# Cosine similarity threshold (RETRIEVAL_QUERY vs RETRIEVAL_DOCUMENT) above which
# a drift group is marked HIGH. 0.75 is empirically safe for gemini-embedding-001;
# tune via config / env in production.
DRIFT_EMBEDDING_THRESHOLD: float = float(
    os.getenv("DRIFT_EMBEDDING_THRESHOLD", "0.75")
)
# Max number of drift groups to return at query time (pre-merge dedup).
DRIFT_EMBEDDING_TOP_K: int = int(os.getenv("DRIFT_EMBEDDING_TOP_K", "20"))

# --- Лимиты (Rate Limiting) ---
# For Tier 1 (paid) with 300-1000 RPM, 25 is optimal. For Free Tier with 15 RPM, use 8.
MAP_MAX_PARALLEL: int = int(os.getenv("MAP_MAX_PARALLEL", "25"))
# Chunk size for Map Phase (smaller = more reliable JSON, but more API calls)
MAP_CHUNK_SIZE: int = int(os.getenv("MAP_CHUNK_SIZE", "50"))

# --- Expert Concurrency ---
# Global limit for parallel expert processing (prevents OOM at scale)
MAX_CONCURRENT_EXPERTS: int = int(os.getenv("MAX_CONCURRENT_EXPERTS", "5"))

# --- Super-Passport Search (FTS5) ---
# Maximum posts to retrieve via FTS5 before Map Phase
MAX_FTS_RESULTS: int = int(os.getenv("MAX_FTS_RESULTS", "300"))
# Feature flag: enable FTS5 pre-filtering (default: False for A/B testing)
USE_SUPER_PASSPORT_DEFAULT: bool = (
    os.getenv("USE_SUPER_PASSPORT_DEFAULT", "false").lower() == "true"
)
# Circuit Breaker: max fallbacks before disabling FTS5 for remaining experts
FTS5_CIRCUIT_BREAKER_THRESHOLD: int = int(
    os.getenv("FTS5_CIRCUIT_BREAKER_THRESHOLD", "3")
)

# --- Прочие настройки ---
DATABASE_URL: str = _normalize_database_url(
    os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_DB_PATH}")
)
# Keep process env aligned with the normalized runtime config for downstream imports.
os.environ["DATABASE_URL"] = DATABASE_URL

# --- Конфигурация логирования ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
# Use relative paths for development, absolute for production
if os.getenv("ENVIRONMENT") == "production":
    BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "/app/data/backend.log")
    FRONTEND_LOG_FILE: str = os.getenv("FRONTEND_LOG_FILE", "/app/data/frontend.log")
else:
    BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "data/backend.log")
    FRONTEND_LOG_FILE: str = os.getenv("FRONTEND_LOG_FILE", "data/frontend.log")

def get_runtime_config_log_lines() -> list[str]:
    """Return human-readable runtime configuration lines for explicit startup logging."""

    lines = ["--- Backend runtime configuration ---"]

    lines.append(
        "  OpenRouter API: "
        f"{'Configured' if OPENROUTER_API_KEY else 'Not configured'}"
    )

    lines.extend(
        [
            "--- Loaded model configuration ---",
            f"  Map фаза:          {MODEL_MAP}",
            f"  Синтез:            {MODEL_SYNTHESIS}",
            f"  Анализ:            {MODEL_ANALYSIS}",
            f"  AI Scout:          {MODEL_SCOUT}",
            f"  Meta-Synthesis:    {MODEL_META_SYNTHESIS}",
            f"  Meta Timeout:      {META_SYNTHESIS_TIMEOUT_SECONDS:g}s",
            "--- Loaded limits configuration ---",
            f"  Map Max Parallel:      {MAP_MAX_PARALLEL}",
            f"  Max Concurrent Experts: {MAX_CONCURRENT_EXPERTS}",
            "--- Loaded Agent Context API configuration ---",
            "  Agent Context API Token: "
            f"{'Configured' if AGENT_CONTEXT_API_TOKEN else 'Not configured'}",
            f"  Agent Context Rate Limit: {AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE}/min",
            f"  Agent Context Timeout:    {AGENT_CONTEXT_TIMEOUT_SECONDS}s",
            f"  Agent Context Max Bytes:  {AGENT_CONTEXT_MAX_RESPONSE_BYTES}",
            "  Agent Context Digest Caps: "
            f"sources={_display_cap(AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS)}, "
            f"source_chars={_display_cap(AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS)}, "
            f"comments/source={_display_cap(AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE)}, "
            f"comment_chars={_display_cap(AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS)}, "
            f"links/source={_display_cap(AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE)}, "
            f"signals={_display_cap(AGENT_CONTEXT_DIGEST_MAX_SIGNALS)}, "
            f"output_tokens={AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS}",
            "  Agent Context Results Dir: "
            f"{AGENT_CONTEXT_RESULTS_DIR or 'default next to backend log'}",
            "--- Loaded artifact retention configuration ---",
            f"  Query Results Dir:          {QUERY_RESULTS_DIR or 'default next to backend log'}",
            f"  Query Results TTL:          {QUERY_RESULTS_TTL_DAYS:g}d",
            f"  Agent Context Results TTL:  {AGENT_CONTEXT_RESULTS_TTL_DAYS:g}d",
            "--- Loaded logging configuration ---",
            f"  Log Level:         {LOG_LEVEL}",
            f"  Backend Log File:  {BACKEND_LOG_FILE}",
            f"  Frontend Log File: {FRONTEND_LOG_FILE}",
        ]
    )
    return lines


def log_runtime_configuration(logger: logging.Logger) -> None:
    """Emit runtime configuration through the active logger instead of import-time prints."""

    for line in get_runtime_config_log_lines():
        logger.info(line)
