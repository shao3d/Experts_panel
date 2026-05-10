#!/usr/bin/env python3
"""Hermes pre_tool_call guard for Harvester research jobs.

The goal is not general shell sandboxing. Hermes already has its normal
security scanner. This guard handles a narrower research-contract problem:
delegated Harvester agents sometimes invent tools or probe internal services
instead of using the mounted Searcharvester scripts.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Any


FORBIDDEN_TOOL_NAMES = {
    "google_search": "Use the terminal command `searcharvester-search --query ...` instead.",
    "read_file": "Use `grep`, `head`, `sed`, or `cat` on saved `./extracts/<id>.md` files instead.",
}

FORBIDDEN_COMMAND_NAMES = {
    "curl",
    "wget",
    "netstat",
    "ss",
    "google_search",
    "read_file",
    "skill_view",
    "rm",
    "sudo",
    "apt",
    "apt-get",
    "pip",
    "pip3",
    "chmod",
    "chown",
}

INTERNAL_SERVICE_RE = re.compile(
    r"https?://(?:searxng|localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?",
    re.IGNORECASE,
)

ALLOWED_RESEARCH_PREFIXES = (
    "searcharvester search ",
    "searcharvester extract ",
    "/usr/local/bin/searcharvester search ",
    "/usr/local/bin/searcharvester extract ",
    "searcharvester-search ",
    "searcharvester-extract ",
    "/usr/local/bin/searcharvester-search ",
    "/usr/local/bin/searcharvester-extract ",
    "search.py ",
    "extract.py ",
    "/usr/local/bin/search.py ",
    "/usr/local/bin/extract.py ",
    "python3 /opt/data/skills/searcharvester-search/scripts/search.py",
    "python3 /opt/data/skills/searcharvester-extract/scripts/extract.py",
    "python3 /usr/local/bin/search.py ",
    "python3 /usr/local/bin/extract.py ",
)

ALLOWED_HEREDOC_TARGETS = (
    "cat > ./plan.md",
    "cat > ./report.md",
)

SAFE_READER_COMMANDS = {"grep", "head", "sed", "cat", "ls", "wc"}
SAFE_READER_PATH_PREFIXES = ("./extracts", "extracts/")
SAFE_READER_EXACT_PATHS = {"./report.md", "./plan.md", "report.md", "plan.md"}
SHELL_CHAIN_TOKENS = {"&&", "||", ";"}
SEARCH_FLAGS_WITH_VALUES = {
    "--query",
    "--max-results",
    "--engines",
    "--categories",
    "--base-url",
}
EXTRACT_FLAGS_WITH_VALUES = {"--url", "--size", "--base-url"}


def main() -> int:
    try:
        payload: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    block_message = _block_message(tool_name, tool_input)
    if block_message:
        print(json.dumps({"action": "block", "message": block_message}))
    return 0


def _block_message(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    if tool_name in FORBIDDEN_TOOL_NAMES:
        return _message(FORBIDDEN_TOOL_NAMES[tool_name])

    if tool_name != "terminal":
        return None

    command = str(
        tool_input.get("command")
        or tool_input.get("cmd")
        or tool_input.get("input")
        or ""
    ).strip()
    if not command:
        return None

    if INTERNAL_SERVICE_RE.search(command):
        return _message("Do not probe internal services directly. Use `searcharvester-search`.")

    first = _first_command_name(command)
    if first in FORBIDDEN_COMMAND_NAMES:
        return _message(f"`{first}` is outside the Harvester research command contract.")

    if re.search(r"\bpython3?\s+-c\b", command):
        return _message("Do not introspect the container from delegated research tasks.")

    research_error = _research_command_error(command)
    if research_error is None:
        return None
    if research_error:
        return _message(research_error)

    if _is_allowed_research_command(command):
        return None

    if _looks_like_shell_introspection(command):
        return _message("Use the Harvester search/extract commands instead of shell introspection.")

    return _message(
        f"`{first or command.split()[0]}` is not in the Harvester research command contract."
    )


def _first_command_name(command: str) -> str:
    try:
        parts = shlex.split(command, comments=False, posix=True)
    except ValueError:
        parts = command.split()
    if not parts:
        return ""
    return parts[0].split("/")[-1]


def _research_command_error(command: str) -> str | None:
    parts = _shlex_parts(command)
    if not parts:
        return "Empty terminal command is outside the Harvester research command contract."
    if not _has_allowed_research_prefix(command):
        return ""
    if any(part in SHELL_CHAIN_TOKENS for part in parts) or "\n" in command:
        return "Run exactly one Harvester search/extract command per terminal call."

    kind, args = _research_kind_and_args(parts)
    if kind == "search":
        return _validate_search_args(args)
    if kind == "extract":
        return _validate_extract_args(args)
    return "Use one of the explicit Harvester search/extract wrapper commands."


def _has_allowed_research_prefix(command: str) -> bool:
    normalized = " ".join(command.split())
    return any(normalized.startswith(prefix) for prefix in ALLOWED_RESEARCH_PREFIXES)


def _is_allowed_research_command(command: str) -> bool:
    normalized = " ".join(command.split())
    if any(normalized.startswith(prefix) for prefix in ALLOWED_HEREDOC_TARGETS):
        return True
    if _is_allowed_reader_command(command):
        return True
    return False


def _research_kind_and_args(parts: list[str]) -> tuple[str, list[str]]:
    first = parts[0].split("/")[-1]
    if first == "python3" and len(parts) >= 2:
        script = parts[1].split("/")[-1]
        if script == "search.py":
            return "search", parts[2:]
        if script == "extract.py":
            return "extract", parts[2:]
    if first == "searcharvester" and len(parts) >= 2:
        if parts[1] in {"search", "extract"}:
            return parts[1], parts[2:]
    if first in {"searcharvester-search", "search.py"}:
        return "search", parts[1:]
    if first in {"searcharvester-extract", "extract.py"}:
        return "extract", parts[1:]
    return "", parts[1:]


def _validate_search_args(args: list[str]) -> str | None:
    if "--query" not in args:
        return "Search commands must use `--query \"...\"`."
    return _validate_flag_args(args, SEARCH_FLAGS_WITH_VALUES, required="--query")


def _validate_extract_args(args: list[str]) -> str | None:
    if "--url" not in args:
        return "Extract commands must use `--url \"https://...\"`."
    error = _validate_flag_args(args, EXTRACT_FLAGS_WITH_VALUES, required="--url")
    if error:
        return error
    if _flag_value_count(args, "--url") != 1:
        return "Extract commands must pass exactly one URL after `--url`."
    return None


def _validate_flag_args(
    args: list[str],
    flags_with_values: set[str],
    *,
    required: str,
) -> str | None:
    i = 0
    while i < len(args):
        part = args[i]
        if part in flags_with_values:
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                return f"`{part}` must have a value."
            i += 2
            continue
        if part.startswith("--"):
            return f"`{part}` is not an allowed Harvester flag."
        return (
            f"Unexpected positional argument `{part}`. "
            f"Use `{required}` and pass one value per flag."
        )
    return None


def _flag_value_count(args: list[str], flag: str) -> int:
    return sum(1 for idx, part in enumerate(args[:-1]) if part == flag and not args[idx + 1].startswith("--"))


def _shlex_parts(command: str) -> list[str]:
    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return command.split()


def _is_allowed_reader_command(command: str) -> bool:
    try:
        parts = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return False
    if not parts:
        return False

    first = parts[0].split("/")[-1]
    if first not in SAFE_READER_COMMANDS:
        return False

    return any(_is_safe_reader_path(part) for part in parts[1:])


def _is_safe_reader_path(value: str) -> bool:
    cleaned = value.rstrip(",;")
    return cleaned in SAFE_READER_EXACT_PATHS or any(
        cleaned.startswith(prefix) for prefix in SAFE_READER_PATH_PREFIXES
    )


def _looks_like_shell_introspection(command: str) -> bool:
    normalized = " ".join(command.split()).lower()
    needles = (
        "which search",
        "command -v",
        "type -a",
        "find /",
        "ls /usr",
        "ls -r /",
        "os.listdir",
        "grep search",
    )
    return any(needle in normalized for needle in needles)


def _message(reason: str) -> str:
    return (
        f"{reason} Allowed research commands are: "
        "`searcharvester search --query ...`, "
        "`searcharvester-search --query ...`, "
        "`searcharvester extract --url ...`, "
        "`searcharvester-extract --url ...`, and file readers "
        "`grep`, `head`, `sed`, `cat ./extracts/<id>.md`, `ls ./extracts`."
    )


if __name__ == "__main__":
    raise SystemExit(main())
