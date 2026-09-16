#!/usr/bin/env python3
"""Import Video Hub JSON segments into the local SQLite database.

Supports both the legacy segment schema (title/summary/content) and the extended
schema produced by the video ingest pipeline: an optional structured `visual`
block (prompt/settings/slides) and optional `frames` references whose files are
copied under `backend/data/video_frames/<video_hash>/`.

Usage:
    python3 backend/scripts/import_video_json.py <path_to_json> [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (  # noqa: E402
    bootstrap_cli,
    get_sqlite_db_path,
    set_default_sqlite_database_url,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.import_video_json",
)
set_default_sqlite_database_url(BACKEND_DIR)

EXPERT_ID = "video_hub"
EXPERT_NAME = "Video Hub (Experts Insights)"
CHANNEL_USERNAME = "video_hub_internal"
FRAMES_ROOT = BACKEND_DIR / "data" / "video_frames"


def get_db_path() -> Path:
    """Resolve the SQLite database path for Video Hub imports."""
    default_db_path = get_sqlite_db_path(BACKEND_DIR)
    if default_db_path.exists():
        return default_db_path

    candidates = [
        BACKEND_DIR / "data" / "experts.db",
        BACKEND_DIR / "data" / "experts_panel.db",
        BACKEND_DIR / "experts_panel.db",
        BACKEND_DIR.parent / "data" / "experts.db",
        BACKEND_DIR.parent / "experts_panel.db",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0].resolve()


def slugify(text: str) -> str:
    """Convert author name into a stable ASCII-friendly ID."""
    if not text:
        return "unknown_author"

    translit_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    normalized = text.lower()
    for cyr, lat in translit_map.items():
        normalized = normalized.replace(cyr, lat)

    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_") or "unknown_author"


def generate_virtual_id(url: str, segment_id: int | str) -> int:
    """Generate a stable integer ID for synthetic `telegram_message_id` values."""
    hash_str = f"{url}_{segment_id}"
    return int(hashlib.md5(hash_str.encode()).hexdigest(), 16) % (10**9)


def normalize_video_url(video_url: str) -> str:
    if len(video_url) < 15 and "http" not in video_url:
        return f"https://www.youtube.com/watch?v={video_url}"
    return video_url


VISUAL_TEXT_KEYS = (
    "kind",
    "app",
    "model",
    "model_selected",
    "settings",
    "prompt_verbatim",
    "showcase_prompt_verbatim",
    "prompt_placeholder",
    "observed",
    "note",
    "gap",
)


def render_visual_block(visual: dict) -> str:
    """Render the structured visual payload as searchable text.

    Prompts and on-screen details live in `media_metadata.visual` for the UI and
    synthesis, but retrieval indexes `message_text` only, so the payload is also
    appended there. Keep the block human-readable: it doubles as context.
    """
    lines = ["VISUAL:"]
    for key in VISUAL_TEXT_KEYS:
        value = visual.get(key)
        if value:
            lines.append(f"{key}: {value}")
    slides = visual.get("slides_verbatim")
    if isinstance(slides, dict):
        for name, text in slides.items():
            if text:
                lines.append(f"slide[{name}]: {text}")
    frames = visual.get("frames_summary")
    if frames:
        lines.append(f"frames_summary: {frames}")
    return "\n".join(lines)


def copy_frames(frames: list, series_dir: Path, base_dir: Path | None) -> list[dict]:
    """Copy referenced frame files into the corpus frame directory."""
    copied: list[dict] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        raw_path = frame.get("path") or frame.get("file")
        if not raw_path:
            continue
        source = Path(raw_path)
        if not source.is_absolute() and base_dir is not None:
            source = base_dir / raw_path
        if not source.exists():
            logger.warning("frame missing, skipped: %s", source)
            continue
        series_dir.mkdir(parents=True, exist_ok=True)
        target = series_dir / source.name
        if not target.exists():
            shutil.copy2(source, target)
        copied.append({"time_s": frame.get("time_s"), "file": target.name})
    return copied


def import_video_json(json_path: Path, *, dry_run: bool = False, frames_base: Path | None = None) -> dict:
    json_path = json_path.expanduser().resolve()
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    db_path = get_db_path()
    logger.info("Using SQLite database at %s", db_path)

    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    meta = data.get("video_metadata", {})
    segments = data.get("segments", [])
    if not segments:
        logger.warning("No segments found in %s; nothing to import", json_path)
        return {"segments": 0, "frames": 0}

    video_url = normalize_video_url(meta.get("url", "unknown_url"))
    video_title = meta.get("title", "Untitled Video")
    author_name = meta.get("author", meta.get("channel", "Unknown Expert"))
    author_id = slugify(author_name)
    published_at = meta.get("published_at")
    url_hash = hashlib.md5(video_url.encode()).hexdigest()[:12]

    base_dir = frames_base or json_path.parent
    series_dir = FRAMES_ROOT / url_hash
    counts = {"segments": 0, "frames": 0, "with_visual": 0}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO expert_metadata (expert_id, display_name, channel_username)
            VALUES (?, ?, ?)
            """,
            (EXPERT_ID, EXPERT_NAME, CHANNEL_USERNAME),
        )

        logger.info("Importing video '%s' by %s (%s)", video_title, author_name, video_url)

        for index, segment in enumerate(segments):
            segment_id = segment.get("segment_id", index)
            virtual_message_id = generate_virtual_id(video_url, segment_id)

            raw_topic_id = segment.get("topic_id", "general")
            composite_topic_id = f"{url_hash}_{raw_topic_id}"

            visual = segment.get("visual") or {}

            full_text = (
                f"TITLE: {segment.get('title', '')}\n"
                f"SUMMARY: {segment.get('summary', '')}\n"
                f"---\nCONTENT:\n{segment.get('content', '')}"
            )
            if visual:
                full_text += "\n\n" + render_visual_block(visual)
            frames = copy_frames(segment.get("frames") or [], series_dir, base_dir)

            media_meta = {
                "type": "video_segment",
                "video_url": video_url,
                "video_title": video_title,
                "topic_id": composite_topic_id,
                "timestamp_seconds": segment.get("timestamp_seconds", 0),
                "context_bridge": segment.get("context_bridge", ""),
                "original_author": author_name,
                "original_author_id": author_id,
            }
            if published_at:
                media_meta["published_at"] = published_at
            if visual:
                media_meta["visual"] = visual
                counts["with_visual"] += 1
            if frames:
                media_meta["frames"] = frames
                counts["frames"] += len(frames)

            if dry_run:
                counts["segments"] += 1
                continue

            values = (
                CHANNEL_USERNAME,
                meta.get("channel", "Video Archive"),
                EXPERT_ID,
                full_text,
                author_name,
                author_id,
                published_at or datetime.utcnow().isoformat(),
                virtual_message_id,
                json.dumps(media_meta, ensure_ascii=False),
                0,
                0,
                0,
                0,
            )
            existing = cursor.execute(
                "SELECT post_id FROM posts WHERE telegram_message_id = ? LIMIT 1",
                (virtual_message_id,),
            ).fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE posts SET
                        channel_id = ?, channel_name = ?, expert_id = ?, message_text = ?,
                        author_name = ?, author_id = ?, created_at = ?, media_metadata = ?,
                        view_count = ?, forward_count = ?, reply_count = ?, is_forwarded = ?
                    WHERE post_id = ?
                    """,
                    (*values[:7], *values[8:], existing[0]),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO posts (
                        channel_id, channel_name, expert_id, message_text,
                        author_name, author_id, created_at, telegram_message_id, media_metadata,
                        view_count, forward_count, reply_count, is_forwarded
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            counts["segments"] += 1

        if dry_run:
            conn.rollback()
            logger.info(
                "DRY RUN: would import %d segments (%d with visual, %d frames)",
                counts["segments"], counts["with_visual"], counts["frames"],
            )
        else:
            conn.commit()
            logger.info(
                "Imported %d video segments (%d with visual, %d frames copied)",
                counts["segments"], counts["with_visual"], counts["frames"],
            )

    except Exception:
        conn.rollback()
        logger.exception("Failed to import video JSON from %s", json_path)
        raise
    finally:
        conn.close()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Path to the exported video JSON file")
    parser.add_argument("--dry-run", action="store_true", help="validate and report without writing")
    parser.add_argument(
        "--frames-base",
        default=None,
        help="base directory for relative frame paths (default: JSON directory)",
    )
    args = parser.parse_args()

    frames_base = Path(args.frames_base).expanduser().resolve() if args.frames_base else None
    try:
        counts = import_video_json(Path(args.json_path), dry_run=args.dry_run, frames_base=frames_base)
    except Exception:
        raise SystemExit(1) from None
    if args.dry_run:
        print(f"dry-run ok: {counts['segments']} segments, {counts['frames']} frames")


if __name__ == "__main__":
    main()
