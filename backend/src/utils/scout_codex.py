"""One no-shell Codex configuration for runtime Scout and paired evaluations."""
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]


def resolve_bun() -> str:
    """SSH non-login sessions may omit Bun's standard install directory."""
    candidate = shutil.which("bun") or str(Path.home() / ".bun/bin/bun")
    if not Path(candidate).is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError("Scout requires Bun: install it in ~/.bun/bin or add it to PATH")
    return candidate


def codex_command(engine: str = "luna", *, fast: bool = False) -> list[str]:
    model, effort = {"luna": ("gpt-6-luna", "max"), "sol": ("gpt-6.1-sol", "low")}[engine]
    prompt = (ROOT / ".opencode/agents/expert-scout.md").read_text().split("---", 2)[2].strip()
    command = [
        os.environ.get("CODEX_BIN", "codex"), "exec", "--strict-config", "--ignore-user-config", "--ephemeral", "--json",
        "--model", model, "--sandbox", "read-only",
    ]
    for feature in (
        "shell_tool", "unified_exec", "apps", "plugins", "multi_agent",
        "browser_use", "computer_use", "image_generation", "view_image", "hooks",
    ):
        command.extend(["--disable", feature])
    settings = {
        "model_reasoning_effort": effort,
        "web_search": "disabled",
        "project_doc_max_bytes": 0,
        "developer_instructions": prompt + "\nUse only the scout MCP tool for corpus access. Do not use any other tool. Answer in Russian.",
        "mcp_servers.expert_scout.command": resolve_bun(),
        "mcp_servers.expert_scout.args": ["run", str(ROOT / "scripts/expert_scout_mcp.ts")],
        "mcp_servers.expert_scout.cwd": str(ROOT),
        "mcp_servers.expert_scout.enabled_tools": ["scout"],
        "mcp_servers.expert_scout.required": True,
        "mcp_servers.expert_scout.tool_timeout_sec": 150,
    }
    if fast:
        settings.update(service_tier="fast", **{"features.fast_mode": True})
    for key, value in settings.items():
        command.extend(["-c", f"{key}={json.dumps(value, ensure_ascii=False)}"])
    return command
