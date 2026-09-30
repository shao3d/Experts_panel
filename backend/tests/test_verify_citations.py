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


def test_quote_fragments_cannot_cross_sources_or_reverse_order(verifier):
    sources = {'a:1':'First long fragment about lighting', 'b:2':'Second long fragment about movement'}
    assert verifier.quote_in_sources('First long fragment about lighting … Second long fragment about movement',sources) == 'unverified'
    assert verifier.quote_in_sources('movement … lighting', {'a:1':'lighting comes before movement'}) == 'skipped'
    assert verifier.quote_in_sources('Second long fragment about movement … First long fragment about lighting',
                                     {'a:1':'First long fragment about lighting. Second long fragment about movement'}) == 'unverified'


def test_quote_must_match_its_local_source_and_not_summary(verifier):
    text = 'Exact primary source words about camera movement'
    sources = {'video_hub:1':text, 'video_hub:2':'Different words'}
    answer = f'«{text}» — video_hub:2.\n\nOther source: video_hub:1.'
    assert verifier.bound_quote_status(answer,sources)[text] == 'unverified'
    assert verifier.quote_in_sources(text, {'video_hub:1':f'TITLE: title\nSUMMARY: {text}\n---\nCONTENT:\nActual different words'}) == 'unverified'
    assert verifier.extract_quotes(f'“{text}”') == [text]


def test_table_quote_is_bound_to_its_row_not_closer_neighbor(verifier):
    quote='копировать траекторию камеры'
    sources={'acidcrunch:1320':'Different source', 'acidcrunch:1276':f'— {quote}'}
    answer=f'| Other | acidcrunch:1320 |\n| «{quote}» plus a lengthy explanation of limitations and testing | acidcrunch:1276 |'
    assert verifier.bound_quote_status(answer,sources)[quote]=='ok'
    wrong=answer.replace('acidcrunch:1276','acidcrunch:1320')
    assert verifier.bound_quote_status(wrong,sources)[quote]=='unverified'


@pytest.mark.parametrize('returncode,output', [(1,'[]'),(0,'invalid'),(0,'[]')])
def test_source_lookup_cannot_silently_drop_keys(verifier, monkeypatch, returncode, output):
    monkeypatch.setattr(verifier.subprocess,'run',lambda *args,**kwargs: subprocess.CompletedProcess([],returncode,output,''))
    with pytest.raises(RuntimeError):
        verifier.fetch_sources(['video_hub:1'])


def test_preview_or_failed_show_never_validates_citation(verifier):
    source = {'source_key':'video_hub:1','content':'actual primary text','content_chars':19}
    def event(command,status='completed'):
        return {'type':'tool_use','part':{'tool':'scout','state':{'status':status,'input':{'command':command},'output':json.dumps([source])}}}
    stop = {'type':'step_finish','part':{'reason':'stop'}}
    for events in ([event('digest'),stop],[event('show','failed'),stop]):
        report = verifier.assess_answer('Answer video_hub:1',events,lookup_unread=False)
        assert report['status']=='partial' and report['keys_unread']==['video_hub:1']
    assert verifier.assess_answer('Answer video_hub:1',[event('show'),stop],lookup_unread=False)['status']=='completed'


def test_absence_needs_successful_searches_and_finished_run(verifier):
    answer='Не нашёл подтверждений в проверенных источниках.'
    def event(command,status='completed',query=''):
        return {'type':'tool_use','part':{'tool':'scout','state':{'status':status,'input':{'command':command,'query':query},'output':'{}'}}}
    events=[event('search',query=str(i)) for i in range(3)]+[event('digest')]
    assert verifier.assess_answer(answer,events,lookup_unread=False)['status']=='partial'
    events.append({'type':'step_finish','part':{'reason':'stop'}})
    assert verifier.assess_answer(answer,events,lookup_unread=False)['status']=='completed'
    events[0]=event('search','failed')
    assert verifier.assess_answer(answer,events,lookup_unread=False)['status']=='partial'


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
