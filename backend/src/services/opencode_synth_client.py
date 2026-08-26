"""Headless opencode synthesis client for Reddit community insights.

Pure-HTTP alternative to the subprocess-based opencode_drift_client: it talks
straight to the `opencode serve` HTTP API, so it works from inside the panel
container and from any host with network access to the VM:

    POST /session                     -> create a titled session
    POST /session/{id}/message        -> synchronous prompt, returns the reply
    POST /session/{id}/abort          -> best-effort cancel on timeout
    DELETE /session/{id}              -> cleanup after completion

Contract matches RedditSynthesisService.synthesize(): returns markdown text.
No agent is used and no project context is inherited (the serve host has no
AGENTS.md); the synthesis system prompt travels in the message payload.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

OPENCODE_URL = os.getenv("OPENCODE_URL", "http://127.0.0.1:4096")
OPENCODE_SYNTH_MODEL = os.getenv("OPENCODE_SYNTH_MODEL", "opencode/x-preview-f-free")
DEFAULT_TIMEOUT_S = float(os.getenv("OPENCODE_SYNTH_TIMEOUT_S", "60"))
MAX_CONCURRENT_SESSIONS = int(os.getenv("OPENCODE_SYNTH_CONCURRENCY", "2"))

_SESSION_TITLE_PREFIX = "reddit_synth_"

_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_SESSIONS))
    return _semaphore


class OpenCodeSynthesisError(RuntimeError):
    """Raised when the headless opencode synthesis attempt fails."""


def _split_model(model_ref: str) -> Tuple[str, str]:
    provider, _, model_id = model_ref.partition("/")
    if not provider or not model_id:
        raise OpenCodeSynthesisError(
            f"OPENCODE_SYNTH_MODEL must be 'provider/model', got '{model_ref}'"
        )
    return provider, model_id


def _assistant_text_from_message(message: Dict[str, Any]) -> str:
    for part in reversed(message.get("parts") or []):
        if part.get("type") == "text" and (part.get("text") or "").strip():
            return part["text"].strip()
    return ""


def _message_error(message: Dict[str, Any]) -> Optional[str]:
    err = (message.get("info") or {}).get("error")
    if not err:
        return None
    detail = err.get("data", {}).get("message", "") if isinstance(err.get("data"), dict) else ""
    return detail or str(err)


def _text_from_messages_payload(payload: Any) -> str:
    """Extract the last assistant text from any messages-shaped response."""
    items: List[Dict[str, Any]]
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = [m for m in payload if isinstance(m, dict)]
    else:
        return ""

    texts: List[str] = []
    for m in reversed(items):
        info = m.get("info") or {}
        role = info.get("role") or ("assistant" if "parts" in m else None)
        if role != "assistant":
            continue
        text = _assistant_text_from_message(m)
        if text:
            texts.append(text)
    # Items came back newest-last in practice; last appended wins.
    return texts[0] if texts else ""


async def check_serve_health(timeout_s: float = 5.0) -> bool:
    """True when the opencode serve answers on OPENCODE_URL."""
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(f"{OPENCODE_URL}/session")
            return resp.status_code == 200 and resp.text.strip().startswith("[")
    except Exception:
        return False


async def synthesize_markdown(
    system_prompt: str,
    user_prompt: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> str:
    """Run one synthesis prompt through headless opencode. Returns markdown.

    Raises OpenCodeSynthesisError on any failure; callers decide on fallback.
    """
    provider, model_id = _split_model(OPENCODE_SYNTH_MODEL)
    title = f"{_SESSION_TITLE_PREFIX}{uuid.uuid4().hex[:12]}"
    session_id: Optional[str] = None

    async with _get_semaphore():
        try:
            async with httpx.AsyncClient(timeout=max(timeout_s + 15.0, 30.0)) as client:
                create = await client.post(
                    f"{OPENCODE_URL}/session",
                    json={
                        "title": title,
                        "model": {"providerID": provider, "id": model_id},
                    },
                )
                create.raise_for_status()
                session_id = create.json().get("id")
                if not session_id:
                    raise OpenCodeSynthesisError(
                        f"session create returned no id: {str(create.text)[:150]}"
                    )

                reply = await client.post(
                    f"{OPENCODE_URL}/session/{session_id}/message",
                    json={
                        "model": {"providerID": provider, "modelID": model_id},
                        "system": system_prompt,
                        "parts": [{"type": "text", "text": user_prompt}],
                    },
                    timeout=timeout_s,
                )
                reply.raise_for_status()

                text = _text_from_messages_payload(reply.json())
                if not text:
                    # Sync endpoint shape may vary between versions: fall back
                    # to reading the session transcript once.
                    msgs = await client.get(f"{OPENCODE_URL}/session/{session_id}/message")
                    if msgs.status_code == 200:
                        text = _text_from_messages_payload(msgs.json())
                if not text:
                    raise OpenCodeSynthesisError("empty assistant response")

                return text
        except httpx.TimeoutException:
            raise OpenCodeSynthesisError(
                f"opencode synthesis timed out after {timeout_s}s"
            )
        except httpx.HTTPStatusError as e:
            raise OpenCodeSynthesisError(
                f"opencode HTTP {e.response.status_code}: {str(e.response.text)[:150]}"
            )
        except OpenCodeSynthesisError:
            raise
        except Exception as e:
            raise OpenCodeSynthesisError(f"opencode synthesis failed: {e}")
        finally:
            await _cleanup_session(session_id)


async def _cleanup_session(session_id: Optional[str]) -> None:
    """Best-effort abort + delete so failed runs don't leak busy sessions."""
    if not session_id:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{OPENCODE_URL}/session/{session_id}/abort")
            await client.delete(f"{OPENCODE_URL}/session/{session_id}")
    except Exception:
        pass
