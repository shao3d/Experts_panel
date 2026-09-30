"""The CLI must not turn partial engine output into a successful result."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('engine_exit,finished,integrity_exit,expected',[(0,True,0,0),(124,True,0,124),(0,False,0,3),(0,True,1,4)])
@pytest.mark.parametrize('engine_name',['sol','bunny'])
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
    engine.write_text('#!/usr/bin/env python3\nimport json\n'+f'print({json.dumps(text_event)!r})\n'+
                      (f'print({json.dumps(finish_event)!r})\n' if finished else '')+
                      f'raise SystemExit({engine_exit})\n')
    engine.chmod(0o700)
    proc=subprocess.run(['bash',str(scripts/'expert_scout.sh'),'Synthetic question'],env={**os.environ,'EXPERT_SCOUT_ENGINE':engine_name,'OPENCODE_BIN':str(engine),'CODEX_BIN':str(engine)},capture_output=True,text=True)
    assert proc.returncode==expected,proc.stderr
    assert 'Test answer' in proc.stdout
    assert ('status=completed' in proc.stderr)==(expected==0)
