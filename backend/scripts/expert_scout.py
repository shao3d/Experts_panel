#!/usr/bin/env python3
"""Read-only Expert Scout corpus helper.

Gives an agentic searcher direct read-only access to the Experts Panel
corpus (SQLite): expert roster, hybrid FTS5 + vector search over posts,
and exact source lookup by source_key.

Safety:
- opens the corpus with `mode=ro` and `PRAGMA query_only=ON`;
- never writes to the corpus and never prints secrets;
- result/row caps on every command.

This helper mirrors the retrieval logic of `HybridRetrievalService`
(sanitize_fts5_query + sqlite-vec KNN + soft freshness + RRF) in a standalone
form so the scout can run without the full FastAPI stack. Consolidate later
if the scout outlives the experiment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import sqlite_vec
except ImportError:  # pragma: no cover - vector search degrades gracefully
    sqlite_vec = None


DEFAULT_LIMIT = 10
MAX_LIMIT = 30
DEFAULT_COMMENTS_LIMIT = 20
MAX_COMMENTS_LIMIT = 100
MAX_SNIPPET_CHARS = 500
VECTOR_TOP_K = 40
# Soft freshness mirrors HybridRetrievalService: linear decay over one year,
# capped at 0.7, applied to both retrievers before the RRF merge.
FRESHNESS_MAX_PENALTY = 0.7
FRESHNESS_DECAY_DAYS = 365.0


def _resolve_backend_dir() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "src").is_dir() and (candidate / "data").is_dir():
            return candidate
    raise RuntimeError("Could not resolve backend directory")


def _load_backend() -> Path:
    backend_dir = _resolve_backend_dir()
    sys.path.insert(0, str(backend_dir))
    from src.cli.bootstrap import load_backend_env

    load_backend_env(backend_dir / ".env")
    return backend_dir


def _resolve_db_path(backend_dir: Path, raw_db: str | None) -> Path:
    """Resolve the corpus path, allowing only the local dev backend data dir."""
    dev_data = (backend_dir / "data").resolve()
    if raw_db:
        candidate = Path(raw_db).resolve()
        if dev_data not in candidate.parents:
            raise SystemExit(
                f"--db must point inside {dev_data} (dev corpus only); "
                f"refusing {candidate}"
            )
        return candidate
    return dev_data / "experts.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _expert_ids(
    conn: sqlite3.Connection, experts: str | None, group: str | None = None
) -> tuple[list[str], list[str]]:
    """Resolve selected experts from an explicit list or a canonical group name.

    Returns `(known_ids, unknown_ids)`; raises `ValueError` for an unknown group.
    """
    known = {
        row[0] for row in conn.execute("SELECT expert_id FROM expert_metadata")
    }
    if group:
        from src.expert_groups import AGENT_CONTEXT_EXPERT_GROUPS, resolve_expert_group

        if group not in AGENT_CONTEXT_EXPERT_GROUPS:
            raise ValueError(
                f"unknown expert group: {group!r} "
                f"(known: {', '.join(sorted(AGENT_CONTEXT_EXPERT_GROUPS))})"
            )
        requested = resolve_expert_group(group)
        unknown = [expert_id for expert_id in requested if expert_id not in known]
        return [expert_id for expert_id in requested if expert_id in known], unknown
    if experts:
        requested = [part.strip() for part in experts.split(",") if part.strip()]
        unknown = [expert_id for expert_id in requested if expert_id not in known]
        return [expert_id for expert_id in requested if expert_id in known], unknown
    return sorted(known), []


def _cutoff_iso(recent_days: int | None) -> str | None:
    if not recent_days:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def _fts_search(
    conn: sqlite3.Connection,
    query: str,
    expert_ids: list[str],
    cutoff_iso: str | None,
    top_k: int,
) -> tuple[list[tuple[int, str, float, str | None]], str | None]:
    from src.services.fts5_retrieval_service import sanitize_fts5_query

    match_query = sanitize_fts5_query(query)
    if not match_query:
        return [], "fts_query_empty_after_sanitize"

    placeholders = ",".join("?" for _ in expert_ids)
    sql = f"""
        SELECT f.rowid AS post_id,
               snippet(posts_fts, 0, '<<', '>>', ' … ', 24) AS snip,
               f.rank AS bm25_rank,
               f.created_at
        FROM posts_fts f
        WHERE posts_fts MATCH ?
          AND f.expert_id IN ({placeholders})
    """
    params: list[Any] = [match_query, *expert_ids]
    if cutoff_iso:
        sql += " AND f.created_at >= ?"
        params.append(cutoff_iso)
    sql += " ORDER BY f.rank LIMIT ?"
    params.append(top_k)

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        return [], f"fts_error: {exc}"
    return [
        (int(pid), str(snip), float(rank), created_at)
        for pid, snip, rank, created_at in rows
    ], None


def _vector_search(
    conn: sqlite3.Connection,
    query: str,
    expert_ids: list[str],
    cutoff_iso: str | None,
    top_k: int,
) -> tuple[list[tuple[int, float, str | None]], str | None]:
    if sqlite_vec is None:
        return [], "sqlite_vec_unavailable"

    from src.services.embedding_service import get_embedding_service

    try:
        embedding = asyncio.run(get_embedding_service().embed_query(query))
    except Exception as exc:  # noqa: BLE001 - degrade to FTS-only
        return [], f"embedding_failed: {type(exc).__name__}"

    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except (AttributeError, sqlite3.OperationalError) as exc:
        return [], f"sqlite_vec_load_failed: {type(exc).__name__}"
    vector = sqlite_vec.serialize_float32(embedding)

    per_expert = top_k
    rows: list[tuple[int, float, str | None]] = []
    errors: list[str] = []
    for expert_id in expert_ids:
        sql = (
            "SELECT post_id, distance, created_at FROM vec_posts "
            "WHERE embedding MATCH ? AND k = ? AND expert_id = ?"
        )
        params: list[Any] = [vector, per_expert, expert_id]
        if cutoff_iso:
            sql += " AND created_at >= ?"
            params.append(cutoff_iso)
        try:
            rows.extend(
                (int(post_id), float(distance), created_at)
                for post_id, distance, created_at in conn.execute(sql, params).fetchall()
            )
        except sqlite3.OperationalError as exc:
            errors.append(f"{expert_id}: {exc}")
    warning = "; ".join(f"vector_partial_error: {item}" for item in errors) or None
    return rows, warning


def _parse_created_at(value: Any) -> datetime | None:
    """Parse both space-format and ISO-T timestamps; None means 'treat as old'."""
    if not value:
        return None
    text = str(value).replace("T", " ").split(".")[0]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _soft_freshness(created_at: Any, now: datetime) -> float:
    parsed = _parse_created_at(created_at)
    if parsed is None:
        return FRESHNESS_MAX_PENALTY
    age_days = max(0, (now - parsed.replace(tzinfo=timezone.utc)).days)
    return max(FRESHNESS_MAX_PENALTY, 1.0 - age_days / FRESHNESS_DECAY_DAYS)


def _rank_fts(
    fts_rows: list[tuple[int, str, float, str | None]], now: datetime
) -> list[int]:
    """Rescore BM25 rows with soft freshness, return post_ids best-first.

    Mirrors HybridRetrievalService: norm_rank in [0,1] -> base 0.3..1.0,
    multiplied by soft freshness.
    """
    if not fts_rows:
        return []
    max_rank = max((abs(rank) for _, _, rank, _ in fts_rows), default=1) or 1
    scored = [
        (post_id, (abs(rank) / max_rank * 0.7 + 0.3) * _soft_freshness(created_at, now))
        for post_id, _, rank, created_at in fts_rows
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [post_id for post_id, _ in scored]


def _rank_vector(
    vector_rows: list[tuple[int, float, str | None]], now: datetime
) -> list[int]:
    """Rescore distance rows with soft freshness, return post_ids best-first."""
    scored = [
        (post_id, max(0.0, 1.0 - distance) * _soft_freshness(created_at, now))
        for post_id, distance, created_at in vector_rows
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [post_id for post_id, _ in scored]


def _rrf_merge(fts_ids: list[int], vector_ids: list[int], k: int) -> list[int]:
    scores: dict[int, float] = {}
    for rank, post_id in enumerate(fts_ids):
        scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, post_id in enumerate(vector_ids):
        scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda pid: scores[pid], reverse=True)


def _video_fields(media_metadata: Any) -> dict[str, Any]:
    """Expose deep-link fields for synthetic video segments.

    Video Hub posts carry `video_url` and `timestamp_seconds` in
    `media_metadata`; surfacing them lets Scout cite an exact moment instead of
    just a source_key.
    """
    if not media_metadata:
        return {}
    try:
        meta = json.loads(media_metadata) if isinstance(media_metadata, str) else media_metadata
    except (ValueError, TypeError):
        return {}
    if not isinstance(meta, dict) or meta.get("type") != "video_segment":
        return {}

    fields: dict[str, Any] = {}
    url = meta.get("video_url")
    timestamp = meta.get("timestamp_seconds")
    if url:
        fields["video_url"] = url
        if timestamp is not None:
            try:
                seconds = int(float(timestamp))
            except (ValueError, TypeError):
                seconds = None
            if seconds is not None:
                fields["video_timestamp_s"] = seconds
                separator = "&" if "?" in url else "?"
                fields["video_link"] = f"{url}{separator}t={seconds}s"
        if "video_link" not in fields:
            fields["video_link"] = url
    if meta.get("video_title"):
        fields["video_title"] = meta["video_title"]
    return fields


def _fetch_posts(conn: sqlite3.Connection, post_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not post_ids:
        return {}
    placeholders = ",".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT post_id, expert_id, telegram_message_id, channel_username,
               created_at, author_name, message_text, media_metadata
        FROM posts WHERE post_id IN ({placeholders})
        """,
        post_ids,
    ).fetchall()
    result: dict[int, dict[str, Any]] = {}
    for (
        post_id,
        expert_id,
        telegram_message_id,
        channel_username,
        created_at,
        author_name,
        message_text,
        media_metadata,
    ) in rows:
        result[int(post_id)] = {
            "source_key": f"{expert_id}:{telegram_message_id}",
            "expert_id": expert_id,
            "telegram_message_id": telegram_message_id,
            "channel_username": channel_username,
            "created_at": created_at,
            "author_name": author_name,
            "message_text": message_text or "",
            **_video_fields(media_metadata),
        }
    return result


def _excerpt(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def cmd_experts(args: argparse.Namespace) -> int:
    backend_dir = _load_backend()
    from src.expert_groups import groups_for_expert

    db_path = _resolve_db_path(backend_dir, args.db)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT em.expert_id, em.display_name, em.channel_username,
                   COUNT(p.post_id)
            FROM expert_metadata em
            LEFT JOIN posts p ON p.expert_id = em.expert_id
            GROUP BY em.expert_id
            ORDER BY em.expert_id
            """
        ).fetchall()
    payload = [
        {
            "expert_id": expert_id,
            "display_name": display_name,
            "channel_username": channel_username,
            "posts_count": count,
            "groups": groups_for_expert(expert_id),
        }
        for expert_id, display_name, channel_username, count in rows
    ]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in payload:
            groups = f" [{'/'.join(item['groups'])}]" if item["groups"] else ""
            print(
                f"{item['expert_id']:<18} {item['posts_count']:>5} posts  "
                f"{item['display_name']} (@{item['channel_username']}){groups}"
            )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    if not args.query.strip():
        print("error: query must not be empty", file=sys.stderr)
        return 2
    backend_dir = _load_backend()
    from src import config

    db_path = _resolve_db_path(backend_dir, args.db)
    limit = max(1, min(args.limit, MAX_LIMIT))
    cutoff = _cutoff_iso(args.recent_days)

    with _connect(db_path) as conn:
        try:
            expert_ids, unknown_experts = _expert_ids(conn, args.experts, args.group)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        warnings: list[str] = []
        if unknown_experts:
            warnings.append(f"unknown_experts: {','.join(unknown_experts)}")
        if not expert_ids:
            warnings.append("no_known_experts_selected")
        now = datetime.now(timezone.utc)
        fts_rows, fts_warning = _fts_search(conn, args.query, expert_ids, cutoff, limit * 3)
        if fts_warning:
            warnings.append(fts_warning)
        vector_rows: list[tuple[int, float, str | None]] = []
        if args.no_vector:
            warnings.append("vector_skipped_by_flag")
        else:
            vector_rows, vector_warning = _vector_search(
                conn, args.query, expert_ids, cutoff, VECTOR_TOP_K
            )
            if vector_warning:
                warnings.append(vector_warning)

        fts_ids = _rank_fts(fts_rows, now)
        vector_ids = _rank_vector(vector_rows, now)[:VECTOR_TOP_K]
        merged = _rrf_merge(fts_ids, vector_ids, config.HYBRID_RRF_K)[:limit]
        posts = _fetch_posts(conn, merged)

    fts_snippets = {post_id: snip for post_id, snip, _, _ in fts_rows}
    found_by: dict[int, list[str]] = {}
    for post_id in fts_ids:
        found_by.setdefault(post_id, []).append("fts")
    for post_id in vector_ids:
        found_by.setdefault(post_id, []).append("vector")

    results = []
    for post_id in merged:
        post = posts.get(post_id)
        if not post:
            continue
        snippet = fts_snippets.get(post_id) or _excerpt(post["message_text"])
        item = {
            "source_key": post["source_key"],
            "expert_id": post["expert_id"],
            "created_at": post["created_at"],
            "channel_username": post["channel_username"],
            "found_by": found_by.get(post_id, []),
            "chars": len(post["message_text"]),
            "snippet": snippet,
        }
        for key in ("video_link", "video_url", "video_timestamp_s", "video_title"):
            if key in post:
                item[key] = post[key]
        results.append(item)

    if args.json:
        print(json.dumps({"query": args.query, "warnings": warnings, "results": results}, ensure_ascii=False, indent=2))
    else:
        if warnings:
            print(f"# warnings: {'; '.join(warnings)}")
        for item in results:
            print(
                f"- {item['source_key']} [{item['created_at']}] "
                f"({'+'.join(item['found_by'])}, {item['chars']} chars)\n"
                f"  {item['snippet']}"
            )
            if item.get("video_link"):
                print(f"  video: {item['video_link']}")
    return 0


def _parse_source_key(raw: str) -> tuple[str, int]:
    expert_id, _, message_id = raw.partition(":")
    if not expert_id or not message_id.isdigit():
        raise ValueError(f"invalid source_key: {raw!r} (expected expert:message_id)")
    return expert_id, int(message_id)


def _collect_show_payload(
    conn: sqlite3.Connection, raw_keys: list[str], comments_limit: int
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for raw_key in raw_keys:
        try:
            expert_id, message_id = _parse_source_key(raw_key)
        except ValueError as exc:
            payload.append({"source_key": raw_key, "error": str(exc)})
            continue
        row = conn.execute(
            """
            SELECT post_id, expert_id, telegram_message_id, channel_username,
                   created_at, author_name, author_id, message_text,
                   reply_count, view_count, media_metadata
            FROM posts WHERE expert_id = ? AND telegram_message_id = ?
            """,
            (expert_id, message_id),
        ).fetchone()
        if row is None:
            payload.append({"source_key": raw_key, "error": "not_found"})
            continue
        (
            post_id,
            _expert_id,
            _message_id,
            channel_username,
            created_at,
            author_name,
            author_id,
            message_text,
            reply_count,
            view_count,
            media_metadata,
        ) = row
        # Posts store "channelXXX", comments store "XXX" (same normalization
        # as CommentGroupMapService._load_main_source_author_comments).
        post_author_id = author_id.replace("channel", "") if author_id else None
        # Author replies are fetched outside the chronological window so they
        # are not crowded out on high-traffic posts.
        author_comments: list[tuple[Any, ...]] = []
        if post_author_id:
            author_comments = conn.execute(
                """
                SELECT comment_text, author_name, author_id, created_at
                FROM comments WHERE post_id = ? AND author_id = ?
                ORDER BY created_at
                LIMIT ?
                """,
                (post_id, post_author_id, comments_limit),
            ).fetchall()
        community_comments = conn.execute(
            """
            SELECT comment_text, author_name, author_id, created_at
            FROM comments
            WHERE post_id = ?
              AND (? IS NULL OR author_id IS NULL OR author_id <> ?)
            ORDER BY created_at
            LIMIT ?
            """,
            (post_id, post_author_id, post_author_id, comments_limit),
        ).fetchall()
        comments = [
            {
                "text": text,
                "author": name,
                "created_at": created,
                "is_author": bool(post_author_id) and comment_author_id == post_author_id,
            }
            for text, name, comment_author_id, created in sorted(
                [*author_comments, *community_comments], key=lambda item: item[3]
            )
        ]
        linked = conn.execute(
            """
            SELECT p.expert_id, p.telegram_message_id, p.created_at,
                   substr(p.message_text, 1, 160)
            FROM links l JOIN posts p ON p.post_id = l.target_post_id
            WHERE l.source_post_id = ?
            LIMIT 10
            """,
            (post_id,),
        ).fetchall()
        payload.append(
            {
                "source_key": f"{expert_id}:{message_id}",
                "channel_username": channel_username,
                "created_at": created_at,
                "author_name": author_name,
                "reply_count": reply_count,
                "view_count": view_count,
                "content": message_text,
                **_video_fields(media_metadata),
                "comments": comments,
                "linked_context": [
                    {
                        "source_key": f"{expert}:{mid}",
                        "created_at": created,
                        "excerpt": excerpt,
                    }
                    for expert, mid, created, excerpt in linked
                ],
            }
        )
    return payload


def cmd_show(args: argparse.Namespace) -> int:
    backend_dir = _load_backend()
    db_path = _resolve_db_path(backend_dir, args.db)
    comments_limit = max(1, min(args.comments_limit, MAX_COMMENTS_LIMIT))

    with _connect(db_path) as conn:
        payload = _collect_show_payload(conn, args.source_keys, comments_limit)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in payload:
            if "error" in item:
                print(f"# {item['source_key']}: {item['error']}")
                continue
            print(f"=== {item['source_key']} [{item['created_at']}] @{item['channel_username']} ===")
            if item.get("video_link"):
                print(f"video: {item['video_link']}")
            print(item["content"])
            author_comments = [c for c in item["comments"] if c["is_author"]]
            community_comments = [c for c in item["comments"] if not c["is_author"]]
            print(f"--- author comments ({len(author_comments)}) ---")
            for comment in author_comments:
                print(f"  [{comment['created_at']}] {comment['text']}")
            print(f"--- community comments ({len(community_comments)}) ---")
            for comment in community_comments:
                print(f"  [{comment['created_at']}] {comment['author']}: {comment['text']}")
            if item["linked_context"]:
                print(f"--- linked context ({len(item['linked_context'])}) ---")
                for link in item["linked_context"]:
                    print(f"  {link['source_key']} [{link['created_at']}]: {link['excerpt']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expert-scout",
        description="Read-only Expert Scout corpus helper (FTS5 + vector + source lookup).",
    )
    parser.add_argument("--db", help="Path to experts.db (default: backend/data/experts.db)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    experts = subparsers.add_parser("experts", help="List experts and post counts")
    experts.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    search = subparsers.add_parser("search", help="Hybrid FTS5 + vector search over posts")
    search.add_argument("query", help="Search query (natural language or keywords)")
    selection = search.add_mutually_exclusive_group()
    selection.add_argument("--experts", help="Comma-separated expert_id subset (default: all)")
    selection.add_argument(
        "--group",
        help="Canonical group name (tech, tech_business, visual); resolved from src/expert_groups.py",
    )
    search.add_argument("--recent-days", type=int, default=None, help="Only posts newer than N days")
    search.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max results (default {DEFAULT_LIMIT}, max {MAX_LIMIT})")
    search.add_argument("--no-vector", action="store_true", help="FTS5 only, skip embeddings")
    search.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    show = subparsers.add_parser("show", help="Show full source(s) with comments and linked context")
    show.add_argument("source_keys", nargs="+", help="source_key values like refat:238")
    show.add_argument("--comments-limit", type=int, default=DEFAULT_COMMENTS_LIMIT, help=f"Max comments per window (author / community) per source (default {DEFAULT_COMMENTS_LIMIT})")
    show.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "experts":
        return cmd_experts(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "show":
        return cmd_show(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
