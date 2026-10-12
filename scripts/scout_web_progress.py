#!/usr/bin/env python3
"""Relay Scout engine JSONL unchanged and emit safe, human-readable progress."""
import json
import os
import signal
import subprocess
import sys


def _tool_progress(args, completed=False):
    command = args.get("command")
    if completed:
        return {
            "search": "Looking through found materials…",
            "show": "Matching sources…",
            "digest": "Selecting relevant fragments…",
            "videos": "Checking the video catalog…",
            "lesson_search": "Looking through found lessons…",
            "experts": "Choosing the search scope…",
        }.get(command)
    if command == "search":
        return "Searching VideoHub…" if args.get("experts") == "video_hub" else "Searching Telegram…"
    return {
        "show": "Reading primary sources…",
        "digest": "Looking through materials…",
        "videos": "Checking the VideoHub catalog…",
        "lesson_search": "Searching published lessons…",
        "experts": "Determining the search scope…",
    }.get(command)


def progress(event):
    if not isinstance(event, dict):
        return None
    event_type = event.get("type")
    if event_type in {"step_start", "step.started"}:
        return "Scout is parsing the question…"

    # OpenCode (the web Scout's GLM engine) reports MCP calls as tool_use.
    if event_type == "tool_use":
        part = event.get("part", {})
        if part.get("tool") != "scout":
            return None
        state = part.get("state", {})
        args = state.get("input") or {}
        if state.get("status") in {"running", "pending"}:
            return _tool_progress(args)
        if state.get("status") == "completed":
            return _tool_progress(args, completed=True)
        return None
    if event_type in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item", {})
        if item.get("type") != "mcp_tool_call":
            return "Assembling the answer…" if item.get("type") == "agent_message" and event_type == "item.completed" else None
        if event_type == "item.started":
            return _tool_progress(item.get("arguments") or {})
        if event_type == "item.completed":
            return _tool_progress(item.get("arguments") or {}, completed=True)
        return None
    if event_type == "step_finish" and event.get("part", {}).get("reason") == "stop":
        return "Checking the answer…"
    if event_type == "error":
        return "Scout is finishing with an error…"

    # Keep compatibility with Codex JSON events used by the optional Sol engine.
    item = event.get("item", {})
    if item.get("type") == "agent_message":
        return "Assembling the answer…"
    if item.get("type") != "mcp_tool_call":
        return None
    return _tool_progress(
        item.get("arguments", {}),
        event_type == "item.completed" or item.get("status") == "completed",
    )


def main():
    arguments = sys.argv[1:]
    try:
        separator = arguments.index("--")
    except ValueError:
        print("usage: scout_web_progress.py <engine> [args...] -- <question>", file=sys.stderr)
        return 2
    command, question = arguments[:separator], arguments[separator + 1:]
    if not command or not question:
        print("usage: scout_web_progress.py <engine> [args...] -- <question>", file=sys.stderr)
        return 2

    print("SCOUT_PROGRESS " + json.dumps("Scout connected. Parsing the question…", ensure_ascii=False),
          file=sys.stderr, flush=True)
    child = subprocess.Popen([*command, *question], stdout=subprocess.PIPE, text=True, bufsize=1)

    def forward_signal(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)
    try:
        for line in child.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                message = progress(json.loads(line))
            except (ValueError, TypeError):
                message = None
            if message:
                print("SCOUT_PROGRESS " + json.dumps(message, ensure_ascii=False), file=sys.stderr, flush=True)
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
