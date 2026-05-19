"""Retention cleanup for durable UI and Agent Context result artifacts."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Iterable

from .. import config

logger = logging.getLogger(__name__)


def query_results_dir() -> Path:
    """Return the durable UI query-result directory."""

    configured = os.getenv("QUERY_RESULTS_DIR") or config.QUERY_RESULTS_DIR
    if configured:
        return Path(configured).expanduser()
    return Path(config.BACKEND_LOG_FILE).expanduser().resolve().parent / "query_results"


def agent_context_results_dir() -> Path:
    """Return the durable Agent Context result directory."""

    configured = os.getenv("AGENT_CONTEXT_RESULTS_DIR") or config.AGENT_CONTEXT_RESULTS_DIR
    if configured:
        return Path(configured).expanduser()
    return (
        Path(config.BACKEND_LOG_FILE)
        .expanduser()
        .resolve()
        .parent
        / "agent_context_results"
    )


def cleanup_result_artifacts(now: float | None = None) -> dict[str, object]:
    """Delete expired durable result artifacts from known backend artifact dirs."""

    now = time.time() if now is None else now
    targets = [
        (
            "query_results",
            query_results_dir(),
            float(config.QUERY_RESULTS_TTL_DAYS),
        ),
        (
            "agent_context_results",
            agent_context_results_dir(),
            float(config.AGENT_CONTEXT_RESULTS_TTL_DAYS),
        ),
    ]
    results = [
        cleanup_json_artifacts(name=name, directory=directory, ttl_days=ttl_days, now=now)
        for name, directory, ttl_days in targets
    ]
    return {
        "deleted_count": sum(int(item["deleted_count"]) for item in results),
        "deleted_bytes": sum(int(item["deleted_bytes"]) for item in results),
        "targets": results,
    }


def cleanup_json_artifacts(
    *,
    name: str,
    directory: Path,
    ttl_days: float,
    now: float | None = None,
) -> dict[str, object]:
    """Delete top-level JSON files older than ttl_days in one artifact directory."""

    now = time.time() if now is None else now
    if ttl_days <= 0:
        logger.warning(
            "Skipping %s artifact cleanup because ttl_days=%s is not positive",
            name,
            ttl_days,
        )
        return _cleanup_result(name, directory, ttl_days, skipped=True)

    if not directory.exists():
        return _cleanup_result(name, directory, ttl_days)

    cutoff = now - (ttl_days * 86400)
    deleted_count = 0
    deleted_bytes = 0
    errors: list[str] = []

    for path in _iter_candidate_json_files(directory):
        try:
            stat = path.stat()
        except OSError as exc:
            errors.append(f"{path}: stat_failed: {exc}")
            continue
        if stat.st_mtime >= cutoff:
            continue
        try:
            path.unlink()
        except OSError as exc:
            errors.append(f"{path}: unlink_failed: {exc}")
            continue
        deleted_count += 1
        deleted_bytes += stat.st_size

    result = _cleanup_result(
        name,
        directory,
        ttl_days,
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
        errors=errors,
    )
    if deleted_count or errors:
        logger.info(
            "Artifact retention cleanup: name=%s deleted_count=%s deleted_bytes=%s errors=%s",
            name,
            deleted_count,
            deleted_bytes,
            len(errors),
        )
    return result


def _iter_candidate_json_files(directory: Path) -> Iterable[Path]:
    """Return only direct JSON artifact files, leaving temp/nested files alone."""

    return (path for path in directory.glob("*.json") if path.is_file())


def _cleanup_result(
    name: str,
    directory: Path,
    ttl_days: float,
    *,
    deleted_count: int = 0,
    deleted_bytes: int = 0,
    errors: list[str] | None = None,
    skipped: bool = False,
) -> dict[str, object]:
    return {
        "name": name,
        "directory": str(directory),
        "ttl_days": ttl_days,
        "deleted_count": deleted_count,
        "deleted_bytes": deleted_bytes,
        "errors": errors or [],
        "skipped": skipped,
    }
