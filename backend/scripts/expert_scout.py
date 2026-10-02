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
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import sqlite_vec
except ImportError:  # pragma: no cover - vector search degrades gracefully
    sqlite_vec = None


DEFAULT_LIMIT = 20
MAX_LIMIT = 40
# Candidate fetch depth is constant (not tied to the output limit): BM25
# rescoring normalizes over the fetched set, so a limit-dependent depth would
# reshuffle the top-10 whenever the caller asks for a wider pool.
FTS_CANDIDATES = 90
DEFAULT_COMMENTS_LIMIT = 20
MAX_COMMENTS_LIMIT = 100
MAX_SNIPPET_CHARS = 500
VECTOR_TOP_K = 40
MAX_EXPAND_NEIGHBORS = 5
MAX_DIGEST_WINDOW = 30
MAX_DIGEST_TEXT = 400
MAX_DIGEST_CHARS = 12000
MAX_SHOW_CHARS = 8000
MAX_SHOW_KEYS = 3
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

    from src.services.embedding_service import EmbeddingService

    try:
        # Leave time for FTS results to return before the tool's 120s timeout.
        # The ingestion service keeps its default, longer retry policy.
        service = EmbeddingService(request_timeout=15, max_retry_attempts=2)
        embedding = asyncio.run(service.embed_query(query))
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
    """Parse stored timestamps (space/ISO-T/date-only); None means 'treat as old'.

    Date-only values ("2026-08-07") are midnight of that day: ingest artifacts
    sometimes carry bare dates, and treating those rows as maximally old would
    punish the freshest videos in freshness ranking.
    """
    from src.utils.date_utils import parse_timestamp

    return parse_timestamp(value)


def _parse_now(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    from src.utils.date_utils import parse_timestamp

    parsed = parse_timestamp(raw)
    if parsed is None:
        raise ValueError(f"invalid --now timestamp: {raw!r}")
    return parsed.replace(tzinfo=timezone.utc)


def _soft_freshness(created_at: Any, now: datetime, freshness: str = "tool") -> float:
    if freshness in ("craft", "any"):
        return 1.0
    parsed = _parse_created_at(created_at)
    if parsed is None:
        return FRESHNESS_MAX_PENALTY
    age_days = max(0, (now - parsed.replace(tzinfo=timezone.utc)).days)
    return max(FRESHNESS_MAX_PENALTY, 1.0 - age_days / FRESHNESS_DECAY_DAYS)


def _rank_fts(
    fts_rows: list[tuple[int, str, float, str | None]], now: datetime, freshness: str = "tool"
) -> list[int]:
    """Rescore BM25 rows with soft freshness, return post_ids best-first.

    Mirrors HybridRetrievalService: norm_rank in [0,1] -> base 0.3..1.0,
    multiplied by soft freshness. `freshness="craft"`/`"any"` disables the
    age penalty for durable craft knowledge (recency trap).
    """
    if not fts_rows:
        return []
    max_rank = max((abs(rank) for _, _, rank, _ in fts_rows), default=1) or 1
    scored = [
        (post_id, (abs(rank) / max_rank * 0.7 + 0.3) * _soft_freshness(created_at, now, freshness))
        for post_id, _, rank, created_at in fts_rows
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [post_id for post_id, _ in scored]


def _rank_vector(
    vector_rows: list[tuple[int, float, str | None]], now: datetime, freshness: str = "tool"
) -> list[int]:
    """Keep the calibrated freshness score; break ties by vector distance.

    L2 distances can exceed one. Their clamped score must not let the order
    of expert partitions decide relevance. Changing the score scale itself
    regressed measured retrieval, so distance only resolves equal scores.
    """
    scored = [
        (post_id, max(0.0, 1.0 - distance) * _soft_freshness(created_at, now, freshness), distance)
        for post_id, distance, created_at in vector_rows
    ]
    scored.sort(key=lambda item: (-item[1], item[2]))
    return [post_id for post_id, _, _ in scored]


def _rrf_merge(fts_ids: list[int], vector_ids: list[int], k: int) -> list[int]:
    scores: dict[int, float] = {}
    for rank, post_id in enumerate(fts_ids):
        scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, post_id in enumerate(vector_ids):
        scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda pid: scores[pid], reverse=True)


def _candidate_pool(fts_ids: list[int], vector_ids: list[int], vector_rows: list[tuple], k: int) -> list[int]:
    """Keep the measured first page; never discard the other fetched candidates.

    Vector similarity is a source of additional leads, not a veto on textual
    matches. The remaining per-expert KNN candidates are also walkable.
    """
    primary = _rrf_merge(fts_ids, vector_ids, k)
    vector_tail = [pid for pid, _, _ in sorted(vector_rows, key=lambda row: row[1])]
    return list(dict.fromkeys([*primary, *vector_tail]))


DIVERSITY_CAP_TOP = 6
DIVERSITY_CAP_REST = 10


def diversify(
    merged_ids: list[int], expert_by_post: dict[int, str], top_k: int = 10
) -> list[int]:
    """Anti-monoculture reorder: no more than N posts per expert in the top
    window, while other experts' candidates exist. Relative order is kept for
    items that fit the cap; overflow is deferred to the tail of the list.
    """
    counts: dict[tuple[str, int], int] = {}
    taken: list[int] = []
    deferred: list[int] = []
    for index, post_id in enumerate(merged_ids):
        expert = expert_by_post.get(post_id, "?")
        window = 0 if index < top_k else 1
        cap = DIVERSITY_CAP_TOP if window == 0 else DIVERSITY_CAP_REST
        if counts.get((expert, window), 0) < cap:
            counts[(expert, window)] = counts.get((expert, window), 0) + 1
            taken.append(post_id)
        else:
            deferred.append(post_id)
    return taken + deferred


def leg_stats(fts_ids: list[int], vector_ids: list[int]) -> dict[str, Any]:
    """Hybrid leg telemetry: a dead leg (overlap ~ 0) fails silently without it."""
    fts_set, vec_set = set(fts_ids), set(vector_ids)
    overlap = fts_set & vec_set
    union = fts_set | vec_set
    jaccard = (len(overlap) / len(union)) if union else 0.0
    return {
        "fts_ranked": len(fts_ids),
        "vector_ranked": len(vector_ids),
        "overlap": len(overlap),
        "jaccard": round(jaccard, 4),
    }


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
    from src.utils.video_identity import youtube_id
    fields.update(
        video_id=youtube_id(url or ""),
        timestamp_kind=meta.get("timestamp_kind", "keyframe"),
        coverage="unknown" if not meta.get("scope") else "declared_scope",
        segment_start_s=meta.get("start_seconds"),
        segment_end_s=meta.get("end_seconds"),
        coverage_note="Keyframes are navigation points, not interval boundaries. Do not infer missing time ranges or continuous coverage from their spacing.",
    )
    if meta.get("context_bridge"):
        fields["editorial_context_bridge"] = meta["context_bridge"]
    for name in ("original_author", "published_at", "duration_seconds", "scope", "scope_range_s", "segment_id"):
        if name in meta:
            fields[name] = meta[name]
    return fields


def _video_posts(conn: sqlite3.Connection, video_id: str | None = None) -> list[dict]:
    """A small read-only catalog; no new index or database migration."""
    ids = [r[0] for r in conn.execute("SELECT post_id FROM posts WHERE expert_id='video_hub'")]
    posts = _fetch_posts(conn, ids).values()
    return sorted((p for p in posts if p.get("video_id") and (not video_id or p["video_id"] == video_id)),
                  key=lambda p: (p.get("video_timestamp_s", 0), p["telegram_message_id"]))


def cmd_videos(args: argparse.Namespace) -> int:
    with _connect(_resolve_db_path(_load_backend(), args.db)) as conn:
        posts = _video_posts(conn, args.video_id)
    videos: dict[str, dict] = {}
    for post in posts:
        record = videos.setdefault(post["video_id"], {
            "video_id": post["video_id"], "title": post.get("video_title"),
            "author": post.get("original_author") or post["author_name"],
            "published_at": post.get("published_at") or post["created_at"],
            "scope": post.get("scope"), "scope_range_s": post.get("scope_range_s"),
            "coverage": post.get("coverage", "unknown"), "timestamp_kind": post.get("timestamp_kind"),
            "segment_count": 0, "first_keyframe_s": post.get("video_timestamp_s"),
            "last_keyframe_s": post.get("video_timestamp_s"),
            "coverage_note": post.get("coverage_note"),
        })
        record["segment_count"] += 1
        record["last_keyframe_s"] = post.get("video_timestamp_s")
    offset = max(0, args.cursor or 0)
    ordered = sorted(videos.values(), key=lambda v: v["video_id"])
    selected = ordered[offset:offset + MAX_DIGEST_WINDOW]
    payload = {"status": "completed", "videos": selected, "total_videos": len(ordered),
               "next_cursor": offset + len(selected) if offset + len(selected) < len(ordered) else None,
               "note": "Keyframes are navigation points. They do not prove segment boundaries or continuous coverage."}
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


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
        try:
            now = _parse_now(args.now)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        fts_rows, fts_warning = _fts_search(conn, args.query, expert_ids, cutoff, FTS_CANDIDATES)
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

        fts_ids = _rank_fts(fts_rows, now, args.freshness)
        vector_ids = _rank_vector(vector_rows, now, args.freshness)[:VECTOR_TOP_K]
        pool = _candidate_pool(fts_ids, vector_ids, vector_rows, config.HYBRID_RRF_K)
        offset = max(0, getattr(args, "cursor", 0))
        merged = pool[offset:offset+limit]
        posts = _fetch_posts(conn, pool if getattr(args, "diversity", False) else merged)

    fts_snippets = {post_id: snip for post_id, snip, _, _ in fts_rows}
    # Anti-monoculture: only meaningful when the scope spans several experts.
    if len(expert_ids) > 1 and getattr(args, "diversity", False) and merged:
        expert_by_post = {pid: p["expert_id"] for pid, p in posts.items()}
        pool = diversify(pool, expert_by_post)
        merged = pool[offset:offset+limit]
    found_by: dict[int, list[str]] = {}
    for post_id in fts_ids:
        found_by.setdefault(post_id, []).append("fts")
    for post_id, _, _ in vector_rows:
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
        item["author_name"] = post["author_name"]
        item.update({key: value for key, value in post.items() if key in {
            "video_id", "original_author", "timestamp_kind", "coverage", "scope", "scope_range_s",
            "segment_start_s", "segment_end_s", "published_at", "duration_seconds",
        }})
        results.append(item)

    if args.json:
        degraded = any(w != "vector_skipped_by_flag" for w in warnings)
        # Search cards select what to read. Links and interval metadata belong
        # to show, which is still required before citing a primary source.
        card_fields = {
            "source_key", "author_name", "created_at", "found_by", "chars", "snippet",
            "video_id", "video_title", "video_timestamp_s", "published_at",
            "scope", "coverage", "timestamp_kind",
        }
        results = [{key: value for key, value in item.items() if key in card_fields}
                   for item in results]
        print(json.dumps({"status": "partial" if degraded else "completed", "query": args.query, "warnings": warnings,
                          "retrieval_stats": leg_stats(fts_ids, vector_ids), "candidate_pool_size": len(pool),
                          "next_cursor": offset + len(merged) if offset + len(merged) < len(pool) else None,
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        if warnings:
            print(f"# warnings: {'; '.join(warnings)}")
        stats = leg_stats(fts_ids, vector_ids)
        print(f"# legs: fts={stats['fts_ranked']} vec={stats['vector_ranked']} overlap={stats['overlap']} jaccard={stats['jaccard']}")
        print(f"# candidates={len(pool)} offset={offset} next_cursor={offset+len(merged) if offset+len(merged)<len(pool) else None}")
        for item in results:
            print(
                f"- {item['source_key']} [{item['created_at']}] "
                f"({'+'.join(item['found_by'])}, {item['chars']} chars)\n"
                f"  {item['snippet']}"
            )
            if item.get("video_link"):
                print(f"  video: {item['video_link']}")
                print(f"  author={item['author_name']}; video_id={item.get('video_id')}; timestamp_kind=keyframe; coverage={item.get('coverage')}")
    return 0


def _parse_source_key(raw: str) -> tuple[str, int]:
    expert_id, _, message_id = raw.partition(":")
    if not expert_id or not message_id.isdigit():
        raise ValueError(f"invalid source_key: {raw!r} (expected expert:message_id)")
    return expert_id, int(message_id)


def _collect_show_payload(
    conn: sqlite3.Connection, raw_keys: list[str], comments_limit: int, expand: int = 0
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
        neighbors: list[dict[str, Any]] = []
        if expand > 0 and not _video_fields(media_metadata):
            n = min(expand, MAX_EXPAND_NEIGHBORS)
            for side_sql, side_params in (
                (
                    "SELECT expert_id, telegram_message_id, created_at, "
                    "substr(message_text, 1, 200) FROM posts WHERE expert_id = ? AND "
                    "(created_at < ? OR (created_at = ? AND post_id < ?)) "
                    "ORDER BY created_at DESC, post_id DESC LIMIT ?",
                    (expert_id, created_at, created_at, post_id, n),
                ),
                (
                    "SELECT expert_id, telegram_message_id, created_at, "
                    "substr(message_text, 1, 200) FROM posts WHERE expert_id = ? AND "
                    "(created_at > ? OR (created_at = ? AND post_id > ?)) "
                    "ORDER BY created_at ASC, post_id ASC LIMIT ?",
                    (expert_id, created_at, created_at, post_id, n),
                ),
            ):
                neighbors.extend(
                    {
                        "source_key": f"{n_expert}:{n_mid}",
                        "created_at": n_created,
                        "excerpt": n_excerpt,
                    }
                    for n_expert, n_mid, n_created, n_excerpt in conn.execute(
                        side_sql, side_params
                    ).fetchall()
                )
        elif expand > 0:
            video_id = _video_fields(media_metadata).get("video_id")
            video_posts = _video_posts(conn, video_id) if video_id else []
            position = next((i for i, p in enumerate(video_posts) if p["source_key"] == raw_key), None)
            if position is not None:
                n = min(expand, MAX_EXPAND_NEIGHBORS)
                neighbors = [{"source_key": p["source_key"], "created_at": p["created_at"],
                              "excerpt": p["message_text"][:200], "video_id": video_id,
                              "video_timestamp_s": p.get("video_timestamp_s")}
                             for p in video_posts[max(0, position-n):position+n+1] if p["source_key"] != raw_key]
        source_text = message_text or ""
        segment_title = None
        if expert_id == "video_hub" and "\nCONTENT:\n" in source_text:
            header, _, source_text = source_text.partition("\nCONTENT:\n")
            segment_title = header.partition("\n")[0].removeprefix("TITLE: ")
        payload.append(
            {
                "source_key": f"{expert_id}:{message_id}",
                "channel_username": channel_username,
                "created_at": created_at,
                "author_name": author_name,
                "reply_count": reply_count,
                "view_count": view_count,
                "content": source_text,
                "segment_title": segment_title,
                "content_kind": "transcript_and_screen_notes" if expert_id == "video_hub" else "expert_post",
                "editorial_note": "TITLE and SUMMARY are editorial aids, not quotations from the expert." if expert_id == "video_hub" else None,
                **_video_fields(media_metadata),
                "comments": comments,
                "neighbors": neighbors,
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


def cmd_digest(args: argparse.Namespace) -> int:
    """Windowed exhaustive read of a scoped collection (no retrieval).

    Long-context over a scope (one expert, a group, video_hub) beats chunk
    retrieval when the corpus slice fits the model's context. The agent pages
    through windows; each call is char-capped so one page cannot flood context.
    """
    backend_dir = _load_backend()
    db_path = _resolve_db_path(backend_dir, args.db)
    window = max(1, min(args.window, MAX_DIGEST_WINDOW))
    page = max(0, args.page)
    cutoff = _cutoff_iso(args.recent_days)

    with _connect(db_path) as conn:
        try:
            expert_ids, unknown_experts = _expert_ids(conn, args.experts, args.group)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not expert_ids:
            print("error: empty scope (use --experts or --group)", file=sys.stderr)
            return 2
        placeholders = ",".join("?" for _ in expert_ids)
        sql = (
            "SELECT post_id, expert_id, telegram_message_id, created_at, message_text, author_name, media_metadata "
            f"FROM posts WHERE expert_id IN ({placeholders})"
        )
        params: list[Any] = list(expert_ids)
        if cutoff:
            sql += " AND created_at >= ?"
            params.append(cutoff)
        offset = getattr(args, "cursor", None)
        offset = page * window if offset is None else max(0, offset)
        if getattr(args, "video_id", None):
            if expert_ids != ["video_hub"]:
                print("error: video_id requires experts=video_hub", file=sys.stderr)
                return 2
            videos = _video_posts(conn, args.video_id)
            if cutoff:
                videos = [p for p in videos if p["created_at"] >= cutoff]
            rows = [(p["telegram_message_id"], p["expert_id"], p["telegram_message_id"],
                     p["created_at"], p["message_text"], p["author_name"],
                     json.dumps({"type": "video_segment", "video_url": p.get("video_url"),
                                 "video_title": p.get("video_title"), "timestamp_seconds": p.get("video_timestamp_s"),
                                 **{k: p[k] for k in ("scope", "scope_range_s", "published_at", "duration_seconds", "original_author", "timestamp_kind") if k in p}}))
                    for p in videos[offset:offset+window+1]]
        else:
            sql += " ORDER BY created_at DESC, post_id DESC LIMIT ? OFFSET ?"
            params.extend([window + 1, offset])
            rows = conn.execute(sql, params).fetchall()

    has_more = len(rows) > window
    rows = rows[:window]
    posts = []
    for post_id, expert_id, telegram_message_id, created_at, message_text, author_name, media_metadata in rows:
        text = (message_text or "").strip().replace("\n", " ")
        if len(text) > MAX_DIGEST_TEXT:
            text = text[: MAX_DIGEST_TEXT - 1] + "…"
        entry = {
            "source_key": f"{expert_id}:{telegram_message_id}",
            "created_at": created_at,
            "text": text,
            "author_name": (author_name or "")[:100],
            "preview_only": True,
            "content_chars": len(message_text or ""),
        }
        fields = _video_fields(media_metadata)
        for key in ("video_id", "video_timestamp_s", "timestamp_kind", "coverage"):
            if key in fields:
                entry[key] = fields[key]
        if fields.get("video_title"):
            entry["video_title"] = fields["video_title"][:100]
        posts.append(entry)

    payload = {
        "scope": expert_ids,
        "page": page,
        "window": window,
        "has_more": has_more,
        "next_cursor": offset + len(posts) if has_more else None,
        "status": "partial" if unknown_experts else "completed",
        "preview_only": True,
        "video_id": getattr(args, "video_id", None),
        "unknown_experts": unknown_experts,
        "posts": posts,
    }
    # Shrink previews rather than dropping rows: legacy page numbers must
    # remain safe as well as the next_cursor protocol.
    while len(json.dumps(payload, ensure_ascii=False)) > MAX_DIGEST_CHARS and any(p["text"] for p in posts):
        for post in posts:
            post["text"] = post["text"][:max(0, len(post["text"]) - 20)]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print(f"# digest scope={','.join(expert_ids)} page={page} posts={len(posts)} has_more={has_more} next_cursor={payload['next_cursor']} preview_only=true")
        for post in posts:
            print(f"- {post['source_key']} [{post['created_at']}] author={post['author_name']} video_id={post.get('video_id')} keyframe={post.get('video_timestamp_s')} {post['text']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    backend_dir = _load_backend()
    db_path = _resolve_db_path(backend_dir, args.db)
    comments_limit = max(0, min(args.comments_limit, MAX_COMMENTS_LIMIT))
    if len(args.source_keys) > MAX_SHOW_KEYS:
        print(f"error: show accepts at most {MAX_SHOW_KEYS} keys; split into batches", file=sys.stderr)
        return 2

    with _connect(db_path) as conn:
        payload = _collect_show_payload(
            conn, args.source_keys, comments_limit, expand=getattr(args, "expand", 0)
        )
    offset = max(0, getattr(args, "content_offset", 0))
    length = max(1, min(getattr(args, "max_chars", MAX_SHOW_CHARS), MAX_SHOW_CHARS))
    for item in payload:
        if "error" in item:
            continue
        total = len(item["content"] or "")
        item["content"] = (item["content"] or "")[offset:offset+length]
        end = min(total, offset+length)
        item.update(content_offset=offset, content_chars=total, content_end=end,
                    truncated=end < total, next_content_offset=end if end < total else None)

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
            print(f"AUTHOR: {item.get('author_name')}")
            print("VIDEO_METADATA: " + json.dumps({k: v for k, v in item.items() if k.startswith('video_') or k in {'timestamp_kind', 'coverage', 'scope', 'scope_range_s', 'segment_start_s', 'segment_end_s', 'published_at'}}, ensure_ascii=False))
            print("READ_STATE: " + json.dumps({k: item[k] for k in ('content_offset', 'content_chars', 'content_end', 'truncated', 'next_content_offset')}))
            print(item["content"])
            if item.get("neighbors"):
                print(f"--- neighbors ({len(item['neighbors'])}) ---")
                for neighbor in item["neighbors"]:
                    print(f"  {neighbor['source_key']} [{neighbor['created_at']}]: {neighbor['excerpt']}")
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
    videos = subparsers.add_parser("videos", help="VideoHub catalog with authors, counts and coverage limits")
    videos.add_argument("--video-id", default=None)
    videos.add_argument("--cursor", type=int, default=0)
    videos.add_argument("--json", action="store_true")

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
    search.add_argument(
        "--diversity",
        action="store_true",
        help="Opt-in: cap per-expert hits in the top window (DIVERSITY_CAP_TOP) to avoid single-author monoculture",
    )
    search.add_argument(
        "--freshness",
        choices=["tool", "craft", "any"],
        default="tool",
        help="tool = soft age penalty (fast-moving tooling); craft/any = no age penalty (durable craft knowledge)",
    )
    search.add_argument(
        "--now",
        help="ISO timestamp used as 'now' for the freshness decay (reproducible probes; default: system time)",
    )
    search.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    search.add_argument("--cursor", type=int, default=0, help="Continue the same query using next_cursor")

    digest = subparsers.add_parser(
        "digest",
        help="Windowed exhaustive read of a scoped collection (expert/group), no retrieval",
    )
    digest_scope = digest.add_mutually_exclusive_group(required=True)
    digest_scope.add_argument("--experts", help="Comma-separated expert_id subset")
    digest_scope.add_argument("--group", help="Canonical group name (tech, tech_business, visual)")
    digest.add_argument("--recent-days", type=int, default=None, help="Only posts newer than N days")
    digest.add_argument("--window", type=int, default=15, help=f"Posts per page (default 15, max {MAX_DIGEST_WINDOW})")
    digest.add_argument("--page", type=int, default=0, help="Page number, 0-based")
    digest.add_argument("--cursor", type=int, default=None, help="Use next_cursor from the previous result")
    digest.add_argument("--video-id", default=None, help="Exact YouTube id, requires experts=video_hub")
    digest.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    show = subparsers.add_parser("show", help="Show full source(s) with comments and linked context")
    show.add_argument("source_keys", nargs="+", help="source_key values like refat:238")
    show.add_argument("--comments-limit", type=int, default=DEFAULT_COMMENTS_LIMIT, help=f"Max comments per window (author / community) per source (default {DEFAULT_COMMENTS_LIMIT})")
    show.add_argument("--expand", type=int, default=0, help=f"Also fetch up to N adjacent posts per source (same expert, +/- in time; max {MAX_EXPAND_NEIGHBORS})")
    show.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    show.add_argument("--content-offset", type=int, default=0)
    show.add_argument("--max-chars", type=int, default=MAX_SHOW_CHARS)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "experts":
        return cmd_experts(args)
    if args.command == "videos":
        return cmd_videos(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "digest":
        return cmd_digest(args)
    if args.command == "show":
        return cmd_show(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
