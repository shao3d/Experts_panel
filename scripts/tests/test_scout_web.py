import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import scout_web_api as api
from scripts.scout_web_progress import progress


def test_source_links_use_real_channel_and_segment_timestamp():
    assert api.source_link({"source_key": "acidcrunch:2511", "channel_username": "@AcidCrunch", "author_name": "Acid Crunch"}) == {
        "url": "https://t.me/AcidCrunch/2511", "label": "Acid Crunch · пост 2511"}
    link = api.source_link({"source_key": "video_hub:900000123", "video_url": "https://www.youtube.com/watch?v=qwGIwxZFc2I&t=1s&start=2#t=3",
                            "video_timestamp_s": 875, "author_name": "Dan Kieft", "video_title": "AI workflow"})
    assert link == {"url": "https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s", "label": "Dan Kieft · AI workflow · 14:35"}
    assert "900000123" not in link["url"]
    assert api.source_link({"source_key": "video_hub:1", "video_url": "https://youtu.be/qwGIwxZFc2I", "video_timestamp_s": 0})["url"].endswith("?t=0s")


@pytest.mark.parametrize("item", [
    {"source_key": "cgevent:42", "error": "not_found"},
    {"source_key": "cgevent:42"},
    {"source_key": "cgevent:42", "channel_username": "evil.example/channel"},
    {"source_key": "video_hub:1", "video_url": "javascript:alert(1)"},
    {"source_key": "video_hub:1", "video_url": "https://youtube.com.evil.example/watch?v=test"},
    {"source_key": "video_hub:1", "video_url": "https://user:password@youtube.com/watch?v=test"},
])
def test_unknown_or_unsafe_sources_do_not_get_invented_links(item):
    assert api.source_link(item) is None


@pytest.mark.asyncio
async def test_resolve_sources_batches_read_only_helper_and_discards_content(monkeypatch):
    commands = []
    class Process:
        returncode = 0
        async def communicate(self):
            return json.dumps([{"source_key": key, "channel_username": "ActualChannel", "content": "Do not send source text"}
                               for key in commands[-1][0][3:commands[-1][0].index("--json")]]).encode(), b""
    async def spawn(*args, **kwargs):
        commands.append((args, kwargs))
        return Process()
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setenv('SCOUT_WEB_PASSWORD_HASH', 'private')
    links = await api.resolve_sources('cgevent:1 acidcrunch:2 strangedalle:3 neyrograph:4 cgevent:1')
    assert len(commands) == 2 and len(links) == 4
    assert links['cgevent:1']['url'] == 'https://t.me/ActualChannel/1'
    assert all('SCOUT_WEB_PASSWORD_HASH' not in kwargs['env'] for _, kwargs in commands)
    assert all(args[2] == 'show' and '--max-chars' in args and '--json' in args for args, _ in commands)
    assert 'Do not send source text' not in json.dumps(links)


@pytest.mark.asyncio
async def test_old_saved_answers_get_links_without_rerunning_model(monkeypatch, tmp_path):
    original = api.Jobs
    monkeypatch.setattr(api, 'Jobs', lambda: original(tmp_path))
    monkeypatch.setenv('SCOUT_WEB_PASSWORD_HASH', hashlib.sha256(b'test-password').hexdigest())
    calls = []
    async def resolve(answer):
        calls.append(answer)
        return {'cgevent:42': {'url': 'https://t.me/cgevent/42', 'label': 'CGEVENT · пост 42'}}
    monkeypatch.setattr(api, 'resolve_sources', resolve)
    with TestClient(api.app) as client:
        api.app.state.jobs.save({'id': 'a'*32, 'status': 'completed', 'answer': 'Совет — cgevent:42'})
        headers = {'X-Scout-Password': 'test-password'}
        result = client.get('/jobs/' + 'a'*32, headers=headers).json()
        assert result['sources']['cgevent:42']['url'] == 'https://t.me/cgevent/42'
        client.get('/jobs/' + 'a'*32, headers=headers)
    assert calls == ['Совет — cgevent:42']


def test_progress_handles_live_and_finished_opencode_tool_events_without_leaking_queries():
    assert progress({'type': 'reasoning', 'text': 'private'}) is None
    assert progress({'type': 'tool_use', 'part': {'tool': 'scout', 'state': {
        'status': 'running', 'input': {'command': 'search', 'experts': 'video_hub', 'query': 'private question'}}}}) == 'Ищу в ВидеоХабе…'
    assert progress({'type': 'tool_use', 'part': {'tool': 'scout', 'state': {
        'status': 'completed', 'input': {'command': 'search', 'group': 'visual', 'query': 'private question'}}}}) == 'Просматриваю найденные материалы…'
    assert progress({'type': 'tool_use', 'part': {'tool': 'scout', 'state': {
        'status': 'running', 'input': {'command': 'show', 'source_keys': ['private:123']}}}}) == 'Читаю первоисточники…'
    assert progress({'type': 'tool_use', 'part': {'tool': 'scout', 'state': {
        'status': 'running', 'input': {'command': 'lesson_search', 'query': 'private question'}}}}) == 'Ищу в опубликованных уроках…'
    assert progress({'type': 'item.started', 'item': {'type': 'mcp_tool_call', 'arguments': {
        'command': 'search', 'experts': 'video_hub', 'query': 'private question'}}}) == 'Ищу в ВидеоХабе…'
    assert progress({'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'arguments': {
        'command': 'show', 'source_keys': ['private:123']}}}) == 'Сопоставляю источники…'
    assert progress({'type': 'step_finish', 'part': {'reason': 'stop'}}) == 'Проверяю ответ…'
    assert progress({'type': 'tool_use', 'part': {'tool': 'other', 'state': {'input': {'query': 'secret'}}}}) is None


def test_detect_language_uses_majority_of_letters():
    assert api.detect_language('How do I keep a character consistent across scenes?') == 'English'
    assert api.detect_language('Как сохранить персонажа между сценами?') == 'Russian'
    assert api.detect_language('How сохранить character consistency?') == 'English'
    assert api.detect_language('Какие camera moves сохранить?') == 'Russian'
    assert api.detect_language('123?!') == 'English'


@pytest.mark.asyncio
@pytest.mark.parametrize(("question", "expected"), [
    ("How to keep a character consistent?", "English"),
    ("Как сохранить персонажа?", "Russian"),
])
async def test_job_runner_prompts_in_detected_language_and_streams_progress(monkeypatch, tmp_path, question, expected):
    jobs = api.Jobs(tmp_path)
    original_spawn = asyncio.create_subprocess_exec
    commands = []

    async def spawn(*args, **kwargs):
        commands.append((args, kwargs))
        script = "import json,sys; print('Answer in the requested language'); print('SCOUT_PROGRESS ' + json.dumps('Searching…', ensure_ascii=False), file=sys.stderr)"
        return await original_spawn(sys.executable, '-c', script,
                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                    start_new_session=True)

    async def empty_sources(_answer):
        return {}

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr(api, 'ROOT', tmp_path)
    monkeypatch.setattr(api, 'resolve_sources', empty_sources)
    job = {'id': 'c'*32, 'question': question, 'status': 'running', 'started_at': 0,
           'answer': '', 'message': 'Starting', 'elapsed': 0}
    jobs.active, jobs.current = job['id'], job
    await jobs.run(job)

    sent_question = commands[0][0][-1]
    assert f"Answer entirely in {expected}" in sent_question
    assert question in sent_question
    assert job['question'] == question
    assert job['status'] == 'completed'
    assert job['answer'] == 'Answer in the requested language\n'
    saved = jobs.get(job['id'])
    assert saved['question'] == question
    assert saved['status'] == 'completed'
    assert 'SCOUT_WEB_PASSWORD_HASH' not in commands[0][1]['env']


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
        progress_json = json.dumps('Читаю первоисточники…', ensure_ascii=False)
        source = "import sys; print('Answer'); print('SCOUT_PROGRESS ' + " + repr(progress_json) + ", file=sys.stderr); sys.exit(" + str(code) + ")"
        return await original(sys.executable, '-c', source,
                              stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                              start_new_session=True)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr(api, 'ROOT', tmp_path)
    monkeypatch.setattr(api, 'resolve_sources', lambda answer: asyncio.sleep(0, result={}))
    monkeypatch.setattr(api, 'detect_language', lambda question: 'English')
    job = {'id': 'b'*32, 'question': 'How to keep the character consistent?', 'status': 'running',
           'started_at': 0, 'answer': '', 'message': 'Starting', 'elapsed': 0}
    jobs.active = job['id']
    jobs.current = job
    await jobs.run(job)
    result = jobs.get(job['id'])
    assert result['status'] == status
    assert 'Answer' in result['answer']
    assert result['message'] == ('Готово' if status == 'completed' else 'Ответ не прошёл полную проверку' if status == 'partial' else 'Поиск не завершился. Можно повторить вопрос.')
    assert 'Answer entirely in English' in commands[0][0][-1]
    assert 'How to keep the character consistent?' in commands[0][0][-1]
    assert 'SCOUT_WEB_PASSWORD_HASH' not in commands[0][1]['env']
