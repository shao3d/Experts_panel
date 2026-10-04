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


@pytest.mark.parametrize('marker', ['-', '*', '+', '1.', '1)'])
def test_list_quote_is_bound_to_its_item(verifier, marker):
    quote = 'Exact camera path and lighting instruction'
    sources = {'video_hub:1': 'Different source', 'video_hub:2': quote}
    answer = (f'{marker} Previous item video_hub:1\n'
              f'{marker} “{quote}” with a long explanation of the source limitations.\n'
              '  Continuation with its citation: video_hub:2')
    assert verifier.bound_quote_status(answer, sources)[quote] == 'ok'
    wrong = answer.replace('video_hub:2', 'video_hub:1')
    assert verifier.bound_quote_status(wrong, sources)[quote] == 'unverified'
    unbound = answer.replace('video_hub:2', '') + '\n- Next item video_hub:2'
    assert verifier.bound_quote_status(unbound, sources)[quote] == 'unbound'


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


@pytest.mark.parametrize("matching_quote", [True, False])
def test_fixture_key_and_quote_validation(verifier, tmp_path, monkeypatch, capsys, matching_quote):
    """CLI validation accepts source text and rejects a fabricated quote offline."""
    quote = "Exact synthetic source words about camera movement"
    source_text = quote if matching_quote else "A different primary source about lighting"
    calls = []

    def lookup(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, json.dumps([
            {"source_key": "fixture_author:1", "content": source_text},
        ]), "")

    monkeypatch.setattr(verifier.subprocess, "run", lookup)
    answer = tmp_path / "answer.md"
    answer.write_text(f"Source fixture_author:1 — «{quote}».", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["verify", "--answer", str(answer), "--json"])
    assert verifier.main() == (0 if matching_quote else 1)
    report = json.loads(capsys.readouterr().out)
    assert report["keys_missing"] == []
    assert report["quotes_unverified"] == ([] if matching_quote else [quote])
    assert len(calls) == 1
    assert calls[0][2:] == ["show", "fixture_author:1", "--comments-limit", "0", "--json"]


def test_hallucinated_key_fails_and_annotates(verifier, tmp_path, monkeypatch, capsys):
    """A missing source must fail and annotate the answer without a live DB."""
    def lookup(command, **kwargs):
        assert command[2:] == ["show", "video_hub:47", "--comments-limit", "0", "--json"]
        return subprocess.CompletedProcess(command, 0, json.dumps([
            {"source_key": "video_hub:47", "error": "not_found"},
        ]), "")

    monkeypatch.setattr(verifier.subprocess, "run", lookup)
    answer = tmp_path / "answer.md"
    original = "Ключ `video_hub:47` я выдумал."
    answer.write_text(original, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["verify", "--answer", str(answer), "--annotate"])
    assert verifier.main() == 1
    assert "MISSING KEY: video_hub:47" in capsys.readouterr().out
    text = answer.read_text(encoding="utf-8")
    assert text.startswith("# WARNING:") and original in text
