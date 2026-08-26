#!/usr/bin/env python3
"""Manual A/B verification for REDDIT_SYNTH_BACKEND=opencode (Reddit synthesis).

Runs three cases against the live headless opencode serve (:4096):
  A. backend=opencode  - real free-model synthesis of a tiny fake result;
                         falls back to Gemini if the model exceeds the budget
  B. backend=auto      - dead OPENCODE_URL -> deterministic Gemini fallback
  C. backend=shadow    - gemini answer returns immediately, opencode logged

Usage (auto-loads backend/.env):
  app/backend/.venv/bin/python app/backend/manual/manual_reddit_opencode_ab.py
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

for line in (BACKEND_DIR / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(name)s: %(message)s")

from src import config                                    # noqa: E402
from src.services.reddit_synthesis_service import RedditSynthesisService  # noqa: E402
import src.services.opencode_synth_client as oc           # noqa: E402


def make_result():
    posts = [
        NS(title="uv vs pip benchmarks", subreddit="Python", score=42,
           num_comments=8, url="https://reddit.com/r/Python/x1",
           created_utc=time.time(), strategy_hits=["literal_global_relevance"],
           heuristic_score=0.9,
           selftext="uv ставит пакеты в 10 раз быстрее pip за счёт Rust и "
                    "глобального кэша. На CI win 40-60% времени.",
           top_comments=[]),
        NS(title="pip 24.x improvements", subreddit="Python", score=15,
           num_comments=3, url="https://reddit.com/r/Python/x2",
           created_utc=time.time(),
           strategy_hits=["expanded_global_relevance"], heuristic_score=0.6,
           selftext="pip всё ещё стандарт, но параллельная установка так и "
                    "не пришла.",
           top_comments=[]),
    ]
    return NS(posts=posts, total_found=86)


async def case_a_opencode():
    config.REDDIT_SYNTH_BACKEND = "opencode"
    svc = RedditSynthesisService()

    async def fake_completion(messages, max_tokens):
        return "GEMINI_FALLBACK_TEXT", "stop"

    svc._generate_completion = fake_completion
    res = await svc.synthesize("uv или pip в 2026: что быстрее?", make_result())
    if res == "GEMINI_FALLBACK_TEXT":
        print("\n=== CASE A (soft): free model exceeded budget, fallback OK ===")
        return
    assert "КУДА ИДИ" in res or "не найдено" in res.lower(), res[:300]
    print(f"\n=== CASE A OK: opencode synthesis {len(res)} chars ===")
    print(res[:400].replace("\n", " | "))


async def case_b_fallback():
    config.REDDIT_SYNTH_BACKEND = "auto"
    oc.OPENCODE_URL = "http://127.0.0.1:59999"  # dead port
    svc = RedditSynthesisService()

    async def fake_completion(messages, max_tokens):
        return "GEMINI_FALLBACK_TEXT", "stop"

    svc._generate_completion = fake_completion
    res = await svc.synthesize("uv или pip?", make_result())
    assert res == "GEMINI_FALLBACK_TEXT", res[:200]
    print("\n=== CASE B OK: fallback reached Gemini once ===")
    oc.OPENCODE_URL = "http://127.0.0.1:4096"


async def case_c_shadow():
    config.REDDIT_SYNTH_BACKEND = "shadow"
    svc = RedditSynthesisService()

    async def fake_completion(messages, max_tokens):
        return "SHADOW_GEMINI_ANSWER", "stop"

    svc._generate_completion = fake_completion
    t0 = time.time()
    res = await svc.synthesize("Claude Code tips?", make_result())
    assert res == "SHADOW_GEMINI_ANSWER", res[:200]
    print(f"\n=== CASE C OK: shadow returned gemini answer "
          f"(wall {time.time() - t0:.1f}s) ===")


async def main():
    await case_a_opencode()
    await case_b_fallback()
    await case_c_shadow()
    print("\nALL CASES PASSED")


if __name__ == "__main__":
    asyncio.run(main())
