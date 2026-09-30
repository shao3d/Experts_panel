"""Deterministic citation/loop verifier tests (improvement: no LLM grading)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
VERIFY_PATH = BACKEND / "scripts" / "verify_citations.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier():
    return _load_module("verify_citations_under_test", VERIFY_PATH)


def test_extract_keys_filters_url_ports(verifier):
    keys = verifier.extract_keys("см. acidcrunch:1335 и localhost:56444, video_hub:47")
    assert keys == ["acidcrunch:1335", "video_hub:47"]


def test_extract_quotes_min_length(verifier):
    answer = 'Короткая «мало» и дословная «Extreme zoom in x 100 это достаточная цитата»'
    quotes = verifier.extract_quotes(answer)
    assert len(quotes) == 1
    assert "Extreme zoom" in quotes[0]


def test_quote_matching_ok_unverified_ellipsis(verifier):
    sources = {"a:1": "here is the Extreme zoom in x 100 text and more words after it and more words here done"}
    assert verifier.quote_in_sources("Extreme zoom in x 100 text and more", sources) == "ok"
    assert verifier.quote_in_sources("совсем другая цитата про кошки и молоко", sources) == "unverified"
    ellipsis = "Extreme zoom in x 100 text … words after it and more words here"
    assert verifier.quote_in_sources(ellipsis, sources) == "ok"
    assert verifier.quote_in_sources("мало", sources) == "skipped"


def test_detect_loops_flags_three_identical_calls(verifier, tmp_path):
    def ev(args, typ="tool_use"):
        return {"type": typ, "part": {"type": "tool", "tool": "scout", "state": {"input": args}}}

    events = [
        ev({"command": "search", "query": "x"}),
        ev({"command": "search", "query": "x"}),
        ev({"command": "search", "query": "x"}),
        ev({"command": "search", "query": "x"}, typ="tool"),  # result mirror, must not double-count
        ev({"command": "show", "source_keys": ["a:1"]}),
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    loops = verifier.detect_loops(path)
    assert len(loops) == 1
    assert loops[0]["tool"] == "scout" and loops[0]["calls"] == 3

    events = events[:2]
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    assert verifier.detect_loops(path) == []


def test_real_key_and_quote_pass(tmp_path):
    """Integration: verified positive on the real corpus via the read-only helper."""
    answer = tmp_path / "answer.md"
    answer.write_text(
        "Находка: **`acidcrunch:1335`** — дословно «Extreme zoom in x 100 (ну и можешь написать куда зумить)».",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--answer", str(answer), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["keys_missing"] == []
    assert report["quotes_unverified"] == []


def test_hallucinated_key_fails_and_annotates(tmp_path):
    """Integration: invented key must fail the check and annotate the answer."""
    answer = tmp_path / "answer.md"
    original = "Ключ `video_hub:47` я выдумал."
    answer.write_text(original, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--answer", str(answer), "--annotate"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1
    report_line = proc.stdout
    assert "MISSING KEY: video_hub:47" in report_line
    text = answer.read_text(encoding="utf-8")
    assert text.startswith("# WARNING:") and original in text
