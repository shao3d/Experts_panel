"""Search probe regression tests (fixture-based, verified ground truth).

Fast checks always run; the network probe (embedding API) is gated by
SEARCH_PROBE=1 and measures recall/MRR against the baseline snapshot.

Run the full probe explicitly:
  SEARCH_PROBE=1 backend/.venv/bin/python -m pytest backend/tests/test_search_probe.py -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
PROBE_PATH = BACKEND / "scripts" / "search_probe.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("search_probe", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()
fixtures = probe.load_fixtures()


def test_fixture_shape():
    ids = [f["id"] for f in fixtures]
    assert len(ids) == len(set(ids)), "duplicate fixture ids"
    assert len(fixtures) >= 15, "fixture set unexpectedly small"
    kinds = {f["kind"] for f in fixtures}
    assert {"hit", "gap", "negative_control"} <= kinds
    for f in fixtures:
        assert f["question"].strip(), f
        if f["kind"] == "hit":
            assert f["expected_keys"], f
            assert f["min_hits"] >= 1, f


def test_key_lookup_batches_match_show_limit(monkeypatch):
    batches=[]
    def run(command,**kwargs):
        keys=command[3:command.index('--comments-limit')]
        batches.append(keys)
        return subprocess.CompletedProcess(command,0,json.dumps([{'source_key':key,'content':'text'} for key in keys]),'')
    monkeypatch.setattr(probe.subprocess,'run',run)
    keys=[f'video_hub:{i}' for i in range(8)]
    assert all(probe.keys_exist(keys).values())
    assert [len(batch) for batch in batches]==[3,3,2]


def test_key_lookup_failure_is_not_absence(monkeypatch):
    monkeypatch.setattr(probe.subprocess,'run',lambda *args,**kwargs:subprocess.CompletedProcess([],2,'',''))
    with pytest.raises(RuntimeError,match='existence check failed'):
        probe.keys_exist(['video_hub:1'])


def test_fixture_keys_exist_in_corpus():
    """Every expected_key must exist right now (guards against ghost ground truth)."""
    all_keys = sorted({k for f in fixtures for k in f["expected_keys"]})
    status = probe.keys_exist(all_keys)
    missing = [k for k, ok in status.items() if not ok]
    assert not missing, f"fixture keys missing from corpus: {missing}"


@pytest.mark.skipif(os.getenv("SEARCH_PROBE") != "1", reason="set SEARCH_PROBE=1 to run the network probe")
def test_search_probe_no_regression():
    result = probe.run_probe()
    problems = probe.compare_to_baseline(result)
    assert not problems, "search probe regressions:\n" + "\n".join(problems)
    summary = result["summary"]
    assert summary["mean_recall@10"] is not None
    # sanity floor: the probe itself must be healthy, not just non-regressing
    assert summary["mean_recall@10"] >= 0.15, summary


@pytest.mark.skipif(os.getenv("SEARCH_PROBE") != "1", reason="set SEARCH_PROBE=1 to run the network probe")
def test_negative_control_returns_no_fixture_keys():
    """Out-of-corpus question must not return keys that look verified.

    At retrieval level nothing is expected to match; this pins that the probe
    does not silently start 'finding' fixture keys in unrelated answers.
    """
    fixture = next(f for f in fixtures if f["kind"] == "negative_control")
    returned = probe.run_search(fixture["question"])["keys"]
    assert not (set(returned) & {k for f in fixtures for k in f["expected_keys"]})
