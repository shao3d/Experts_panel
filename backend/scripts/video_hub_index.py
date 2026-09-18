#!/usr/bin/env python3
"""Read-only VideoHub index: what videos are in the corpus, grouped by author.

Usage:
  backend/.venv/bin/python backend/scripts/video_hub_index.py            # print index
  backend/.venv/bin/python backend/scripts/video_hub_index.py --write    # update docs/video-hub-index.md
  backend/.venv/bin/python backend/scripts/video_hub_index.py --check <youtube_url|youtube_id>

--check exit codes: 0 = not found (free to ingest), 10 = already in VideoHub.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))
from scripts.import_video_json import canonical_video_url, find_video_post_ids  # noqa: E402

DEFAULT_DB = REPO_ROOT / "backend" / "data" / "experts.db"
DEFAULT_INDEX = REPO_ROOT / "docs" / "video-hub-index.md"


def load_videos(conn: sqlite3.Connection) -> dict[str, dict]:
    """Collect one record per video (canonical URL), counting its segments."""
    videos: dict[str, dict] = {}
    for _post_id, meta_raw in conn.execute("SELECT post_id, media_metadata FROM posts"):
        if not meta_raw:
            continue
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        except (ValueError, TypeError):
            continue
        if not isinstance(meta, dict) or meta.get("type") != "video_segment":
            continue
        url = canonical_video_url(str(meta.get("video_url", "")))
        rec = videos.setdefault(
            url,
            {
                "title": meta.get("video_title", ""),
                "author": meta.get("original_author") or meta.get("channel_name") or "Unknown",
                "published": str(meta.get("published_at") or "")[:10],
                "segments": 0,
            },
        )
        rec["segments"] += 1
    return videos


def _video_id(url: str) -> str:
    return url.rsplit("v=", 1)[-1] if "v=" in url else url


def render_index(videos: dict[str, dict], db_path: Path) -> str:
    lines = [
        "# VideoHub Index",
        "",
        "Автогенерация: `backend/.venv/bin/python backend/scripts/video_hub_index.py --write`",
        "Проверка дубликата перед ingest: `backend/.venv/bin/python backend/scripts/video_hub_index.py --check <url|id>`",
        f"Источник: `{db_path}` (staging-БД; после data release совпадает с продом).",
        "",
    ]
    by_author: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for url, rec in videos.items():
        by_author[rec["author"]].append((url, rec))
    for author in sorted(by_author):
        lines += [
            f"## {author}",
            "",
            "| YouTube ID | Название | Сегментов | Опубликовано |",
            "|---|---|---:|---|",
        ]
        for url, rec in sorted(by_author[author], key=lambda item: item[1]["published"], reverse=True):
            lines.append(
                f"| `{_video_id(url)}` | {rec['title']} | {rec['segments']} | {rec['published']} |"
            )
        lines.append("")
    total = sum(rec["segments"] for rec in videos.values())
    lines.append(f"Итого: **{len(videos)}** видео, **{total}** сегментов.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite path (read-only)")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="index file path")
    parser.add_argument("--write", action="store_true", help="rewrite the index file")
    parser.add_argument("--check", metavar="URL_OR_ID", help="duplicate check for one video")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        if args.check:
            query = args.check if "://" in args.check else f"https://youtu.be/{args.check}"
            canonical = canonical_video_url(query)
            ids = find_video_post_ids(conn.cursor(), canonical)
            rec = load_videos(conn).get(canonical)
            if ids and rec:
                print(
                    f"DUPLICATE | {rec['author']} | {rec['title']} | "
                    f"{len(ids)} сегм. | опубликовано {rec['published']}"
                )
                return 10
            print("FREE | не найдено в VideoHub — можно брать в работу")
            return 0
        videos = load_videos(conn)
    finally:
        conn.close()

    text = render_index(videos, args.db)
    if args.write:
        args.index.write_text(text, encoding="utf-8")
        print(f"written: {args.index}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
