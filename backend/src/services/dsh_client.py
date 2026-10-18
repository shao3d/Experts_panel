"""DeepSeek Harness (dsh) headless client for the Reddit Search stages.

Why a subprocess: the Reddit roles (planner, answerability judge, reflection
replanner, synthesis) used to run on OpenRouter/Gemini and must now run on
DeepSeek V4.1 Flash through the local `dsh` CLI. This module is the single
adapter, mirroring `utils/reddit_codex_judge.py`: the prompt travels on stdin,
the answer is read from the `--json` NDJSON stream, and the process group is
killed on timeout.

Contract with the callers (`reddit_enhanced_service`, `reddit_synthesis_service`)
is the OpenRouter response surface: `response.choices[0].message.content`,
`response.choices[0].finish_reason`, `response.model`, `response.usage`.

Model routing: the callers already pick a model per role
(`MODEL_SCOUT`/`MODEL_ANALYSIS` for planner + judge, `MODEL_SYNTHESIS` for
comparison rerank and synthesis). All of them are the same underlying dsh
model, so the requested name is used only to choose the reasoning effort:
synthesis-tier work gets `high`, everything else `low`.

No tools: the profile overlay passed via `DSH_PATCH_PATH` disables the agent
tools, so the model answers instead of browsing. See `backend/deploy/dsh/`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DSH_BIN = os.getenv("REDDIT_DSH_BIN", "dsh")
DSH_PROFILE = os.getenv("REDDIT_DSH_PROFILE", "headless")
# Tool-free overlay applied after the profile layer (see backend/deploy/dsh/).
DSH_PATCH_PATH = os.getenv("DSH_PATCH_PATH", "")
DSH_TIMEOUT_S = float(os.getenv("REDDIT_DSH_TIMEOUT_S", "90"))
DSH_MAX_CONCURRENCY = int(os.getenv("REDDIT_DSH_CONCURRENCY", "2"))
# Neutral working directory: the profile otherwise inherits the caller's cwd
# and could pull project context into a judge prompt.
DSH_CWD = os.getenv("REDDIT_DSH_CWD", "")

# `DSH_PROFILE`, `DSH_SESSION_ID` and friends are set by the harness in the
# environment of every process it starts. Inheriting them made the adapter
# boot the *interactive* `dsh-tui` profile instead of `headless`, which then
# waited for a terminal and hung until the timeout. Ambient DSH_* state is
# therefore stripped; only DSH_HOME (which holds .credentials.yaml) survives.
_AMBIENT_DSH_PREFIX = "DSH_"
_DSH_ENV_KEEP = {"DSH_HOME"}

# A dsh call boots the whole plugin stack, so calls are serialized through a
# small semaphore instead of spawning one process per candidate.
_semaphore: Optional[asyncio.Semaphore] = None

_LENGTH_REASONS = {"length", "max_tokens", "token_limit", "output_limit"}


class DshLLMError(RuntimeError):
    """Raised when a dsh call fails; callers decide on degraded fallbacks."""


def set_reasoning_effort_for_model(model: str) -> str:
    """Map a role's requested model to a dsh reasoning effort.

    `REDDIT_DSH_EFFORT_OVERRIDE` pins the effort for every role, which is how
    the A/B harness measures whether a cheaper effort keeps the same decisions.
    """
    from .. import config

    override = os.getenv("REDDIT_DSH_EFFORT_OVERRIDE", "").strip().lower()
    if override in {"off", "low", "high", "max"}:
        return override
    return "high" if model == config.MODEL_SYNTHESIS else "low"


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, DSH_MAX_CONCURRENCY))
    return _semaphore


def _working_directory() -> str:
    if DSH_CWD:
        return DSH_CWD
    # /tmp keeps the profile away from any repository AGENTS.md.
    return "/tmp"


def dsh_command(*, reasoning_effort: Optional[str] = None) -> List[str]:
    command = [DSH_BIN, "--profile", DSH_PROFILE]
    # `--patch` is repeatable and applied in order: the tool-free overlay
    # first, then the per-call reasoning-effort overlay.
    patches = [p for p in (DSH_PATCH_PATH, _effort_overlay(reasoning_effort)) if p]
    for patch in patches:
        command.extend(["--patch", patch])
    command.extend(["--json", "-"])
    return command


_OVERLAY_DIR = Path(os.getenv("REDDIT_DSH_OVERLAY_DIR", "/tmp/dsh-reddit-overlays"))


def _effort_overlay(reasoning_effort: Optional[str]) -> str:
    """Path to a generated overlay pinning the reasoning effort for this call.

    Effort is a profile-layer value, and the CLI exposes no flag for it, so it
    is applied as an extra patch layer per call.
    """
    if not reasoning_effort:
        return ""
    _OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    overlay = _OVERLAY_DIR / f"effort-{reasoning_effort}.yml"
    if not overlay.exists():
        overlay.write_text(
            "- id: agent-default-model\n"
            "  config:\n"
            "    provider: commandcode\n"
            "    model: deepseek/deepseek-v4.1-flash\n"
            f"    reasoningEffort: {reasoning_effort}\n",
            encoding="utf-8",
        )
    return str(overlay)


def _subscription_environment() -> Dict[str, str]:
    """Pass the environment through, minus provider keys and harness state.

    Credentials live in `$DSH_HOME/.credentials.yaml`; dropping the provider
    API keys keeps a judge call from ever being billed elsewhere, and dropping
    ambient `DSH_*` state keeps a nested call from adopting the caller's
    interactive profile or session.
    """
    excluded = {
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "OPENROUTER_API_KEY",
        "CODEX_ACCESS_TOKEN",
        "AGENT_CONTEXT_API_TOKEN",
        "REDDIT_SEARCH_API_TOKEN",
    }
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in excluded
        and not (k.startswith(_AMBIENT_DSH_PREFIX) and k not in _DSH_ENV_KEEP)
    }
    env["DSH_PROFILE"] = DSH_PROFILE
    return env


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str, finish_reason: Optional[str] = None):
        self.message = _Message(content)
        self.finish_reason = finish_reason


class _Usage:
    def __init__(self, payload: Dict[str, Any]):
        self.prompt_tokens = int(payload.get("inputTokens", 0) or 0)
        self.completion_tokens = int(payload.get("outputTokens", 0) or 0)
        self.total_tokens = int(payload.get("totalTokens", 0) or 0)
        self.cached_tokens = int(payload.get("cacheReadTokens", 0) or 0)


class DshResponse:
    """OpenRouter-shaped response so callers need no changes."""

    def __init__(
        self, text: str, model: str, finish_reason: str, usage: Dict[str, Any]
    ):
        self.model = model
        self.choices = [_Choice(text, finish_reason)]
        self.usage = _Usage(usage)


def parse_events(stdout: bytes, model: str) -> DshResponse:
    """Read the NDJSON run stream and return the final assistant message."""
    text: Optional[str] = None
    reason_kind = ""
    usage: Dict[str, Any] = {}
    for line in stdout.decode(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "final":
            text = event.get("text") or ""
        elif kind == "status" and event.get("phase") == "step_end":
            usage = event.get("usage") or usage
        elif kind == "status" and event.get("phase") == "turn_end":
            reason = event.get("reason") or {}
            reason_kind = str(reason.get("kind") or "")
        elif kind in {"error", "turn.failed"}:
            raise DshLLMError(f"dsh reported a failed turn: {str(event)[:200]}")
    if text is None:
        raise DshLLMError("dsh returned no final message")
    finish_reason = "length" if reason_kind in _LENGTH_REASONS else "stop"
    return DshResponse(text, model, finish_reason, usage)


class DshHeadlessLLMClient:
    """One-call-per-process LLM client backed by `dsh --profile headless`."""

    def __init__(self, timeout_s: float = DSH_TIMEOUT_S):
        self.timeout_s = timeout_s
        self.calls = 0

    async def chat_completions_create(
        self,
        *,
        model: str = "",
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,  # accepted and ignored: CLI has none
        max_tokens: Optional[int] = None,      # accepted and ignored
        reasoning_effort: Optional[str] = None,
        **_: Any,
    ) -> DshResponse:
        prompt = "\n\n".join(m.get("content", "") for m in messages)
        if not prompt.strip():
            raise DshLLMError("empty prompt")
        effort = reasoning_effort or set_reasoning_effort_for_model(model)
        command = dsh_command(reasoning_effort=effort)

        async with _get_semaphore():
            self.calls += 1
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=_working_directory(),
                env=_subscription_environment(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(
                    proc.communicate(prompt.encode()), timeout=self.timeout_s
                )
            except BaseException:
                await _kill(proc)
                raise DshLLMError(f"dsh call timed out after {self.timeout_s}s")
            if proc.returncode:
                # Never forward raw diagnostics: they can carry credentials.
                raise DshLLMError(f"dsh exited with code {proc.returncode}")
        return parse_events(stdout, model or "dsh")


async def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        await proc.wait()
    except Exception:  # pragma: no cover - best effort cleanup
        pass


async def check_dsh_health(timeout_s: float = 30.0) -> bool:
    """True when a trivial prompt round-trips through the profile."""
    client = DshHeadlessLLMClient(timeout_s=timeout_s)
    try:
        response = await client.chat_completions_create(
            model="health", messages=[{"role": "user", "content": "Reply with: OK"}]
        )
        return bool((response.choices[0].message.content or "").strip())
    except Exception as exc:
        logger.warning("dsh health check failed: %s", exc)
        return False


def get_reddit_llm_client():
    """The single engine switch for every Reddit role.

    Both `reddit_enhanced_service` (planner, answerability judge, reflection
    replanner) and `reddit_synthesis_service` obtain their client here, so the
    engine is configured in exactly one place.
    """
    from .. import config

    if getattr(config, "REDDIT_LLM_BACKEND", "dsh") == "dsh":
        return DshHeadlessLLMClient(timeout_s=getattr(
            config, "REDDIT_DSH_TIMEOUT_S", DSH_TIMEOUT_S
        ))
    from .vertex_llm_client import get_vertex_llm_client

    return get_vertex_llm_client()
