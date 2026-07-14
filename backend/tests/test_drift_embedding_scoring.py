"""Tests for embedding-based drift scoring (replaces LLM chunked scoring).

Covers:
- ``build_drift_text`` parser: multiple input formats, empty/malformed input, bytes.
- ``CommentGroupMapService._score_by_embedding``: cosine similarity ranking,
  threshold filter, top_k cap, dim-mismatch skip, zero-vector guard, date sort.
"""

import logging

import numpy as np
import pytest

from src.services.comment_group_map_service import (
    CommentGroupMapService,
    _all_drift_groups_have_embeddings,
    _normalize_embedding_to_blob,
    build_drift_text,
)


def _make_service() -> CommentGroupMapService:
    """Create service for tests. LLM client init is defensive and tolerates None."""
    return CommentGroupMapService(model="gemini-2.5-flash")


def _group_with_embedding(
    telegram_message_id: int,
    drift_embedding: np.ndarray,
    created_at: str = "2026-01-01",
) -> dict:
    return {
        "anchor_post": {
            "telegram_message_id": telegram_message_id,
            "message_text": f"post {telegram_message_id}",
            "created_at": created_at,
            "author_name": "x",
            "channel_username": "test",
        },
        "drift_topics": [
            {"topic": "t", "keywords": ["k"], "key_phrases": [], "context": "c"}
        ],
        "comments_count": 0,
        "comments": [],
        "drift_embedding": np.asarray(drift_embedding, dtype=np.float32).tobytes(),
    }


# --- build_drift_text ---


def test_build_drift_text_handles_dict_format():
    """Standard format: {has_drift, drift_topics: [{topic, keywords, context}]}."""
    json_str = (
        '{"has_drift": true, "drift_topics": ['
        '{"topic": "AI agents", "keywords": ["a", "b"], "context": "ctx"}'
        "]}"
    )
    text = build_drift_text(json_str)
    assert "AI agents" in text
    assert "a" in text
    assert "b" in text
    assert "ctx" in text


def test_build_drift_text_handles_list_format():
    """Bare list format (legacy from analyze_drift_async): [{topic, keywords}]."""
    json_str = '[{"topic": "T", "keywords": ["k1"]}]'
    text = build_drift_text(json_str)
    assert "T" in text
    assert "k1" in text


def test_build_drift_text_includes_key_phrases():
    """All four fields (topic, keywords, key_phrases, context) are concatenated."""
    json_str = (
        '{"drift_topics": ['
        '{"topic": "T", "keywords": ["kw"], "key_phrases": ["phrase one"], "context": "ctx"}'
        "]}"
    )
    text = build_drift_text(json_str)
    for piece in ("T", "kw", "phrase one", "ctx"):
        assert piece in text


def test_build_drift_text_handles_empty_input():
    assert build_drift_text("") == ""
    assert build_drift_text(None) == ""


def test_build_drift_text_handles_malformed_json():
    assert build_drift_text("not json at all") == ""
    assert build_drift_text("{invalid") == ""
    assert build_drift_text("[1, 2,") == ""


def test_build_drift_text_handles_bytes_input():
    """DB stores JSON as bytes in some code paths; build_drift_text must handle it."""
    json_str = b'{"drift_topics": [{"topic": "X", "keywords": ["y"]}]}'
    text = build_drift_text(json_str)
    assert "X" in text
    assert "y" in text


def test_build_drift_text_handles_non_dict_topics():
    """Topic entries that are not dicts (str, None, list) are skipped gracefully."""
    json_str = (
        '{"drift_topics": ['
        '"a string topic", null, ["a", "list"], '
        '{"topic": "valid", "keywords": ["k"]}'
        "]}"
    )
    text = build_drift_text(json_str)
    assert "valid" in text
    assert "k" in text
    # String/null/list entries should not be embedded
    assert "a string topic" not in text
    assert "a" not in text.split(" ")


# --- _score_by_embedding helpers ---


def _aligned_unit_vec(seed: int, axis: int = 0) -> np.ndarray:
    """Create a deterministic unit vector pointing along the given axis (with tiny noise)."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(768).astype(np.float32) * 0.001
    v[axis] = 1.0
    return v / np.linalg.norm(v)


def test_score_by_embedding_ranks_aligned_above_orthogonal():
    """Group aligned with query is returned HIGH; orthogonal group is below threshold."""
    svc = _make_service()
    q = _aligned_unit_vec(0, axis=0)
    g_aligned = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g_orthogonal = _group_with_embedding(2, _aligned_unit_vec(0, axis=1))

    result = svc._score_by_embedding(
        [g_aligned, g_orthogonal], q.tolist(), expert_id="test", t_start=0.0,
    )

    aligned_ids = {g["anchor_post"]["telegram_message_id"] for g in result}
    assert 1 in aligned_ids
    assert 2 not in aligned_ids  # orthogonal similarity is near 0, below 0.75 threshold


def test_score_by_embedding_respects_top_k():
    """Only top_k groups are returned even when more are above threshold."""
    from src import config

    original_top_k = config.DRIFT_EMBEDDING_TOP_K
    config.DRIFT_EMBEDDING_TOP_K = 3
    try:
        svc = _make_service()
        q = _aligned_unit_vec(0, axis=0)

        groups = [
            _group_with_embedding(i, _aligned_unit_vec(0, axis=0))
            for i in range(1, 8)  # 7 groups, all very similar to q
        ]

        result = svc._score_by_embedding(
            groups, q.tolist(), expert_id="test", t_start=0.0,
        )
        assert len(result) == 3
    finally:
        config.DRIFT_EMBEDDING_TOP_K = original_top_k


def test_score_by_embedding_handles_dimension_mismatch(caplog):
    """Group with wrong-dim embedding is skipped with WARNING; valid groups still scored."""
    svc = _make_service()
    q = _aligned_unit_vec(0, axis=0).tolist()

    g_wrong = _group_with_embedding(1, np.ones(512, dtype=np.float32))  # 512 != 768
    g_ok = _group_with_embedding(2, _aligned_unit_vec(0, axis=0))

    with caplog.at_level(logging.WARNING, logger="src.services.comment_group_map_service"):
        result = svc._score_by_embedding(
            [g_wrong, g_ok], q, expert_id="test", t_start=0.0,
        )

    assert any("dim mismatch" in r.message for r in caplog.records)
    aligned_ids = {g["anchor_post"]["telegram_message_id"] for g in result}
    assert 1 not in aligned_ids
    assert 2 in aligned_ids


def test_score_by_embedding_handles_zero_query_vector(caplog):
    """Zero query vector returns empty with WARNING (degenerate case)."""
    svc = _make_service()
    q = np.zeros(768, dtype=np.float32).tolist()
    g = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))

    with caplog.at_level(logging.WARNING, logger="src.services.comment_group_map_service"):
        result = svc._score_by_embedding(
            [g], q, expert_id="test", t_start=0.0,
        )

    assert result == []
    assert any("zero query vector" in r.message for r in caplog.records)


def test_score_by_embedding_sorts_results_by_date_desc():
    """When multiple groups pass, results are sorted by anchor post date desc."""
    svc = _make_service()
    q = _aligned_unit_vec(0, axis=0)
    g_old = _group_with_embedding(
        1, _aligned_unit_vec(0, axis=0), created_at="2025-01-01",
    )
    g_new = _group_with_embedding(
        2, _aligned_unit_vec(0, axis=0), created_at="2026-12-31",
    )
    g_mid = _group_with_embedding(
        3, _aligned_unit_vec(0, axis=0), created_at="2026-06-15",
    )

    result = svc._score_by_embedding(
        [g_old, g_new, g_mid], q.tolist(), expert_id="test", t_start=0.0,
    )

    dates = [g["anchor_post"]["created_at"] for g in result]
    assert dates == sorted(dates, reverse=True)


def test_score_by_embedding_skips_group_with_null_embedding():
    """A group whose drift_embedding is None is silently skipped (not crashed)."""
    svc = _make_service()
    q = _aligned_unit_vec(0, axis=0).tolist()
    g_null = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g_null["drift_embedding"] = None
    g_ok = _group_with_embedding(2, _aligned_unit_vec(0, axis=0))

    result = svc._score_by_embedding(
        [g_null, g_ok], q, expert_id="test", t_start=0.0,
    )
    aligned_ids = {g["anchor_post"]["telegram_message_id"] for g in result}
    assert aligned_ids == {2}


def test_score_by_embedding_does_not_mutate_input_groups():
    """Each returned group is a shallow copy; input groups keep their original fields."""
    svc = _make_service()
    q = _aligned_unit_vec(0, axis=0)
    g = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g["relevance"] = "ORIGINAL"
    g["reason"] = "ORIGINAL"

    result = svc._score_by_embedding(
        [g], q.tolist(), expert_id="test", t_start=0.0,
    )
    assert len(result) == 1
    # Returned copy is updated
    assert result[0]["relevance"] == "HIGH"
    # Original input is untouched
    assert g["relevance"] == "ORIGINAL"
    assert g["reason"] == "ORIGINAL"


# --- build_drift_text: non-list topics guard ---


def test_build_drift_text_rejects_topics_that_is_not_list():
    """Guard against corrupted rows: if ``drift_topics`` is a bare string or
    number, return empty rather than iterating characters."""
    assert build_drift_text('{"drift_topics": "not a list"}') == ""
    assert build_drift_text('{"drift_topics": 42}') == ""
    assert build_drift_text('{"drift_topics": null}') == ""


# --- _all_drift_groups_have_embeddings (dispatch predicate) ---


def test_all_drift_groups_have_embeddings_true_for_empty():
    """Empty group list → vacuously True (no LLM fallback)."""
    assert _all_drift_groups_have_embeddings([]) is True


def test_all_drift_groups_have_embeddings_true_when_all_present():
    g1 = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g2 = _group_with_embedding(2, _aligned_unit_vec(0, axis=0))
    assert _all_drift_groups_have_embeddings([g1, g2]) is True


def test_all_drift_groups_have_embeddings_false_when_one_missing():
    """The critical dispatch contract: ONE missing embedding → fallback to LLM."""
    g1 = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g2 = _group_with_embedding(2, _aligned_unit_vec(0, axis=0))
    g2["drift_embedding"] = None  # simulate legacy row
    assert _all_drift_groups_have_embeddings([g1, g2]) is False


def test_all_drift_groups_have_embeddings_false_when_all_missing():
    g1 = _group_with_embedding(1, _aligned_unit_vec(0, axis=0))
    g1["drift_embedding"] = None
    g2 = _group_with_embedding(2, _aligned_unit_vec(0, axis=0))
    g2["drift_embedding"] = None
    assert _all_drift_groups_have_embeddings([g1, g2]) is False


# --- _normalize_embedding_to_blob helpers ---
# This is the write-side contract that lets _score_by_embedding skip matrix
# normalize on read (saving ~120µs per expert). If you change the storage
# contract, ALSO update _score_by_embedding in comment_group_map_service.py.


def test_normalize_embedding_produces_unit_length_blob():
    """Output bytes decode back to a vector of norm exactly 1.0."""
    rng = np.random.default_rng(42)
    vec = rng.standard_normal(768).astype(np.float32) * 7.0  # any norm
    blob = _normalize_embedding_to_blob(vec)
    decoded = np.frombuffer(blob, dtype=np.float32)
    assert decoded.shape == (768,)
    assert np.isclose(np.linalg.norm(decoded), 1.0, atol=1e-6)


def test_normalize_embedding_idempotent_on_unit_input():
    """Normalizing an already-unit-length vector returns bytes close to original."""
    vec = _aligned_unit_vec(0, axis=0)
    blob = _normalize_embedding_to_blob(vec)
    decoded = np.frombuffer(blob, dtype=np.float32)
    assert np.allclose(decoded, vec, atol=1e-6)


def test_normalize_embedding_handles_list_input():
    """Embedding service returns lists, not ndarrays; helper must accept both."""
    vec_list = [0.0] * 767 + [3.0]  # only last component nonzero
    blob = _normalize_embedding_to_blob(vec_list)
    decoded = np.frombuffer(blob, dtype=np.float32)
    assert np.isclose(np.linalg.norm(decoded), 1.0, atol=1e-6)
    assert decoded[-1] > 0  # sign preserved


def test_normalize_embedding_raises_on_zero_norm():
    """Zero-norm input raises - never silently stored as a zero-vector."""
    vec = np.zeros(768, dtype=np.float32)
    with pytest.raises(ValueError, match="zero-norm"):
        _normalize_embedding_to_blob(vec)


def test_normalize_embedding_raises_on_nan_or_inf():
    """NaN/Inf must surface loudly - otherwise the row's dot product is also
    NaN, and ``sim < threshold`` evaluates False so it would silently pass
    the cosine filter and land in the HIGH set. Reject at storage time."""
    vec_nan = np.ones(768, dtype=np.float32)
    vec_nan[42] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        _normalize_embedding_to_blob(vec_nan)
    vec_inf = np.ones(768, dtype=np.float32)
    vec_inf[7] = float("inf")
    with pytest.raises(ValueError, match="non-finite"):
        _normalize_embedding_to_blob(vec_inf)
