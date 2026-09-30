"""Parse live Scout events and source reads for verification and evaluation.

This module has no corpus access. A requested key is not evidence until the
tool succeeds and returns its text. Digests and neighbor previews do not count.
"""
from __future__ import annotations

import json
import re


def sources_from_output(output: object) -> list[dict]:
    if isinstance(output, dict):
        if output.get("isError") or output.get("status") == "error":
            return []
        return [row for block in output.get("content", []) if block.get("type") == "text"
                for row in sources_from_output(block.get("text", ""))]
    if not isinstance(output, str):
        return []
    try:
        parsed = json.loads(output)
    except (ValueError, TypeError):
        matches = list(re.finditer(r"^=== ([a-z][a-z_]*:\d+) \[([^\]]+)\] @[^\n]* ===\n", output, re.M))
        rows = []
        for index, match in enumerate(matches):
            end = matches[index+1].start() if index+1 < len(matches) else len(output)
            body = re.split(r"^--- (?:neighbors|author comments|community comments|linked context)",
                            output[match.end():end], maxsplit=1, flags=re.M)[0]
            source = {"source_key": match[1], "created_at": match[2]}
            while body.startswith(("video: ", "AUTHOR: ", "VIDEO_METADATA: ", "READ_STATE: ")):
                header, _, body = body.partition("\n")
                name, _, value = header.partition(": ")
                if name in ("READ_STATE", "VIDEO_METADATA"):
                    try:
                        source.update(json.loads(value))
                    except ValueError:
                        return []
                else:
                    source["video_link" if name == "video" else "author_name"] = value
            source["content"] = body.rstrip("\n")
            rows.append(source)
        return rows
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict) and row.get("source_key") and "error" not in row]
    return sources_from_output(parsed) if isinstance(parsed, dict) else []


def tool_calls(events: list[dict]) -> list[dict]:
    calls = []
    for event in events:
        if event.get("type") == "tool_use":
            part = event.get("part") or {}
            state = part.get("state") or {}
            name, args, status, output = part.get("tool"), state.get("input") or {}, state.get("status"), state.get("output", "")
        elif event.get("type") == "item.completed" and event.get("item", {}).get("type") == "mcp_tool_call":
            item = event["item"]
            name, args, status, output = item.get("tool"), item.get("arguments") or {}, item.get("status"), item.get("result") or {}
        else:
            continue
        successful = status == "completed"
        if isinstance(output, dict) and output.get("isError"):
            successful = False
        texts = [output] if isinstance(output, str) else [b.get("text", "") for b in output.get("content", [])] if isinstance(output, dict) else []
        for text in texts:
            try:
                if json.loads(text).get("status") in {"error", "partial"}:
                    successful = False
            except (ValueError, AttributeError):
                pass
            if text.startswith("scout failed:"):
                successful = False
        calls.append({"tool": name, "args": args, "status": status, "successful": successful, "output": output})
    return calls


def read_evidence(events: list[dict]) -> dict[str, dict]:
    reads: dict[str, dict] = {}
    for call in tool_calls(events):
        if not call["successful"] or call["args"].get("command") != "show":
            continue
        for source in sources_from_output(call["output"]):
            key = source["source_key"]
            content = source.get("content") or ""
            offset = source.get("content_offset", 0)
            total = source.get("content_chars", len(content))
            record = reads.setdefault(key, {**source, "parts": {}, "conflict": False})
            if offset in record["parts"] and record["parts"][offset] != content:
                record["conflict"] = True
            record["parts"][offset] = content
            record["content_chars"] = total
    for record in reads.values():
        text = ""
        for offset, part in sorted(record["parts"].items()):
            if offset > len(text):
                break
            overlap = min(len(part), len(text)-offset)
            if overlap and text[offset:offset+overlap] != part[:overlap]:
                record["conflict"] = True
            text += part[overlap:]
        record["content"] = text
        record["fully_read"] = not record["conflict"] and len(text) >= record["content_chars"]
    return reads


def finished(events: list[dict]) -> bool:
    return any(e.get("type") == "turn.completed" or
               (e.get("type") == "step_finish" and e.get("part", {}).get("reason") == "stop")
               for e in events) and not any(e.get("type") in {"error", "turn.failed"} for e in events)
