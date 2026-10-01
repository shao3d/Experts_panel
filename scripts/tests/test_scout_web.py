import asyncio
import hashlib
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import scout_web_api as api
from scripts.scout_web_progress import progress


def test_progress_does_not_expose_content_or_internal_reasoning():
    assert progress({'item': {'type': 'reasoning', 'text': 'private'}}) is None
    assert progress({'item': {'type': 'mcp_tool_call', 'arguments': {
        'command': 'search', 'experts': 'video_hub', 'query': 'private question'}}}) == 'Ищу в ВидеоХабе…'
    assert progress({'item': {'type': 'mcp_tool_call', 'arguments': {
        'command': 'search', 'group': 'visual'}}}) == 'Ищу в Telegram…'


def test_auth_cors_and_private_results(monkeypatch, tmp_path):
    original = api.Jobs
    monkeypatch.setattr(api, 'Jobs', lambda: original(tmp_path))
    monkeypatch.setenv('SCOUT_WEB_PASSWORD_HASH', hashlib.sha256(b'test-password').hexdigest())
    with TestClient(api.app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/auth').status_code == 401
        assert client.get('/auth', headers={'X-Scout-Password': 'wrong'}).status_code == 401
        assert client.get('/auth', headers={'X-Scout-Password': 'test-password'}).status_code == 200
        assert client.get('/jobs/' + 'a'*32).status_code == 401
        response = client.options('/jobs', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'POST'})
        assert 'access-control-allow-origin' not in response.headers
        assert client.post('/jobs', json={'question': ' '}, headers={'X-Scout-Password': 'test-password'}).status_code == 422


def test_results_survive_restart_and_validate_ids(tmp_path):
    jobs = api.Jobs(tmp_path)
    jobs.save({'id': 'a'*32, 'status': 'running', 'message': 'running'})
    jobs = api.Jobs(tmp_path)
    assert jobs.get('a'*32)['status'] == 'error'
    with pytest.raises(api.HTTPException):
        jobs.get('../../secret')


@pytest.mark.asyncio
async def test_busy_stop_and_kill_process_tree(monkeypatch, tmp_path):
    jobs = api.Jobs(tmp_path)
    original_spawn = asyncio.create_subprocess_exec
    async def spawn(*args, **kwargs):
        return await original_spawn(sys.executable, '-c', 'import time; time.sleep(60)',
                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                   start_new_session=True)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    job = await jobs.start('test')
    while jobs.process is None:
        await asyncio.sleep(.01)
    pid = jobs.process.pid
    with pytest.raises(api.HTTPException) as error:
        await jobs.start('second')
    assert error.value.status_code == 409
    result = await jobs.stop(job['id'])
    assert result['status'] == 'stopped' and not result['answer']
    assert jobs.active is None
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_stop_before_process_starts(tmp_path):
    jobs = api.Jobs(tmp_path)
    job = await jobs.start('test')
    result = await jobs.stop(job['id'])
    assert result['status'] == 'stopped'
    assert jobs.active is None


@pytest.mark.asyncio
@pytest.mark.parametrize('code,status', [(0, 'completed'), (4, 'partial'), (1, 'error')])
async def test_completed_partial_and_failed_runs_are_distinct(monkeypatch, tmp_path, code, status):
    jobs = api.Jobs(tmp_path)
    original = asyncio.create_subprocess_exec
    commands = []
    async def spawn(*args, **kwargs):
        commands.append((args, kwargs))
        source = "import sys; print('Answer'); print('SCOUT_PROGRESS \\\"Читаю источники…\\\"', file=sys.stderr); sys.exit(" + str(code) + ")"
        return await original(sys.executable, '-c', source,
                              stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                              start_new_session=True)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    job = await jobs.start('$(not a shell command)')
    await jobs.task
    result = jobs.get(job['id'])
    assert result['status'] == status
    assert 'Answer' in result['answer']
    assert commands[0][0][-1] == '$(not a shell command)'
    assert 'SCOUT_WEB_PASSWORD_HASH' not in commands[0][1]['env']
