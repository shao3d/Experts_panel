#!/usr/bin/env python3
"""Launch the default Scout model; only its read-only MCP tool is enabled."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from src.utils.scout_codex import codex_command

if len(sys.argv) < 2:
    raise SystemExit("usage: expert_scout_codex.py <question>")
command = codex_command("sol", fast=True) + [" ".join(sys.argv[1:])]
os.execvpe(command[0], command, os.environ)
