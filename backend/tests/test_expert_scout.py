#!/usr/bin/env python3
"""Unit tests for the read-only Expert Scout helper and output filter."""

from __future__ import annotations

import importlib.util
import io
from contextlib import nullcontext
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
SCOUT_PATH = BACKEND_DIR / "scripts" / "expert_scout.py"
FILTER_PATH = REPO_ROOT / "scripts" / "expert_scout_filter.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scout():
    return _load_module("expert_scout_under_test", SCOUT_PATH)


def test_parse_source_key_valid_and_invalid(scout):
    assert scout._parse_source_key("refat:238") == ("refat", 238)

    for bad in ["refat", "refat:abc", ":12", "refat:-1"]:
        with pytest.raises(ValueError):
            scout._parse_source_key(bad)


def test_rrf_merge_prefers_ids_found_by_both_retrievers(scout):
    merged = scout._rrf_merge([10, 11], [12, 10], k=60)

    assert merged[0] == 10  # present in both lists wins
    assert set(merged) == {10, 11, 12}


def test_leg_stats_exposes_dead_leg(scout):
    """Improvement 3: hybrid leg telemetry (silent dead-leg detection)."""
    stats = scout.leg_stats([1, 2, 3, 4], [3, 4, 5, 6])
    assert stats["fts_ranked"] == 4
    assert stats["vector_ranked"] == 4
    assert stats["overlap"] == 2
    assert 0 < stats["jaccard"] < 1

    dead = scout.leg_stats([1, 2], [3, 4])
    assert dead["overlap"] == 0 and dead["jaccard"] == 0.0

    empty = scout.leg_stats([], [])
    assert empty["overlap"] == 0 and empty["jaccard"] == 0.0


def test_digest_parser_requires_scope(scout):
    """Improvement 4: digest = windowed exhaustive read of a scope."""
    parser = scout.build_parser()
    args = parser.parse_args(["digest", "--experts", "acidcrunch", "--window", "30", "--page", "2"])
    assert args.command == "digest"
    assert args.window == 30 and args.page == 2
    with pytest.raises(SystemExit):
        parser.parse_args(["digest"])
    with pytest.raises(SystemExit):
        parser.parse_args(["digest", "--experts", "a", "--group", "visual"])


def test_digest_caps_are_bounded(scout):
    assert scout.MAX_DIGEST_WINDOW <= 30
    assert scout.MAX_DIGEST_TEXT <= 500
    assert scout.MAX_DIGEST_CHARS <= 20000


@pytest.fixture
def synthetic_corpus(scout, tmp_path, monkeypatch):
    """Exercise real read-only SQL without a deployment corpus or credentials."""
    backend = tmp_path / "backend"
    (backend / "data").mkdir(parents=True)
    with sqlite3.connect(backend / "data" / "experts.db") as conn:
        conn.executescript("""
            CREATE TABLE expert_metadata (expert_id TEXT);
            CREATE TABLE posts (
                post_id INTEGER PRIMARY KEY, expert_id TEXT,
                telegram_message_id INTEGER, channel_username TEXT,
                created_at TEXT, author_name TEXT, author_id TEXT,
                message_text TEXT, reply_count INTEGER, view_count INTEGER,
                media_metadata TEXT
            );
            CREATE TABLE comments (
                post_id INTEGER, comment_text TEXT, author_name TEXT,
                author_id TEXT, created_at TEXT
            );
            CREATE TABLE links (source_post_id INTEGER, target_post_id INTEGER);
        """)
        for expert in ("fixture_author", "other_author"):
            conn.execute("INSERT INTO expert_metadata VALUES (?)", (expert,))
            for number in range(1, 24):
                conn.execute(
                    "INSERT INTO posts VALUES (NULL, ?, ?, ?, ?, ?, NULL, ?, 0, 0, NULL)",
                    (expert, number, expert, f"2026-01-{number:02d} 00:00:00",
                     "Test author", "Synthetic source text. " * 40),
                )
    monkeypatch.setattr(scout, "_load_backend", lambda: backend)
    return backend


def test_digest_walks_small_expert_completely(scout, synthetic_corpus, capsys):
    """Every fixture post is reachable across pages, without scope leakage."""
    keys = []
    for page, size in enumerate((10, 10, 3)):
        args = scout.build_parser().parse_args([
            "digest", "--experts", "fixture_author", "--window", "10",
            "--page", str(page), "--json",
        ])
        assert scout.cmd_digest(args) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["scope"] == ["fixture_author"]
        assert payload["has_more"] is (page < 2)
        assert payload["next_cursor"] == ((page + 1) * 10 if page < 2 else None)
        assert len(payload["posts"]) == size
        assert all(len(post["text"]) <= scout.MAX_DIGEST_TEXT for post in payload["posts"])
        keys.extend(post["source_key"] for post in payload["posts"])
    assert keys == [f"fixture_author:{number}" for number in range(23, 0, -1)]


def test_parse_now_is_optional_and_validated(scout):
    """Reproducible probes: --now anchors the day-based freshness decay."""
    from datetime import datetime, timezone

    assert scout._parse_now(None) is not None
    fixed = scout._parse_now("2026-09-29T12:00:00")
    assert fixed == datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
    assert scout._parse_now("2026-09-29 12:00:00") == fixed
    with pytest.raises(ValueError):
        scout._parse_now("не дата")


def test_diversify_caps_monoculture_but_keeps_order(scout):
    """Improvement 7: the top window keeps at most N posts per expert."""
    assert scout.DIVERSITY_CAP_TOP == 6
    assert scout.DIVERSITY_CAP_REST == 10
    ids = list(range(10))
    experts = {i: ("a" if i < 7 else "b") for i in ids}
    out = scout.diversify(ids, experts, top_k=10)
    # 7 "a" posts, 3 "b" posts: the top window takes only 6 "a", then the "b"s
    # float up; the 7th "a" is deferred to the tail (order kept).
    assert out[:6] == [0, 1, 2, 3, 4, 5]
    assert out[6:9] == [7, 8, 9]
    assert out[9:] == [6]
    assert set(out) == set(ids)
    # single-expert lists are untouched
    mono = {i: "a" for i in ids}
    assert scout.diversify(ids, mono, top_k=10) == ids


def test_show_expand_fetches_adjacent_posts(scout, synthetic_corpus, capsys):
    """Expansion is capped, excludes the center and cannot cross experts."""
    assert scout.MAX_EXPAND_NEIGHBORS <= 5
    args = scout.build_parser().parse_args([
        "show", "fixture_author:12", "--expand", "99", "--json",
    ])
    assert scout.cmd_show(args) == 0
    item = json.loads(capsys.readouterr().out)[0]
    neighbors = item["neighbors"]
    assert len(neighbors) == 2 * scout.MAX_EXPAND_NEIGHBORS
    assert {post["source_key"] for post in neighbors} == {
        f"fixture_author:{number}"
        for number in range(12 - scout.MAX_EXPAND_NEIGHBORS, 13 + scout.MAX_EXPAND_NEIGHBORS)
        if number != 12
    }


def test_cutoff_iso_format(scout):
    assert scout._cutoff_iso(None) is None
    cutoff = scout._cutoff_iso(7)
    assert cutoff is not None
    assert len(cutoff) == len("2026-01-01 00:00:00")


def test_search_pool_is_wide_for_llm_reranking(scout):
    """Improvement 1: the candidate pool is wide enough for the model to re-rank."""
    assert scout.MAX_LIMIT >= 40
    assert scout.DEFAULT_LIMIT >= 20
    assert scout.VECTOR_TOP_K >= scout.MAX_LIMIT
    args = scout.build_parser().parse_args(["search", "q"])
    assert args.limit == scout.DEFAULT_LIMIT
    assert scout.build_parser().parse_args(["search", "q", "--limit", "40"]).limit == 40


def test_search_candidate_depth_is_limit_independent(scout):
    """Ranking must not reshuffle when the caller widens the pool (BM25 max_rank)."""
    assert scout.FTS_CANDIDATES >= 90
    src = Path(scout.__file__).read_text(encoding="utf-8")
    assert "limit * 3" not in src


def test_freshness_craft_mode_neutralizes_age_penalty(scout):
    """Improvement 2: craft/any profiles must not demote old canonical posts."""
    from datetime import datetime, timezone

    now = datetime(2026, 9, 29, tzinfo=timezone.utc)
    old = "2024-01-01 00:00:00"
    fresh = "2026-09-01 00:00:00"
    assert scout._soft_freshness(old, now, "tool") == scout.FRESHNESS_MAX_PENALTY
    assert scout._soft_freshness(old, now, "craft") == 1.0
    assert scout._soft_freshness(old, now, "any") == 1.0
    assert scout._soft_freshness(fresh, now, "tool") > scout._soft_freshness(old, now, "tool")

    # old strong BM25 match vs a slightly weaker fresh one: age penalty flips the order
    fts_rows = [
        (1, "old strong", -10.0, old),
        (2, "fresh slightly weaker", -9.0, fresh),
    ]
    tool_order = scout._rank_fts(fts_rows, now, "tool")
    craft_order = scout._rank_fts(fts_rows, now, "craft")
    assert craft_order[0] == 1, "craft must keep the strong old match first"
    assert tool_order[0] == 2, "tool profile demotes the old match (recency trap demo)"


def test_connect_is_read_only(scout, tmp_path):
    db_path = tmp_path / "sample.db"
    with sqlite3.connect(db_path) as setup:
        setup.execute("CREATE TABLE t (x INTEGER)")
        setup.execute("INSERT INTO t VALUES (1)")
        setup.commit()

    with scout._connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO t VALUES (2)")


def test_resolve_db_path_rejects_outside_backend_data(scout):
    with pytest.raises(SystemExit):
        scout._resolve_db_path(BACKEND_DIR, "/etc/passwd")

    resolved = scout._resolve_db_path(BACKEND_DIR, None)
    assert resolved == (BACKEND_DIR / "data" / "experts.db").resolve()


def test_expert_ids_validates_against_metadata(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?)", [("refat",), ("akimov",)]
    )

    known, unknown = scout._expert_ids(conn, "refat,bogus")
    assert known == ["refat"]
    assert unknown == ["bogus"]

    all_known, no_unknown = scout._expert_ids(conn, None)
    assert all_known == ["akimov", "refat"]
    assert no_unknown == []


def test_expert_ids_resolves_canonical_group(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?)",
        [("acidcrunch",), ("strangedalle",), ("cgevent",), ("neyrograph",), ("iideyalogiya",), ("refat",)],
    )

    known, unknown = scout._expert_ids(conn, None, "visual")
    assert known == ["strangedalle", "acidcrunch", "cgevent", "neyrograph", "iideyalogiya"]
    assert unknown == []

    known_tb, _ = scout._expert_ids(conn, None, "tech_business")
    assert known_tb == ["refat"]


def test_expert_ids_rejects_unknown_group(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")

    with pytest.raises(ValueError, match="unknown expert group"):
        scout._expert_ids(conn, None, "bogus")


def test_expert_groups_shared_module_is_canonical():
    from src.expert_groups import AGENT_CONTEXT_EXPERT_GROUPS, groups_for_expert

    assert "visual" in AGENT_CONTEXT_EXPERT_GROUPS
    assert "strangedalle" in AGENT_CONTEXT_EXPERT_GROUPS["visual"]
    assert groups_for_expert("acidcrunch") == ["visual"]
    assert groups_for_expert("cgevent") == ["visual"]
    assert groups_for_expert("neyrograph") == ["visual"]
    assert groups_for_expert("iideyalogiya") == ["visual"]
    assert groups_for_expert("refat") == ["tech_business"]
    assert groups_for_expert("mkarpov") == []


def test_filter_keeps_only_text_after_last_tool(capsys, monkeypatch):
    filter_module = _load_module("expert_scout_filter_under_test", FILTER_PATH)
    events = "\n".join(
        [
            '{"type":"text","part":{"messageID":"m1","text":"narration"}}',
            '{"type":"tool_use","part":{"messageID":"m2","tool":"bash"}}',
            '{"type":"text","part":{"messageID":"m3","text":"FINAL "}}',
            '{"type":"text","part":{"messageID":"m3","text":"ANSWER"}}',
            '{"type":"step_finish","part":{"reason":"stop"}}',
        ]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(events))

    assert filter_module.main() == 0
    assert capsys.readouterr().out.strip() == "FINAL ANSWER"


def test_filter_marks_fallback_narration(capsys, monkeypatch):
    filter_module = _load_module("expert_scout_filter_fallback", FILTER_PATH)
    events = "\n".join(
        [
            '{"type":"text","part":{"messageID":"m1","text":"thinking out loud"}}',
            '{"type":"tool_use","part":{"messageID":"m2","tool":"scout"}}',
        ]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(events))

    assert filter_module.main() == 3
    out = capsys.readouterr().out
    assert out.startswith("# WARNING")
    assert "thinking out loud" in out


def test_soft_freshness_parses_both_formats_and_floors(scout):
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    one_day_space = scout._soft_freshness("2026-09-12 12:00:00.000000", now)
    one_day_iso = scout._soft_freshness("2026-09-12T12:00:00", now)

    assert one_day_space == pytest.approx(one_day_iso)
    assert one_day_space == pytest.approx(1 - 1 / 365, abs=1e-6)
    assert scout._soft_freshness("2020-01-01 00:00:00", now) == 0.7
    assert scout._soft_freshness(None, now) == 0.7
    assert scout._soft_freshness("garbage", now) == 0.7


def test_rank_fts_demotes_stale_strong_match(scout):
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    rows = [
        (1, "s1", -6.0, "2023-01-01 00:00:00.000000"),  # better BM25, stale
        (2, "s2", -5.0, "2026-09-12 00:00:00"),  # slightly weaker, fresh
    ]

    assert scout._rank_fts(rows, now) == [2, 1]


def test_rank_vector_prefers_fresh_relevant(scout):
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    rows = [
        (1, 0.10, "2023-01-01 00:00:00.000000"),  # closest, stale
        (2, 0.30, "2026-09-12 00:00:00"),  # farther, fresh
    ]

    assert scout._rank_vector(rows, now)[:1] == [2]


@pytest.mark.parametrize('freshness', ['tool', 'craft', 'any'])
def test_rank_vector_distinguishes_distances_above_one(scout, freshness):
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    rows = [(1, 1.4, '2026-10-01'), (2, 1.1, '2026-10-01'),
            (3, 1.01, '2026-10-01'), (4, 0.9, '2026-10-01')]
    expected = [4, 3, 2, 1]
    assert scout._rank_vector(rows, now, freshness) == expected
    # Expert iteration order must not decide relevance for distant matches.
    assert scout._rank_vector(list(reversed(rows)), now, freshness) == expected


def test_vec_default_metric_can_exceed_one(scout):
    if scout.sqlite_vec is None:
        pytest.skip('sqlite_vec not installed')
    with sqlite3.connect(':memory:') as conn:
        conn.enable_load_extension(True)
        scout.sqlite_vec.load(conn)
        conn.execute('CREATE VIRTUAL TABLE vectors USING vec0(embedding float[2])')
        conn.execute("INSERT INTO vectors(rowid, embedding) VALUES (1, '[0, 1]')")
        distance = conn.execute(
            "SELECT distance FROM vectors WHERE embedding MATCH '[1, 0]' AND k=1"
        ).fetchone()[0]
    assert distance == pytest.approx(2 ** 0.5)


def test_broad_candidate_pool_keeps_text_and_vector_tail(scout):
    fts = list(range(90))
    vector = list(range(100,140))
    rows = [(i,1.4,'2026-09-30') for i in vector] + [(200,1.1,'2026-09-30')]
    pool = scout._candidate_pool(fts,vector,rows,60)
    assert pool[:40] == scout._rrf_merge(fts,vector,60)[:40]
    assert set(pool) == set(fts+vector+[200])
    assert len(pool) == len(set(pool))


@pytest.fixture()
def show_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE posts (
            post_id INTEGER PRIMARY KEY, expert_id TEXT, telegram_message_id INTEGER,
            channel_username TEXT, created_at TEXT, author_name TEXT, author_id TEXT,
            message_text TEXT, reply_count INTEGER, view_count INTEGER,
            media_metadata TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE comments (
            comment_id INTEGER PRIMARY KEY, post_id INTEGER, comment_text TEXT,
            author_id TEXT, author_name TEXT, created_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE TABLE links (source_post_id INTEGER, target_post_id INTEGER, link_type TEXT)"
    )
    conn.execute(
        "INSERT INTO posts (post_id, expert_id, telegram_message_id, channel_username,"
        " created_at, author_name, author_id, message_text, reply_count, view_count)"
        " VALUES (1, 'acidcrunch', 2062, 'AcidCrunch',"
        " '2025-06-05 10:00:00.000000', 'Acid', 'channel55', 'post text', 3, 100)"
    )
    for i in range(6):
        conn.execute(
            "INSERT INTO comments VALUES (?, 1, ?, '999', ?, ?)",
            (i + 1, f"community {i}", f"user{i}", f"2025-06-05 11:{i:02d}:00.000000"),
        )
    # Late author replies would fall outside the chronological comment window.
    conn.execute(
        "INSERT INTO comments VALUES (20, 1, 'author answer', '55', 'Acid',"
        " '2025-06-06 10:00:00.000000')"
    )
    conn.execute(
        "INSERT INTO comments VALUES (21, 1, 'author answer 2', '55', 'Acid',"
        " '2025-06-06 11:00:00.000000')"
    )
    conn.execute(
        "INSERT INTO posts (post_id, expert_id, telegram_message_id, channel_username,"
        " created_at, author_name, author_id, message_text, reply_count, view_count)"
        " VALUES (2, 'acidcrunch', 2070, 'AcidCrunch',"
        " '2025-06-07 10:00:00.000000', 'Acid', 'channel55', 'linked post text', 0, 5)"
    )
    conn.execute(
        "INSERT INTO posts (post_id, expert_id, telegram_message_id, channel_username,"
        " created_at, author_name, author_id, message_text, reply_count, view_count, media_metadata)"
        " VALUES (3, 'video_hub', 825056013, NULL, '2026-08-21T00:00:00',"
        " 'Youri van Hofwegen', 'youri', 'video segment text', 0, 0, ?)",
        (
            json.dumps(
                {
                    "type": "video_segment",
                    "video_url": "https://youtu.be/2b3Z4rW5VJc",
                    "timestamp_seconds": 258,
                    "video_title": "Seedance 2.5 tutorial",
                }
            ),
        ),
    )
    conn.execute("INSERT INTO links VALUES (1, 2, 'reply')")
    conn.commit()
    return conn


def test_collect_show_payload_keeps_late_author_comments(scout, show_conn):
    payload = scout._collect_show_payload(show_conn, ["acidcrunch:2062"], 5)
    item = payload[0]

    author = [c for c in item["comments"] if c["is_author"]]
    community = [c for c in item["comments"] if not c["is_author"]]
    assert len(author) == 2  # both late author replies are kept
    assert len(community) == 5  # community window stays capped
    assert item["linked_context"][0]["source_key"] == "acidcrunch:2070"


def test_collect_show_payload_reports_bad_keys(scout, show_conn):
    payload = scout._collect_show_payload(
        show_conn, ["acidcrunch:abc", "acidcrunch:999999"], 5
    )

    assert payload[0]["error"].startswith("invalid source_key")
    assert payload[1]["error"] == "not_found"


def test_video_fields_builds_deep_link(scout):
    fields = scout._video_fields(
        json.dumps(
            {
                "type": "video_segment",
                "video_url": "https://youtu.be/abc",
                "timestamp_seconds": 258,
                "video_title": "Title",
            }
        )
    )
    assert fields["video_link"] == "https://youtu.be/abc?t=258s"
    assert fields["video_timestamp_s"] == 258
    assert fields["video_title"] == "Title"


def test_video_fields_ignores_non_video_and_bad_json(scout):
    assert scout._video_fields("not json at all") == {}
    assert scout._video_fields(json.dumps({"type": "telegram_post"})) == {}
    assert scout._video_fields(None) == {}


def test_collect_show_payload_exposes_video_link(scout, show_conn):
    payload = scout._collect_show_payload(show_conn, ["video_hub:825056013"], 3)
    item = payload[0]

    assert item["video_link"] == "https://youtu.be/2b3Z4rW5VJc?t=258s"
    assert item["video_timestamp_s"] == 258
    assert item["video_title"] == "Seedance 2.5 tutorial"


def _mock_corpus(scout, monkeypatch, conn):
    monkeypatch.setattr(scout, "_load_backend", lambda: BACKEND_DIR)
    monkeypatch.setattr(scout, "_connect", lambda *args: nullcontext(conn))


def test_search_returns_fts_after_embedding_timeouts(scout, show_conn, monkeypatch, capsys):
    from unittest.mock import AsyncMock
    import requests
    from src.services import embedding_service as embeddings

    _mock_corpus(scout, monkeypatch, show_conn)
    monkeypatch.setattr(scout, '_expert_ids', lambda *a: (['acidcrunch'], []))
    monkeypatch.setattr(scout, '_fts_search', lambda *a: ([(1, 'post text', -1, '2025-06-05')], None))
    monkeypatch.setattr(embeddings.config, 'OPENROUTER_API_KEY', 'test-only')
    calls = []

    def fail(*a, **kw):
        calls.append(kw['timeout'])
        raise requests.Timeout('simulated timeout')

    monkeypatch.setattr(embeddings.requests, 'post', fail)
    monkeypatch.setattr(embeddings.asyncio, 'sleep', AsyncMock())
    args = scout.build_parser().parse_args(['search', 'post', '--experts', 'acidcrunch', '--json'])
    assert scout.cmd_search(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert calls == [15, 15]
    assert result['status'] == 'partial'
    assert result['warnings'] == ['embedding_failed: RetryableEmbeddingError']
    assert result['results'][0]['source_key'] == 'acidcrunch:2062'
    assert result['results'][0]['found_by'] == ['fts']


def test_compact_search_keeps_candidates_and_show_keeps_metadata(scout, show_conn, monkeypatch, capsys):
    _mock_corpus(scout, monkeypatch, show_conn)
    monkeypatch.setattr(scout, '_expert_ids', lambda *a: (['video_hub'], []))
    monkeypatch.setattr(scout, '_fts_search', lambda *a: ([(3, 'video snippet', -1, '2026-08-21')], None))
    args = scout.build_parser().parse_args(['search', 'video', '--experts', 'video_hub', '--no-vector', '--json'])
    assert scout.cmd_search(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'completed'
    assert result['candidate_pool_size'] == 1
    card = result['results'][0]
    assert card['source_key'] == 'video_hub:825056013'
    assert card['author_name'] == 'Youri van Hofwegen'
    assert card['video_id'] == '2b3Z4rW5VJc'
    assert card['snippet'] == 'video snippet'
    assert card['coverage'] == 'unknown'
    assert card['timestamp_kind'] == 'keyframe'
    assert 'video_url' not in card and 'video_link' not in card
    assert 'channel_username' not in card and 'segment_start_s' not in card
    source = scout._collect_show_payload(show_conn, [card['source_key']], 0)[0]
    assert source['video_link'].endswith('t=258s')
    assert source['content'] == 'video segment text'
    assert source['timestamp_kind'] == 'keyframe'


def test_digest_does_not_skip_rows_at_character_cap(scout, show_conn, monkeypatch, capsys):
    show_conn.execute("DELETE FROM posts")
    show_conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    show_conn.execute("INSERT INTO expert_metadata VALUES ('acidcrunch')")
    show_conn.executemany("INSERT INTO posts (post_id, expert_id, telegram_message_id, created_at, message_text, author_name) VALUES (?, 'acidcrunch', ?, '2026-01-01', ?, 'Author')",
                          [(i, i, 'x'*500) for i in range(1,61)])
    _mock_corpus(scout, monkeypatch, show_conn)
    seen = []
    for page in range(2):
        args = scout.build_parser().parse_args(['digest','--experts','acidcrunch','--window','30','--page',str(page),'--json'])
        assert scout.cmd_digest(args) == 0
        payload = json.loads(capsys.readouterr().out)
        seen.extend(p['source_key'] for p in payload['posts'])
        assert len(payload['posts']) == 30
        assert payload['preview_only']
    assert len(set(seen)) == 60
    assert payload['next_cursor'] is None


def test_exact_video_digest_and_catalog(scout, show_conn, monkeypatch, capsys):
    show_conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    show_conn.execute("INSERT INTO expert_metadata VALUES ('video_hub')")
    _mock_corpus(scout, monkeypatch, show_conn)
    args = scout.build_parser().parse_args(['videos','--video-id','2b3Z4rW5VJc','--json'])
    assert scout.cmd_videos(args) == 0
    record = json.loads(capsys.readouterr().out)['videos'][0]
    assert record['author'] == 'Youri van Hofwegen'
    assert record['segment_count'] == 1 and record['coverage'] == 'unknown'
    args = scout.build_parser().parse_args(['digest','--experts','video_hub','--video-id','2b3Z4rW5VJc','--json'])
    assert scout.cmd_digest(args) == 0
    posts = json.loads(capsys.readouterr().out)['posts']
    assert [p['source_key'] for p in posts] == ['video_hub:825056013']
    assert posts[0]['timestamp_kind'] == 'keyframe'


def test_video_neighbors_follow_video_and_time(scout, show_conn):
    for pid, mid, video, timestamp in [(4,4,'2b3Z4rW5VJc',100),(5,5,'other_video',257),(6,6,'2b3Z4rW5VJc',400)]:
        meta = json.dumps({'type':'video_segment','video_url':f'https://youtu.be/{video}','timestamp_seconds':timestamp})
        show_conn.execute("INSERT INTO posts (post_id,expert_id,telegram_message_id,created_at,message_text,media_metadata) VALUES (?, 'video_hub', ?, '2026-08-21', 'text', ?)", (pid,mid,meta))
    item = scout._collect_show_payload(show_conn,['video_hub:825056013'],0,expand=1)[0]
    assert [p['source_key'] for p in item['neighbors']] == ['video_hub:4','video_hub:6']


def test_show_has_explicit_continuation_and_author(scout, show_conn, monkeypatch, capsys):
    show_conn.execute("UPDATE posts SET message_text=? WHERE post_id=3", ('start-'+ 'x'*10000+'-critical-tail',))
    _mock_corpus(scout, monkeypatch, show_conn)
    args = scout.build_parser().parse_args(['show','video_hub:825056013','--json','--comments-limit','0'])
    assert scout.cmd_show(args) == 0
    first = json.loads(capsys.readouterr().out)[0]
    assert first['truncated'] and first['next_content_offset'] == scout.MAX_SHOW_CHARS
    args.content_offset = first['next_content_offset']
    assert scout.cmd_show(args) == 0
    second = json.loads(capsys.readouterr().out)[0]
    assert second['content'].endswith('-critical-tail') and not second['truncated']
    args.json, args.content_offset = False, 0
    scout.cmd_show(args)
    assert 'AUTHOR: Youri van Hofwegen' in capsys.readouterr().out


def test_digest_missing_expert_is_incomplete_scope(scout,show_conn,monkeypatch,capsys):
    show_conn.execute('CREATE TABLE expert_metadata (expert_id TEXT)')
    show_conn.execute("INSERT INTO expert_metadata VALUES ('video_hub')")
    _mock_corpus(scout,monkeypatch,show_conn)
    args=scout.build_parser().parse_args(['digest','--experts','video_hub,missing_expert','--json'])
    assert scout.cmd_digest(args)==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='partial' and result['unknown_experts']==['missing_expert']
