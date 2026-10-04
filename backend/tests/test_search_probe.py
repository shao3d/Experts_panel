"""Search probe regression tests (fixture-based, verified ground truth).

Fixture shape and mocked lookup checks always run; corpus and network checks are gated by
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


@pytest.mark.skipif(os.getenv("SEARCH_PROBE") != "1", reason="set SEARCH_PROBE=1 to validate the real corpus")
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


def test_changed_gold_cannot_silently_pass_baseline(tmp_path, monkeypatch):
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'summary': {}, 'results': [{'id': 'x', 'kind': 'hit', 'fixture_signature': 'old'}]}))
    monkeypatch.setattr(probe, 'BASELINE_PATH', baseline)
    problems = probe.compare_to_baseline({'summary': {}, 'results': [{'id': 'x', 'kind': 'hit', 'fixture_signature': 'new'}]})
    assert any('contract changed' in p for p in problems)
    assert any('missing' in p for p in probe.compare_to_baseline({'summary': {}, 'results': []}))


def test_rebaseline_keeps_original_search_date(tmp_path, monkeypatch):
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'generated_at': '2026-09-30 23:00:00', 'search_as_of': '2026-09-29T12:00:00'}))
    monkeypatch.setattr(probe, 'BASELINE_PATH', baseline)
    assert probe._probe_now() == '2026-09-29T12:00:00'


@pytest.mark.parametrize('recall,exit_code', [(1.0, 0), (0.5, 1)])
def test_saved_comparison_is_offline_and_preserves_failure(tmp_path, monkeypatch, capsys, recall, exit_code):
    baseline = tmp_path / 'baseline.json'
    saved = tmp_path / 'saved.json'
    row = {'id': 'x', 'kind': 'hit', 'fixture_signature': 'same',
           'recall@10': 1.0, 'recall@20': 1.0, 'recall@40': 1.0,
           'mrr@10': 1.0, 'hidden_total': 0}
    report = {'generated_at': '2026-10-04', 'summary': {}, 'results': [row]}
    baseline.write_text(json.dumps(report))
    row['recall@10'] = recall
    saved.write_text(json.dumps(report))
    original = baseline.read_bytes()
    monkeypatch.setattr(probe, 'BASELINE_PATH', baseline)
    monkeypatch.setattr(probe, 'run_probe', lambda: pytest.fail('must not run live search'))
    monkeypatch.setattr(sys, 'argv', ['search_probe.py', '--check-saved', str(saved)])
    assert probe.main() == exit_code
    output = capsys.readouterr().out
    assert 'no new search performed' in output
    assert 'not Scout answer quality' in output
    assert baseline.read_bytes() == original


def test_saved_report_cannot_be_used_to_silently_overwrite_baseline(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['search_probe.py', '--check-saved', 'unused.json',
                                   '--write-baseline', '--baseline-note', 'invalid combination'])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2


def test_grid_baseline_matches_reviewed_contract():
    baseline = json.loads(probe.BASELINE_PATH.read_text())
    row = next(r for r in baseline['results'] if r['id'] == 'grid_prompting')
    fixture = next(f for f in fixtures if f['id'] == 'grid_prompting')
    assert row['fixture_signature'] == probe.fixture_signature(fixture)
    assert row['expected'] == fixture['expected_keys']


def test_reviewed_agent_gold_has_evidence():
    for fixture in fixtures:
        assert 0 <= fixture['min_hits'] <= len(fixture['expected_keys'])
        if fixture.get('reviewed_at'):
            assert fixture.get('rubric')
            assert set(fixture.get('evidence', {})) == set(fixture['expected_keys'])
        if fixture.get('max_sources'):
            assert fixture['min_hits'] <= fixture['max_sources']
        for keys in fixture.get('required_groups', {}).values():
            assert keys and set(keys) <= set(fixture['expected_keys'])
        args = fixture.get('search_args', [])
        if '--experts' in args:
            experts = args[args.index('--experts')+1].split(',')
            assert all(key.split(':')[0] in experts for key in fixture['expected_keys'])
