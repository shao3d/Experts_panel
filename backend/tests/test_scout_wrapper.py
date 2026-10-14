"""The CLI must not turn partial engine output into a successful result."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('engine_exit,finished,integrity_exit,expected',[(0,True,0,0),(124,True,0,124),(0,False,0,3),(0,True,1,4)])
@pytest.mark.parametrize('engine_name',['sol','bunny','glm'])
def test_wrapper_preserves_failure_status(tmp_path,engine_exit,finished,integrity_exit,expected,engine_name):
    scripts=tmp_path/'scripts'; scripts.mkdir()
    backend=tmp_path/'backend'; (backend/'scripts').mkdir(parents=True)
    (backend/'.venv/bin').mkdir(parents=True)
    (backend/'.venv/bin/python').symlink_to(shutil.which('python3'))
    shutil.copy(ROOT/'scripts/expert_scout.sh',scripts/'expert_scout.sh')
    shutil.copy(ROOT/'scripts/expert_scout_filter.py',scripts/'expert_scout_filter.py')
    shutil.copy(ROOT/'scripts/expert_scout_codex.py',scripts/'expert_scout_codex.py')
    (tmp_path/'.opencode/agents').mkdir(parents=True)
    shutil.copy(ROOT/'.opencode/agents/expert-scout.md',tmp_path/'.opencode/agents/expert-scout.md')
    shutil.copytree(ROOT/'backend/src/utils',backend/'src/utils',ignore=shutil.ignore_patterns('__pycache__'))
    (backend/'scripts/verify_citations.py').write_text(f'raise SystemExit({integrity_exit})\n')
    engine=tmp_path/'engine'
    text_event={'type':'item.completed','item':{'type':'agent_message','text':'Test answer'}} if engine_name=='sol' else {'type':'text','part':{'text':'Test answer'}}
    finish_event={'type':'turn.completed'} if engine_name=='sol' else {'type':'step_finish','part':{'reason':'stop'}}
    import json
    engine.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'+
                      'open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"engine-args.txt"),"w").write("\\n".join(sys.argv[1:]))\n'+
                      f'print({json.dumps(text_event)!r})\n'+
                      (f'print({json.dumps(finish_event)!r})\n' if finished else '')+
                      f'raise SystemExit({engine_exit})\n')
    engine.chmod(0o700)
    proc=subprocess.run(['bash',str(scripts/'expert_scout.sh'),'Synthetic question'],env={**os.environ,'EXPERT_SCOUT_ENGINE':engine_name,'OPENCODE_BIN':str(engine),'CODEX_BIN':str(engine)},capture_output=True,text=True)
    # OpenCode 2 streams end with the answer text and no terminal event; the
    # wrapper normalizes that to a completed turn (ensure_turn_completed), so
    # the v1 "unfinished" failure only applies to explicit-terminal engines.
    if engine_name!='sol' and (engine_exit,finished,integrity_exit)==(0,False,0):
        expected=0
    assert proc.returncode==expected,proc.stderr
    assert 'Test answer' in proc.stdout
    assert ('status=completed' in proc.stderr)==(expected==0)
    if engine_name=='glm':
        args=(tmp_path/'engine-args.txt').read_text()
        assert '--model' in args and 'commandcode/z-ai/glm-5.3-flash' in args


def test_wrapper_openv2_stream_without_answer_still_unfinished(tmp_path):
    """A clean OpenCode 2 exit with no answer text must stay a failure."""
    scripts=tmp_path/'scripts'; scripts.mkdir()
    backend=tmp_path/'backend'; (backend/'scripts').mkdir(parents=True)
    (backend/'.venv/bin').mkdir(parents=True)
    (backend/'.venv/bin/python').symlink_to(shutil.which('python3'))
    shutil.copy(ROOT/'scripts/expert_scout.sh',scripts/'expert_scout.sh')
    shutil.copy(ROOT/'scripts/expert_scout_filter.py',scripts/'expert_scout_filter.py')
    shutil.copytree(ROOT/'backend/src/utils',backend/'src/utils',ignore=shutil.ignore_patterns('__pycache__'))
    (tmp_path/'.opencode/agents').mkdir(parents=True)
    shutil.copy(ROOT/'.opencode/agents/expert-scout.md',tmp_path/'.opencode/agents/expert-scout.md')
    (backend/'scripts/verify_citations.py').write_text('raise SystemExit(0)\n')
    engine=tmp_path/'engine'
    engine.write_text('#!/usr/bin/env python3\n'
                      'print(\'{"type":"step_start","part":{}}\')\n'
                      'raise SystemExit(0)\n')
    engine.chmod(0o700)
    proc=subprocess.run(['bash',str(scripts/'expert_scout.sh'),'Synthetic question'],env={**os.environ,'EXPERT_SCOUT_ENGINE':'glm','OPENCODE_BIN':str(engine)},capture_output=True,text=True)
    assert proc.returncode==3,proc.stderr
    assert 'empty answer' in proc.stderr


def test_wrapper_default_engine_is_glm(tmp_path):
    scripts=tmp_path/'scripts'; scripts.mkdir()
    backend=tmp_path/'backend'; (backend/'scripts').mkdir(parents=True)
    (backend/'.venv/bin').mkdir(parents=True)
    (backend/'.venv/bin/python').symlink_to(shutil.which('python3'))
    shutil.copy(ROOT/'scripts/expert_scout.sh',scripts/'expert_scout.sh')
    shutil.copy(ROOT/'scripts/expert_scout_filter.py',scripts/'expert_scout_filter.py')
    (tmp_path/'.opencode/agents').mkdir(parents=True)
    shutil.copy(ROOT/'.opencode/agents/expert-scout.md',tmp_path/'.opencode/agents/expert-scout.md')
    shutil.copytree(ROOT/'backend/src/utils',backend/'src/utils',ignore=shutil.ignore_patterns('__pycache__'))
    (backend/'scripts/verify_citations.py').write_text('raise SystemExit(0)\n')
    import json
    engine=tmp_path/'engine'
    engine.write_text('#!/usr/bin/env python3\nimport json\n'+
                      'print(json.dumps({"type":"text","part":{"text":"Test answer"}}))\n'+
                      'print(json.dumps({"type":"step_finish","part":{"reason":"stop"}}))\n')
    engine.chmod(0o700)
    env={key:value for key,value in os.environ.items() if key!='EXPERT_SCOUT_ENGINE'}
    proc=subprocess.run(['bash',str(scripts/'expert_scout.sh'),'Synthetic question'],
                        env={**env,'OPENCODE_BIN':str(engine)},capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    meta=next((tmp_path/'output/scout_runs').glob('*/meta.txt')).read_text()
    assert 'engine: glm' in meta
    assert 'model: commandcode/z-ai/glm-5.3-flash' in meta
