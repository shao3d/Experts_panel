"""Centralized runtime configuration for the backend."""

import logging
import os
from pathlib import Path


# --- Вспомогательные функции ---
def _mask_value(value: str) -> str:
    """Маскирует чувствительные значения для безопасного вывода в логи."""
    if not isinstance(value, str) or len(value) < 12:
        return "Not configured or too short to mask"
    return f"{value[:5]}...{value[-4:]}"


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

# --- Model Configuration ---
# Only Gemini models on Vertex AI are supported.
# Defined in .env or defaulting to stable versions here.

MODEL_MAP: str = os.getenv("MODEL_MAP", "gemini-2.5-flash-lite")

MODEL_SYNTHESIS: str = os.getenv("MODEL_SYNTHESIS", "gemini-3-flash-preview")

MODEL_ANALYSIS: str = os.getenv("MODEL_ANALYSIS", "gemini-2.5-flash")

MODEL_SCOUT: str = os.getenv("MODEL_SCOUT", "gemini-3.1-flash-lite-preview")

MODEL_MEDIUM_SCORING: str = os.getenv("MODEL_MEDIUM_SCORING", "gemini-2.5-flash")

MODEL_COMMENT_GROUPS: str = os.getenv("MODEL_COMMENT_GROUPS", "gemini-2.5-flash")

MODEL_DRIFT_ANALYSIS: str = os.getenv("MODEL_DRIFT_ANALYSIS", "gemini-3-flash-preview")

# --- Meta-Synthesis (Cross-Expert Analysis) ---
MODEL_META_SYNTHESIS: str = os.getenv("MODEL_META_SYNTHESIS", "gemini-3-flash-preview")

# --- Embedding Configuration ---
MODEL_EMBEDDING: str = os.getenv("MODEL_EMBEDDING", "gemini-embedding-001")
EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

# --- Reddit Search Configuration ---
REDDIT_SEARCH_V2_ENABLED: bool = (
    os.getenv("REDDIT_SEARCH_V2_ENABLED", "true").lower() == "true"
)
REDDIT_SEARCH_DEBUG: bool = (
    os.getenv("REDDIT_SEARCH_DEBUG", "false").lower() == "true"
)
REDDIT_RERANK_CANDIDATES: int = int(os.getenv("REDDIT_RERANK_CANDIDATES", "18"))
REDDIT_PRE_RERANK_ENRICH_LIMIT: int = int(
    os.getenv("REDDIT_PRE_RERANK_ENRICH_LIMIT", "12")
)
REDDIT_MIN_CONFIDENCE: float = float(
    os.getenv("REDDIT_MIN_CONFIDENCE", "0.52")
)
REDDIT_SOFT_CONFIDENCE: float = float(
    os.getenv("REDDIT_SOFT_CONFIDENCE", "0.44")
)

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

    if VERTEX_AI_SERVICE_ACCOUNT_JSON or VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH or GOOGLE_APPLICATION_CREDENTIALS_PATH:
        lines.append(
            "  Vertex AI Auth: Configured "
            f"(project={VERTEX_AI_PROJECT_ID or 'auto'}, location={VERTEX_AI_LOCATION})"
        )
    elif LEGACY_GOOGLE_AI_STUDIO_API_KEYS:
        lines.append(
            "  Legacy API keys: configured as migration fallback "
            f"({len(LEGACY_GOOGLE_AI_STUDIO_API_KEYS)} keys)"
        )
    else:
        lines.append("  Vertex AI Auth: Not configured")

    lines.extend(
        [
            "--- Loaded model configuration ---",
            f"  Map фаза:          {MODEL_MAP}",
            f"  Синтез:            {MODEL_SYNTHESIS}",
            f"  Анализ:            {MODEL_ANALYSIS}",
            f"  AI Scout:          {MODEL_SCOUT}",
            f"  Drift Analysis:    {MODEL_DRIFT_ANALYSIS}",
            f"  Meta-Synthesis:    {MODEL_META_SYNTHESIS}",
            "--- Loaded limits configuration ---",
            f"  Map Max Parallel:      {MAP_MAX_PARALLEL}",
            f"  Max Concurrent Experts: {MAX_CONCURRENT_EXPERTS}",
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
