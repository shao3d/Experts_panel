#!/usr/bin/env python3
"""Read-only channel audit for VideoHub: uploads x staging DB x admission log.

Purpose: answer "what is on this channel, what do we have, what is pending and
what has no recorded verdict" in one command, keyed by the YouTube channel id
(not by the author label — one channel may be labelled differently in old rows).

Usage:
  backend/.venv/bin/python backend/scripts/channel_audit.py UCG0sRL6J1x62Y-FQTrJmP1w
  backend/.venv/bin/python backend/scripts/channel_audit.py https://www.youtube.com/@noisygroup
  backend/.venv/bin/python backend/scripts/channel_audit.py --channel UCG0sRL6J1x62Y-FQTrJmP1w --json

Sources (read-only):
  * channel uploads: YouTube RSS feed (latest 15, with exact publish dates);
    `--ytdlp` additionally walks the full /videos tab through the WARP proxy.
  * corpus: staging `backend/data/experts.db` (video_hub segments only).
  * decisions: `output/video_admission/admission_log.json`.

Exit codes: 0 = report printed; 1 = technical failure (network/parse);
2 = `--strict` and some upload has no admission record or no DB entry.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

DEFAULT_DB = REPO_ROOT / "backend" / "data" / "experts.db"
DEFAULT_LOG = REPO_ROOT / "output" / "video_admission" / "admission_log.json"
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
ATOM = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def resolve_channel_id(target: str) -> str:
    """Accept a channel id, a /channel/ URL, or a handle URL/handle."""
    match = re.search(r"(UC[\w-]{22})", target)
    if match:
        return match.group(1)
    if target.startswith("@") or "/@" in target:
        url = target if target.startswith("http") else f"https://www.youtube.com/{target}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed youtube host
                page = response.read().decode("utf-8", "replace")
        except OSError as exc:
            raise SystemExit(f"cannot resolve {target}: {exc}") from exc
        match = re.search(r'"channelId":"(UC[\w-]{22})"', page)
        if match:
            return match.group(1)
        raise SystemExit(f"channel id not found on {url}")
    raise SystemExit("pass a channel id (UC...), a /channel/UC... or a @handle URL")


def fetch_rss(channel_id: str, timeout: int = 30) -> list[dict]:
    request = urllib.request.Request(RSS_URL.format(channel_id=channel_id), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed youtube host
        root = ElementTree.fromstring(response.read())
    uploads = []
    for entry in root.findall("a:entry", ATOM):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ATOM)
        if not video_id:
            continue
        uploads.append(
            {
                "video_id": video_id,
                "title": entry.findtext("a:title", default="", namespaces=ATOM),
                "published_at": (entry.findtext("a:published", default="", namespaces=ATOM) or "")[:10],
            }
        )
    return uploads


def fetch_ytdlp(channel_id: str, proxy: str | None) -> list[dict]:
    """Full /videos tab walk (needs network that YouTube accepts, e.g. WARP)."""
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    command = ["yt-dlp", "--flat-playlist", "-J", url]
    if proxy:
        command[1:1] = ["--proxy", proxy]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode != 0:
        raise SystemExit(f"yt-dlp failed: {result.stderr.strip().splitlines()[-1] if result.stderr else 'unknown error'}")
    payload = json.loads(result.stdout)
    return [
        {"video_id": entry.get("id", ""), "title": entry.get("title", ""), "published_at": ""}
        for entry in payload.get("entries") or []
        if entry.get("id")
    ]


def load_corpus(db_path: Path) -> dict[str, int]:
    """video_id -> segment count, staging corpus only, read-only."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT json_extract(media_metadata,'$.video_url'), count(*) FROM posts "
            "WHERE expert_id='video_hub' AND media_metadata IS NOT NULL GROUP BY 1"
        )
        counts: dict[str, int] = {}
        for url, count in rows:
            match = re.search(r"[?&]v=([\w-]{11})", url or "")
            if match:
                counts[match.group(1)] = count
        return counts
    finally:
        connection.close()


def load_log(log_path: Path) -> dict[str, dict]:
    if not log_path.exists():
        return {}
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    return {entry["video_id"]: entry for entry in payload.get("videos", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="channel id, /channel/UC... url or @handle url")
    parser.add_argument("--channel", help="alias for the positional channel id")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="exit 2 on gaps")
    parser.add_argument("--ytdlp", action="store_true", help="walk the full /videos tab instead of the RSS window")
    parser.add_argument("--proxy", default="socks5h://127.0.0.1:40000", help="proxy for --ytdlp")
    args = parser.parse_args()

    target = args.channel or args.target
    if not target:
        parser.error("pass a channel id (UC...) or a @handle url")
    channel_id = resolve_channel_id(target)
    uploads = fetch_ytdlp(channel_id, args.proxy) if args.ytdlp else fetch_rss(channel_id)
    corpus = load_corpus(Path(args.db))
    log = load_log(Path(args.log))

    rows = []
    for upload in uploads:
        video_id = upload["video_id"]
        entry = log.get(video_id, {})
        in_db = video_id in corpus
        verdict = entry.get("verdict")
        row = {
            "video_id": video_id,
            "title": upload["title"] or entry.get("title", ""),
            "published_at": upload["published_at"] or entry.get("published_at") or "",
            "in_corpus": in_db,
            "segments": corpus.get(video_id, 0),
            "verdict": verdict,
            "queue_status": entry.get("queue_status"),
            "has_record": bool(entry),
            "state": "ok" if (in_db or verdict) else "NO VERDICT",
        }
        if in_db and verdict not in {"ingest", "ingest_scoped"}:
            row["state"] = "STATE MISMATCH (in corpus, verdict=%s)" % (verdict,)
        rows.append(row)

    rows.sort(key=lambda item: item["published_at"], reverse=True)
    gaps = [row for row in rows if not row["has_record"]]

    if args.json:
        print(json.dumps({"channel_id": channel_id, "uploads": rows, "gaps": len(gaps)}, ensure_ascii=False, indent=1))
    else:
        print(f"channel: {channel_id}")
        print(f"uploads: {len(rows)} | in corpus: {sum(r['in_corpus'] for r in rows)} | with verdict: {sum(r['has_record'] for r in rows)} | gaps: {len(gaps)}")
        print()
        print(f"{'video_id':12} {'published':10} {'db':>3} {'seg':>4}  {'verdict':12} {'queue':22} title")
        for row in rows:
            print(
                f"{row['video_id']:12} {row['published_at']:10} {'yes' if row['in_corpus'] else 'no':>3} "
                f"{row['segments']:>4}  {(row['verdict'] or '—'):12} {(row['queue_status'] or '—'):22} {row['title'][:60]}"
            )
        if gaps:
            print("\nwithout a recorded verdict:")
            for row in gaps:
                print(f"  {row['video_id']}  {row['title'][:70]}")

    return 2 if (args.strict and gaps) else 0


if __name__ == "__main__":
    raise SystemExit(main())
