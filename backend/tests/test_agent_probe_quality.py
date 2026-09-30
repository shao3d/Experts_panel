"""Probe failures must not be scored as successful abstention."""
import importlib.util
import json
from pathlib import Path

PATH=Path(__file__).resolve().parents[1]/'scripts/agent_probe.py'


def probe():
    spec=importlib.util.spec_from_file_location('probe_quality_test',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_failed_run_is_not_honest_absence():
    module=probe()
    fixture={'id':'gap','kind':'gap','expected_keys':[]}
    run={'answer_keys':[],'abstain_signal':True,'exit':4,'run_completed':True,'read_keys':[]}
    result=module.score_fixture(fixture,run)
    assert result['abstain_ok'] is False and result['run_succeeded'] is False


def test_missing_result_is_regression(tmp_path):
    module=probe()
    before=tmp_path/'before.json';after=tmp_path/'after.json'
    before.write_text(json.dumps({'summary':{},'results':[{'id':'required'}]}))
    after.write_text(json.dumps({'summary':{},'results':[]}))
    assert module.compare(str(before),str(after))==1
