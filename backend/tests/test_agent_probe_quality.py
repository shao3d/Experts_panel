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


def successful_run(keys):
    return {'answer_keys': keys, 'abstain_signal': False, 'exit': 0,
            'run_completed': True, 'integrity': {'status': 'completed'},
            'read_keys': keys, 'read_total': len(keys)}


def test_one_source_request_accepts_one_of_several_alternatives(monkeypatch):
    module = probe()
    monkeypatch.setattr(module.probe, 'keys_exist', lambda keys: dict.fromkeys(keys, True))
    fixture = {'id': 'one', 'kind': 'hit', 'expected_keys': ['expert:1', 'expert:2'],
               'min_hits': 1, 'max_sources': 1}
    result = module.score_fixture(fixture, successful_run(['expert:2']))
    assert result['recall'] == 0.5
    assert result['automatic_pass'] is True
    assert module.score_fixture(fixture, successful_run(['expert:1', 'expert:2']))['automatic_pass'] is False


def test_completed_run_with_no_answer_sources_fails():
    module = probe()
    result = module.score_fixture({'id': 'hit', 'kind': 'hit', 'expected_keys': ['expert:1'], 'min_hits': 1}, successful_run([]))
    assert result['run_succeeded'] is True
    assert result['automatic_pass'] is False


def test_strict_abstention_rejects_citations_when_context_is_disallowed(monkeypatch):
    module = probe()
    monkeypatch.setattr(module.probe, 'keys_exist', lambda keys: dict.fromkeys(keys, True))
    run = successful_run(['expert:1']); run['abstain_signal'] = True
    result = module.score_fixture({'id': 'negative', 'kind': 'negative_control', 'expected_keys': []}, run)
    assert not result['hallucinated']
    assert result['abstain_ok'] is False
    assert result['automatic_pass'] is False


def test_context_abstention_requires_honesty_existing_and_read_sources(monkeypatch):
    module = probe()
    fixture = next(f for f in module.probe.load_fixtures() if f['id'] == 'negative_control_out_of_corpus')
    monkeypatch.setattr(module.probe, 'keys_exist', lambda keys: dict.fromkeys(keys, True))
    run = successful_run(['expert:1']); run['abstain_signal'] = True
    # Mechanical success still requires a separate semantic review of context.
    assert module.score_fixture(fixture, run)['automatic_pass'] is True
    assert module.score_fixture(fixture, {**run, 'abstain_signal': False})['automatic_pass'] is False
    assert module.score_fixture(fixture, {**run, 'read_keys': []})['automatic_pass'] is False
    monkeypatch.setattr(module.probe, 'keys_exist', lambda keys: dict.fromkeys(keys, False))
    assert module.score_fixture(fixture, run)['automatic_pass'] is False


def test_paired_questions_are_in_default_exam_and_share_reviewed_gold():
    module = probe()
    fixtures = {f['id']: f for f in module.probe.load_fixtures()}
    for variant, original in [
        ('videohub_liquid_plain_language', 'videohub_liquid_speed_ramp'),
        ('videohub_character_sheet_false_premise', 'videohub_character_sheet_model'),
    ]:
        assert variant in module.AGENT_FIXTURES
        assert fixtures[variant]['question'] != fixtures[original]['question']
        assert fixtures[variant]['expected_keys'] == fixtures[original]['expected_keys']
        assert fixtures[variant]['evidence'] == fixtures[original]['evidence']


def test_facets_require_sources_for_both_techniques(monkeypatch):
    module = probe()
    monkeypatch.setattr(module.probe, 'keys_exist', lambda keys: dict.fromkeys(keys, True))
    fixture = {'id': 'facets', 'kind': 'hit', 'expected_keys': ['expert:1', 'expert:2', 'expert:3'],
               'min_hits': 2, 'required_groups': {'grid': ['expert:1', 'expert:2'], 'interpolation': ['expert:3']}}
    result = module.score_fixture(fixture, successful_run(['expert:1', 'expert:2']))
    assert result['missing_groups'] == ['interpolation'] and result['automatic_pass'] is False
    assert module.score_fixture(fixture, successful_run(['expert:1', 'expert:3']))['automatic_pass'] is True


def test_missing_integrity_is_not_success():
    module = probe(); run = successful_run([]); run.pop('integrity'); run['abstain_signal'] = True
    assert module.score_fixture({'id': 'gap', 'kind': 'gap', 'expected_keys': []}, run)['automatic_pass'] is False


def test_quality_failure_returns_nonzero(monkeypatch):
    import sys
    module = probe()
    monkeypatch.setattr(module, 'run_all', lambda *args: {'summary': {'failed_runs': 0, 'quality_failures': 1}})
    monkeypatch.setattr(sys, 'argv', ['agent_probe', '--run'])
    assert module.main() == 1


def test_cli_forwards_selected_engine_and_questions(monkeypatch):
    import sys
    module = probe()
    calls = []

    def run_all(*args):
        calls.append(args)
        return {'summary': {'failed_runs': 0, 'quality_failures': 0}}

    monkeypatch.setattr(module, 'run_all', run_all)
    monkeypatch.setattr(sys, 'argv', ['agent_probe', '--run', '--engine', 'luna',
                                    '--fixtures', 'kling_elements_stability', '--show-answers'])
    assert module.main() == 0
    assert calls == [(900, ['kling_elements_stability'], True, 'luna')]
