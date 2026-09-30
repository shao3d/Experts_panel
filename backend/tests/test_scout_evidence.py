"""Only completed, fully returned source text is evidence."""
from src.utils.scout_evidence import read_evidence, finished
import json


def event(offset, text, total=10, status='completed'):
    source = {'source_key':'video_hub:1','content':text,'content_offset':offset,'content_chars':total}
    return {'type':'tool_use','part':{'tool':'scout','state':{'status':status,'input':{'command':'show'},'output':json.dumps([source])}}}


def test_source_pages_require_contiguous_complete_reading():
    assert not read_evidence([event(0,'abcd')])['video_hub:1']['fully_read']
    assert not read_evidence([event(0,'abcd'),event(6,'ghij')])['video_hub:1']['fully_read']
    source = read_evidence([event(0,'abcd'),event(4,'efghij')])['video_hub:1']
    assert source['fully_read'] and source['content'] == 'abcdefghij'


def test_failed_read_and_conflicting_pages_are_rejected():
    assert read_evidence([event(0,'abcdefghij',status='failed')]) == {}
    source = read_evidence([event(0,'abcdefghij'),event(0,'different!')])['video_hub:1']
    assert not source['fully_read'] and source['conflict']


def test_final_text_does_not_prove_finished_run():
    assert not finished([{'type':'text','part':{'text':'Answer'}}])
    assert finished([{'type':'step_finish','part':{'reason':'stop'}}])
    assert not finished([{'type':'step_finish','part':{'reason':'stop'}},{'type':'error'}])


def test_degraded_search_cannot_prove_absence():
    from src.utils.scout_evidence import tool_calls
    degraded={'type':'tool_use','part':{'tool':'scout','state':{'status':'completed','input':{'command':'search','query':'test'},'output':json.dumps({'status':'partial','warnings':['vector_failed'],'results':[]})}}}
    assert not tool_calls([degraded])[0]['successful']
