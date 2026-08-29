#!/usr/bin/env python3
"""Contract test for scripts/install_reddit_search_skill.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
INSTALLER = ROOT / "scripts" / "install_reddit_search_skill.sh"


def test_installer_creates_skill_and_wrapper_without_secrets(tmp_path):
    codex_home = tmp_path / "codex"
    bin_dir = tmp_path / "bin"
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    env["REDDIT_SEARCH_BIN_DIR"] = str(bin_dir)
    env.pop("AGENT_CONTEXT_API_TOKEN", None)

    result = subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    skill_dir = codex_home / "skills" / "reddit-search"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "agents" / "openai.yaml").is_file()
    assert (skill_dir / "reddit_search_runner.py").is_file()
    assert (bin_dir / "reddit-search").is_file()
    assert "secret" not in result.stdout.lower()
    assert "token was created" in result.stdout.lower()
