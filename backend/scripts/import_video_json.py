#!/usr/bin/env python3
"""Import Video Hub JSON segments into the local SQLite database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
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


def import_video_json(json_path: Path) -> None:
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
        return

    video_url = meta.get("url", "unknown_url")
    video_title = meta.get("title", "Untitled Video")
    author_name = meta.get("author", "Unknown Expert")
    author_id = slugify(author_name)

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

        logger.info("Importing video '%s' by %s", video_title, author_name)
        count = 0

        for index, segment in enumerate(segments):
            segment_id = segment.get("segment_id", index)
            virtual_message_id = generate_virtual_id(video_url, segment_id)

            raw_topic_id = segment.get("topic_id", "general")
            url_hash = hashlib.md5(video_url.encode()).hexdigest()[:12]
            composite_topic_id = f"{url_hash}_{raw_topic_id}"

            full_text = (
                f"TITLE: {segment.get('title', '')}\n"
                f"SUMMARY: {segment.get('summary', '')}\n"
                f"---\nCONTENT:\n{segment.get('content', '')}"
            )

            media_meta = {
                "type": "video_segment",
                "video_url": (
                    f"https://www.youtube.com/watch?v={video_url}"
                    if len(video_url) < 15 and "http" not in video_url
                    else video_url
                ),
                "video_title": video_title,
                "topic_id": composite_topic_id,
                "timestamp_seconds": segment.get("timestamp_seconds", 0),
                "context_bridge": segment.get("context_bridge", ""),
                "original_author": author_name,
                "original_author_id": author_id,
            }

            cursor.execute(
                """
                INSERT OR REPLACE INTO posts (
                    channel_id, channel_name, expert_id, message_text,
                    author_name, author_id, created_at, telegram_message_id, media_metadata,
                    view_count, forward_count, reply_count, is_forwarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    CHANNEL_USERNAME,
                    meta.get("channel", "Video Archive"),
                    EXPERT_ID,
                    full_text,
                    author_name,
                    author_id,
                    datetime.utcnow().isoformat(),
                    virtual_message_id,
                    json.dumps(media_meta, ensure_ascii=False),
                    0,
                    0,
                    0,
                    0,
                ),
            )
            count += 1

        conn.commit()
        logger.info("Imported %s video segments from %s", count, json_path)

    except Exception:
        conn.rollback()
        logger.exception("Failed to import video JSON from %s", json_path)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Path to the exported video JSON file")
    args = parser.parse_args()

    try:
        import_video_json(Path(args.json_path))
    except Exception:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
