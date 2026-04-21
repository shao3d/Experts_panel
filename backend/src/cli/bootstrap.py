"""Shared bootstrap helpers for standalone backend CLI scripts."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Awaitable

from dotenv import load_dotenv

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def resolve_backend_dir(current_file: str | Path) -> Path:
    """Resolve the backend directory regardless of current working directory."""
    current_path = Path(current_file).resolve()
    for candidate in [current_path.parent, *current_path.parents]:
        if (candidate / "src").is_dir():
            return candidate
    raise RuntimeError(f"Could not resolve backend directory from {current_file}")


def setup_backend_path(backend_dir: str | Path) -> Path:
    """Ensure backend root is importable as a package root for `src.*` imports."""
    backend_dir_path = Path(backend_dir).resolve()
    backend_dir_str = str(backend_dir_path)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)
    return backend_dir_path


def load_backend_env(env_path: str | Path) -> Path:
    """Load `backend/.env` from an explicit path."""
    resolved_env_path = Path(env_path).resolve()
    load_dotenv(resolved_env_path, override=False)
    return resolved_env_path


def configure_cli_logging(
    name: str,
    level: str | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure consistent CLI logging with respect for `LOG_LEVEL`."""
    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    if verbose and resolved_level == "INFO":
        resolved_level = "DEBUG"

    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format=_LOG_FORMAT,
        datefmt=_LOG_DATE_FORMAT,
        force=True,
    )

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, resolved_level, logging.INFO))
    return logger


def bootstrap_cli(
    current_file: str | Path,
    *,
    logger_name: str,
    level: str | None = None,
    verbose: bool = False,
) -> tuple[Path, logging.Logger]:
    """Resolve backend root, load `.env`, and configure logging."""
    backend_dir = resolve_backend_dir(current_file)
    setup_backend_path(backend_dir)
    load_backend_env(backend_dir / ".env")
    logger = configure_cli_logging(logger_name, level=level, verbose=verbose)
    return backend_dir, logger


def require_vertex_runtime() -> Any:
    """Ensure Vertex runtime auth is configured before running LLM/embedding CLI."""
    from ..services.vertex_ai_auth import get_vertex_ai_auth_manager

    auth_manager = get_vertex_ai_auth_manager()
    if not auth_manager.is_configured():
        raise RuntimeError(
            "Vertex AI runtime is not configured. "
            "Set VERTEX_AI_SERVICE_ACCOUNT_JSON, "
            "VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH, or GOOGLE_APPLICATION_CREDENTIALS."
        )
    return auth_manager


def set_default_sqlite_database_url(
    backend_dir: str | Path,
    *,
    db_path: str | Path | None = None,
    force: bool = False,
) -> Path:
    """Point `DATABASE_URL` at the default local SQLite DB when the script needs it."""
    backend_dir_path = Path(backend_dir).resolve()
    resolved_db_path = Path(db_path).resolve() if db_path else backend_dir_path / "data" / "experts.db"
    resolved_db_path = resolved_db_path.resolve()
    current_database_url = os.getenv("DATABASE_URL")
    if current_database_url and current_database_url.startswith("sqlite:///") and not force:
        current_path = Path(current_database_url.replace("sqlite:///", "", 1))
        if not current_path.is_absolute():
            resolved_current_path = (backend_dir_path / current_path).resolve()
            os.environ["DATABASE_URL"] = f"sqlite:///{resolved_current_path}"
            return resolved_current_path
        return current_path.resolve()

    if force or not current_database_url:
        os.environ["DATABASE_URL"] = f"sqlite:///{resolved_db_path}"
    return resolved_db_path


def get_sqlite_db_path(backend_dir: str | Path) -> Path:
    """Resolve an on-disk SQLite DB path from env when possible, else use the default."""
    backend_dir_path = Path(backend_dir).resolve()
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("sqlite:///"):
        current_path = Path(database_url.replace("sqlite:///", "", 1)).expanduser()
        if not current_path.is_absolute():
            resolved_current_path = (backend_dir_path / current_path).resolve()
            os.environ["DATABASE_URL"] = f"sqlite:///{resolved_current_path}"
            return resolved_current_path
        resolved_current_path = current_path.resolve()
        os.environ["DATABASE_URL"] = f"sqlite:///{resolved_current_path}"
        return resolved_current_path
    return (backend_dir_path / "data" / "experts.db").resolve()


def get_postgres_database_url(
    *,
    env_var: str = "POSTGRES_DATABASE_URL",
    fallback_env_var: str = "DATABASE_URL",
) -> str:
    """Read a PostgreSQL URL without accidentally accepting SQLite runtime config."""
    database_url = os.getenv(env_var) or os.getenv(fallback_env_var)
    if not database_url:
        raise RuntimeError(
            f"PostgreSQL URL is not configured. Set {env_var} "
            f"or override {fallback_env_var} with a PostgreSQL connection string."
        )
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            f"{env_var if os.getenv(env_var) else fallback_env_var} must point to PostgreSQL, "
            f"got: {database_url.split(':', 1)[0]}"
        )
    return database_url


def run_async(awaitable: Awaitable[Any]) -> Any:
    """Run async CLI code with a stable keyboard interrupt exit code."""
    try:
        return asyncio.run(awaitable)
    except KeyboardInterrupt as exc:
        raise SystemExit(130) from exc
