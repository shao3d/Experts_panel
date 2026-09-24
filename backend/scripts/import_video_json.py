#!/usr/bin/env python3
"""Import Video Hub JSON segments into the local SQLite database.

Supports both the legacy segment schema (title/summary/content) and the extended
schema produced by the video ingest pipeline: an optional structured `visual`
block (prompt/settings/slides) and optional `frames` references whose files are
copied under `backend/data/video_frames/<video_hash>/`.

Usage:
    python3 backend/scripts/import_video_json.py <path_to_json> [--dry-run] [--replace-video]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.utils.date_utils import (  # noqa: E402
    format_timestamp,
    to_canonical_timestamp,
)
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


def _extract_youtube_id(video_url: str) -> str | None:
    """Extract the video ID from common YouTube URL forms."""
    try:
        parsed = urlparse(video_url or "")
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate or None
    if host in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    ):
        if parsed.path == "/watch":
            values = parse_qs(parsed.query).get("v")
            if values and values[0]:
                return values[0]
        for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
            if parsed.path.startswith(prefix):
                candidate = parsed.path[len(prefix):].split("/")[0]
                return candidate or None
    return None


def canonical_video_url(video_url: str) -> str:
    """Canonicalize a YouTube URL to one identity per video.

    Virtual segment IDs and composite topic hashes derive from the URL, so
    `youtu.be/<id>` and `youtube.com/watch?v=<id>` must not produce duplicate
    segment rows. Non-YouTube URLs fall back to `normalize_video_url`.
    """
    video_id = _extract_youtube_id(video_url or "")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return normalize_video_url(video_url)


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

    Keys outside the known set (e.g. `seed`, `negative_prompt`) are rendered
    too when scalar, so future LLM-pass fields stay searchable; containers are
    skipped (they remain in `media_metadata.visual`).
    """
    lines = ["VISUAL:"]
    for key in VISUAL_TEXT_KEYS:
        value = visual.get(key)
        if value:
            lines.append(f"{key}: {value}")
    skip = set(VISUAL_TEXT_KEYS) | {"slides_verbatim", "frames_summary"}
    for key in sorted(set(visual) - skip):
        value = visual.get(key)
        if isinstance(value, bool):
            lines.append(f"{key}: {value}")
        elif isinstance(value, str | int | float):
            text = str(value).strip()
            if text:
                lines.append(f"{key}: {text}")
    slides = visual.get("slides_verbatim")
    if isinstance(slides, dict):
        for name, text in slides.items():
            if text:
                lines.append(f"slide[{name}]: {text}")
    frames = visual.get("frames_summary")
    if frames:
        lines.append(f"frames_summary: {frames}")
    return "\n".join(lines)


def _table_exists(cursor: sqlite3.Cursor, name: str) -> bool:
    return (
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )


def _load_vec_extension(conn: sqlite3.Connection) -> bool:
    """Load sqlite-vec so vec_posts rows can be maintained; warn and skip if unavailable."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        logger.warning("sqlite_vec package missing; vec_posts rows left untouched")
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        logger.warning("sqlite-vec extension unavailable; vec_posts rows left untouched")
        return False


def _invalidate_embeddings(cursor: sqlite3.Cursor, post_id: int, *, vec_ok: bool) -> None:
    """Drop stale embedding rows so the next embed run regenerates them."""
    if vec_ok and _table_exists(cursor, "vec_posts"):
        cursor.execute("DELETE FROM vec_posts WHERE post_id = ?", (post_id,))
    if _table_exists(cursor, "post_embeddings"):
        cursor.execute("DELETE FROM post_embeddings WHERE post_id = ?", (post_id,))


def find_video_post_ids(cursor: sqlite3.Cursor, canonical_url: str) -> list[int]:
    """Find existing segment rows of one video, matched by canonical URL."""
    rows = cursor.execute(
        "SELECT post_id, media_metadata FROM posts WHERE expert_id = ?",
        (EXPERT_ID,),
    ).fetchall()
    doomed = []
    for post_id, media_meta in rows:
        try:
            meta = json.loads(media_meta) if isinstance(media_meta, str) else (media_meta or {})
        except (ValueError, TypeError):
            continue
        if not isinstance(meta, dict):
            continue
        if canonical_video_url(str(meta.get("video_url", ""))) == canonical_url:
            doomed.append(post_id)
    return doomed


def delete_video_rows(cursor: sqlite3.Cursor, post_ids: list[int], *, vec_ok: bool) -> None:
    """Delete segment rows plus orphan-prone satellite rows.

    posts_fts rows are removed by the DELETE trigger; video segments carry no
    comments, but they are cleaned defensively.
    """
    for post_id in post_ids:
        _invalidate_embeddings(cursor, post_id, vec_ok=vec_ok)
        if _table_exists(cursor, "links"):
            cursor.execute(
                "DELETE FROM links WHERE source_post_id = ? OR target_post_id = ?",
                (post_id, post_id),
            )
        if _table_exists(cursor, "comments"):
            cursor.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        cursor.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))


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


def import_video_json(
    json_path: Path,
    *,
    dry_run: bool = False,
    frames_base: Path | None = None,
    replace_video: bool = False,
) -> dict:
    json_path = json_path.expanduser().resolve()
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    db_path = get_db_path()
    logger.info("Using SQLite database at %s", db_path)

    with open(json_path, encoding="utf-8") as handle:
        data = json.load(handle)

    meta = data.get("video_metadata", {})
    segments = data.get("segments", [])
    if not segments:
        logger.warning("No segments found in %s; nothing to import", json_path)
        return {"segments": 0, "frames": 0}

    video_url = canonical_video_url(meta.get("url", "unknown_url"))
    video_title = meta.get("title", "Untitled Video")
    author_name = meta.get("author", meta.get("channel", "Unknown Expert"))
    author_id = slugify(author_name)
    # Normalize the publication date once, up front: any accepted shape
    # (date-only, ISO with T, offsets) becomes canonical text so freshness
    # ranking and date filters see one format. Unparsable dates abort the
    # import — a silently wrong created_at would rank the video as "new".
    try:
        published_at = to_canonical_timestamp(
            meta.get("published_at"), field="video_metadata.published_at"
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if published_at is None:
        logger.warning(
            "video_metadata.published_at missing for %s; created_at falls back to "
            "import time, so freshness ranking treats the video as newly imported "
            "instead of its real publication date",
            video_url,
        )
    created_at_value = published_at or format_timestamp(
        datetime.now(UTC).replace(tzinfo=None)
    )
    url_hash = hashlib.md5(video_url.encode()).hexdigest()[:12]

    base_dir = frames_base or json_path.parent
    series_dir = FRAMES_ROOT / url_hash
    counts = {"segments": 0, "frames": 0, "with_visual": 0, "replaced": 0}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    vec_ok = _load_vec_extension(conn)

    try:
        if replace_video:
            doomed = find_video_post_ids(cursor, video_url)
            if dry_run:
                counts["replaced"] = len(doomed)
                logger.info(
                    "DRY RUN: would delete %d existing segment(s) of this video",
                    len(doomed),
                )
            elif doomed:
                delete_video_rows(cursor, doomed, vec_ok=vec_ok)
                counts["replaced"] = len(doomed)
                logger.info(
                    "Deleted %d existing segment(s) of this video (--replace-video)",
                    len(doomed),
                )

        cursor.execute(
            """
            INSERT OR IGNORE INTO expert_metadata (expert_id, display_name, channel_username)
            VALUES (?, ?, ?)
            """,
            (EXPERT_ID, EXPERT_NAME, CHANNEL_USERNAME),
        )

        logger.info("Importing video '%s' by %s (%s)", video_title, author_name, video_url)

        seen_virtual: dict[int, object] = {}
        for index, segment in enumerate(segments):
            segment_id = segment.get("segment_id", index)
            virtual_message_id = generate_virtual_id(video_url, segment_id)
            if virtual_message_id in seen_virtual:
                raise SystemExit(
                    f"duplicate segment identity: {segment_id!r} (index {index}) maps to "
                    f"telegram_message_id {virtual_message_id}, already used by "
                    f"{seen_virtual[virtual_message_id]!r}. Renumber segment_id values "
                    "so they are unique within this video."
                )
            seen_virtual[virtual_message_id] = segment_id

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
                media_meta["published_at"] = published_at  # canonical text
            if visual:
                media_meta["visual"] = visual
                counts["with_visual"] += 1
            if frames:
                media_meta["frames"] = frames
                counts["frames"] += len(frames)

            if dry_run:
                counts["segments"] += 1
                continue

            # One shared column->value mapping for INSERT and UPDATE; adding a
            # column cannot silently desynchronize the two statements.
            row_values = {
                "channel_id": CHANNEL_USERNAME,
                "channel_name": meta.get("channel", "Video Archive"),
                "expert_id": EXPERT_ID,
                "message_text": full_text,
                "author_name": author_name,
                "author_id": author_id,
                # Canonical naive-UTC text ("YYYY-MM-DD HH:MM:SS"): matches the
                # SQLAlchemy SQLite DATETIME rendering used by synced Telegram
                # rows, so strings compare correctly in SQL and parse back to
                # real datetimes on ORM load.
                "created_at": created_at_value,
                "telegram_message_id": virtual_message_id,
                "media_metadata": json.dumps(media_meta, ensure_ascii=False),
                "view_count": 0,
                "forward_count": 0,
                "reply_count": 0,
                "is_forwarded": 0,
                "channel_username": CHANNEL_USERNAME,
            }
            existing = cursor.execute(
                "SELECT post_id, message_text FROM posts WHERE telegram_message_id = ? LIMIT 1",
                (virtual_message_id,),
            ).fetchone()
            if existing:
                if existing[1] != full_text:
                    # Text changed: drop stale vectors so the next embed run
                    # regenerates them instead of serving outdated ones.
                    _invalidate_embeddings(cursor, existing[0], vec_ok=vec_ok)
                update_cols = [c for c in row_values if c != "telegram_message_id"]
                set_clause = ", ".join(f"{column} = ?" for column in update_cols)
                cursor.execute(
                    f"UPDATE posts SET {set_clause} WHERE post_id = ?",
                    (*[row_values[c] for c in update_cols], existing[0]),
                )
            else:
                columns = ", ".join(row_values)
                placeholders = ", ".join("?" for _ in row_values)
                cursor.execute(
                    f"INSERT INTO posts ({columns}) VALUES ({placeholders})",
                    tuple(row_values.values()),
                )
            counts["segments"] += 1

        if dry_run:
            conn.rollback()
            logger.info(
                "DRY RUN: would import %d segments (%d with visual, %d frames; %d replaced)",
                counts["segments"], counts["with_visual"], counts["frames"], counts["replaced"],
            )
        else:
            conn.commit()
            logger.info(
                "Imported %d video segments (%d with visual, %d frames copied, %d replaced)",
                counts["segments"], counts["with_visual"], counts["frames"], counts["replaced"],
            )

    except BaseException:
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
        "--replace-video",
        action="store_true",
        help="delete existing segments of the same video (matched by canonical URL, "
        "with their embeddings) before importing",
    )
    parser.add_argument(
        "--frames-base",
        default=None,
        help="base directory for relative frame paths (default: JSON directory)",
    )
    args = parser.parse_args()

    frames_base = Path(args.frames_base).expanduser().resolve() if args.frames_base else None
    try:
        counts = import_video_json(
            Path(args.json_path),
            dry_run=args.dry_run,
            frames_base=frames_base,
            replace_video=args.replace_video,
        )
    except Exception:
        raise SystemExit(1) from None
    if args.dry_run:
        print(f"dry-run ok: {counts['segments']} segments, {counts['frames']} frames")


if __name__ == "__main__":
    main()
