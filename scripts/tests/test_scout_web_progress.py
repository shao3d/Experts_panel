import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scout_web_progress.py"
spec = importlib.util.spec_from_file_location("scout_web_progress", SCRIPT)
progress_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress_module)


def test_opencode_search_progress_hides_private_query_and_changes_on_completion():
    started = {
        "type": "tool_use",
        "part": {"tool": "scout", "state": {"status": "running", "input": {
            "command": "search", "experts": "video_hub", "query": "private question"}}},
    }
    completed = {
        "type": "tool_use",
        "part": {"tool": "scout", "state": {"status": "completed", "input": {
            "command": "search", "experts": "video_hub", "query": "private question"}}},
    }

    assert progress_module.progress(started) == "Ищу в ВидеоХабе…"
    assert progress_module.progress(completed) == "Просматриваю найденные материалы…"
    assert "private question" not in progress_module.progress(started)


def test_opencode_reports_real_stages_for_all_sources():
    def event(command, status="running", **arguments):
        return {"type": "tool_use", "part": {"tool": "scout", "state": {
            "status": status, "input": {"command": command, **arguments}}}}

    assert progress_module.progress(event("search", experts="video_hub")) == "Ищу в ВидеоХабе…"
    assert progress_module.progress(event("digest", group="visual")) == "Просматриваю материалы…"
    assert progress_module.progress(event("show", source_keys=["secret:1"])) == "Читаю первоисточники…"
    assert progress_module.progress(event("lesson_search", query="private")) == "Ищу в опубликованных уроках…"
    assert progress_module.progress(event("experts")) == "Определяю область поиска…"
    assert progress_module.progress(event("videos")) == "Сверяю каталог ВидеоХаба…"
    assert progress_module.progress(event("show", status="completed")) == "Сопоставляю источники…"


def test_codex_progress_and_private_reasoning_are_handled_safely():
    assert progress_module.progress({"type": "reasoning", "text": "do not show"}) is None
    assert progress_module.progress({"type": "step_start"}) == "Скаут разбирает вопрос…"
    assert progress_module.progress({"type": "item.started", "item": {
        "type": "mcp_tool_call", "arguments": {"command": "search", "experts": "video_hub"}}}) == "Ищу в ВидеоХабе…"
    assert progress_module.progress({"type": "item.completed", "item": {
        "type": "mcp_tool_call", "arguments": {"command": "show"}}}) == "Сопоставляю источники…"
    assert progress_module.progress({"type": "step_finish", "part": {"reason": "stop"}}) == "Проверяю ответ…"
    assert progress_module.progress({"type": "tool_use", "part": {
        "tool": "another-tool", "state": {"input": {"query": "secret"}}}}) is None
