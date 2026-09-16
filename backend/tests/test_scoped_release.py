#!/usr/bin/env python3
"""Unit tests for scoped data release helpers (`--scope visual`)."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.expert_groups import resolve_expert_group  # noqa: E402
from src.services.drift_scheduler_service import DriftSchedulerService  # noqa: E402
from run_drift_service import _resolve_expert_ids  # noqa: E402


class _ScopeStub:
    def __init__(self, expert_ids):
        self.expert_ids = expert_ids


def test_scope_sql_without_scope_is_empty():
    params: dict = {}
    assert DriftSchedulerService._scope_sql(_ScopeStub(None), params) == ""
    assert params == {}


def test_scope_sql_builds_parameterized_in_clause():
    params: dict = {}
    sql = DriftSchedulerService._scope_sql(_ScopeStub(["a", "b"]), params)
    assert sql == " AND cgd.expert_id IN (:scope_expert_0, :scope_expert_1)"
    assert params == {"scope_expert_0": "a", "scope_expert_1": "b"}


def test_scope_sql_custom_column():
    params: dict = {}
    sql = DriftSchedulerService._scope_sql(_ScopeStub(["a"]), params, column="p.expert_id")
    assert sql == " AND p.expert_id IN (:scope_expert_0)"


def test_resolve_expert_ids_by_scope():
    ids = _resolve_expert_ids(Namespace(scope="visual", experts=None))
    assert ids == resolve_expert_group("visual")
    assert "acidcrunch" in ids and "refat" not in ids


def test_resolve_expert_ids_by_explicit_list():
    ids = _resolve_expert_ids(Namespace(scope=None, experts="acidcrunch, cgevent ,"))
    assert ids == ["acidcrunch", "cgevent"]


def test_resolve_expert_ids_without_scope():
    assert _resolve_expert_ids(Namespace(scope=None, experts=None)) is None


def test_resolve_expert_ids_unknown_scope_exits():
    with pytest.raises(SystemExit):
        _resolve_expert_ids(Namespace(scope="nosuch", experts=None))
