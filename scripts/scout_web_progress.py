#!/usr/bin/env python3
"""Relay Codex output unchanged and emit safe, human-readable progress."""
import json
import os
import subprocess
import sys


def progress(event):
    item = event.get("item", {})
    if item.get("type") == "agent_message":
        return "Собираю ответ…"
    if item.get("type") != "mcp_tool_call":
        return None
    args = item.get("arguments", {})
    command = args.get("command")
    if command == "search":
        if event.get("type") == "item.completed":
            return "Просматриваю найденные материалы…"
        return "Ищу в ВидеоХабе…" if args.get("experts") == "video_hub" else "Ищу в Telegram…"
    if command == "show" and event.get("type") == "item.completed":
        return "Сопоставляю источники…"
    return {"show": "Читаю источники…", "digest": "Просматриваю материалы…",
            "videos": "Проверяю каталог видео…", "experts": "Проверяю область поиска…"}.get(command)


def main():
    child = subprocess.Popen([os.environ["SCOUT_WEB_CODEX_BIN"], *sys.argv[1:]],
                             stdout=subprocess.PIPE, text=True)
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


if __name__ == "__main__":
    raise SystemExit(main())
