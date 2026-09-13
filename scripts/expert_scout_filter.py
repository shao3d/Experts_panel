#!/usr/bin/env python3
"""Reduce `opencode run --format json` JSONL into the final agent answer.

Keeps only text parts emitted after the last tool call (falling back to all
text parts — explicitly marked with a # WARNING — when the run ended without
a post-tool answer), grouped by assistant message.
"""

from __future__ import annotations

import itertools
import json
import sys


def main() -> int:
    events = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    last_tool_index = -1
    for index, event in enumerate(events):
        if event.get("type") in {"tool", "tool_use"}:
            last_tool_index = index

    text_parts: list[tuple[str, str]] = []
    for index, event in enumerate(events):
        if event.get("type") != "text":
            continue
        if last_tool_index >= 0 and index <= last_tool_index:
            continue
        part = event.get("part") or {}
        text = part.get("text")
        message_id = part.get("messageID") or f"msg-{index}"
        if text:
            text_parts.append((message_id, text))

    used_fallback = False
    if not text_parts:
        used_fallback = True
        for index, event in enumerate(events):
            if event.get("type") != "text":
                continue
            part = event.get("part") or {}
            text = part.get("text")
            if text:
                text_parts.append((part.get("messageID") or f"msg-{index}", text))

    grouped: list[str] = []
    for _message_id, group in itertools.groupby(text_parts, key=lambda item: item[0]):
        grouped.append("".join(text for _, text in group))

    answer = "\n\n".join(grouped).strip()
    if answer and used_fallback and last_tool_index >= 0:
        answer = (
            "# WARNING: scout did not emit a final answer after the last tool call; "
            "the text below is intermediate narration and may be incomplete.\n\n"
            + answer
        )
    if answer:
        print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
