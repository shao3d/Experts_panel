#!/usr/bin/env python3
"""Live probe of the Reddit Search stages on the DeepSeek Harness engine.

Runs the *answerability judge* (and optionally the synthesis contract) through
`services/dsh_client.py` on in-memory posts, so a dsh regression is visible
without touching the Reddit proxy, the database or the production pipeline.

Usage:
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/dsh_reddit_probe.py

The posts below are synthetic: the probe measures JSON discipline, span
verification and latency of the engine, not Reddit retrieval quality.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config  # noqa: E402
from src.services.dsh_client import check_dsh_health  # noqa: E402
from src.services.reddit_enhanced_service import (  # noqa: E402
    RedditEnhancedService,
    RedditPost,
)


def post(pid: str, title: str, body: str, comments: list[dict], **kw) -> RedditPost:
    fields = dict(
        id=pid,
        title=title,
        selftext=body,
        url=f"https://reddit.com/r/test/comments/{pid}/",
        permalink=f"https://reddit.com/r/test/comments/{pid}/",
        score=120,
        num_comments=40,
        subreddit="test",
        author="op",
        created_utc=1_760_000_000,
        heuristic_score=1.2,
        anchor_matches=2,
        top_comments=comments,
    )
    return RedditPost(**{**fields, **kw})


QUERY = "How do practitioners export Z-depth passes from Unreal Engine Movie Render Queue?"

POSTS = [
    post(
        "aaa111",
        "Z-depth pass through Movie Render Queue: working setup",
        (
            "After a week of fighting this, the reliable path is the additional "
            "render passes plugin. Enable Movie Render Queue Additional Render "
            "Passes, then add a depth pass in the deferred rendering settings."
        ),
        [
            {
                "body": "Confirming this works: the depth pass must use the same "
                "anti-aliasing settings as the beauty pass or the edges mismatch.",
                "replies": [],
            }
        ],
    ),
    post(
        "bbb222",
        "Best settings for cinematic renders",
        "Just sharing a colour grade I liked. Nothing about exports or passes here.",
        [{"body": "Looks great, what LUT did you use?", "replies": []}],
    ),
    post(
        "ccc333",
        "Compositing depth in Nuke from Unreal",
        (
            "For anyone compositing in Nuke: export the depth pass as 16-bit EXR, "
            "not PNG. The alpha channel of the depth pass carries the occlusion "
            "mask you need for the defocus."
        ),
        [{"body": "16-bit EXR fixed the banding I had in the defocus.", "replies": []}],
    ),
]


async def run_synthesis() -> int:
    """End-to-end check of the synthesis stage on the dsh engine.

    Builds a shortlist in memory and runs the real synthesis prompt + contract,
    so the outcome is one of: a rendered answer, the canonical abstention
    string, or a contract failure (which the pipeline treats as technical).
    """
    from types import SimpleNamespace

    from src.services.reddit_synthesis_service import RedditSynthesisService

    posts = [
        dataclasses.replace(
            p,
            evidence_status="verified",
            evidence_context=f"[opening] {p.selftext[:200]}",
            found_by_strategy="targeted_scout_relevance",
        )
        for p in POSTS
    ]
    result = SimpleNamespace(posts=posts, sources=posts, found_count=len(posts))

    service = RedditSynthesisService()
    started = time.monotonic()
    try:
        rendered = await service.synthesize(QUERY, result, max_sources_in_context=3)
    except Exception as exc:
        print(f"synthesis raised: {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.monotonic() - started

    print(f"\nsynthesis latency: {elapsed:.1f}s for {len(posts)} sources")
    print(f"chars: {len(rendered)}")
    print("--- rendered ---")
    print(rendered[:2000])
    return 0


async def main() -> int:
    if "--synthesis" in sys.argv:
        return await run_synthesis()
    # --count N pads the sample to the real rerank budget
    # (REDDIT_RERANK_CANDIDATES), which is what the judge prompt size and
    # therefore the latency depend on.
    count = config.REDDIT_RERANK_CANDIDATES
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])
    posts = [POSTS[i % len(POSTS)] for i in range(count)]
    for index, original in enumerate(posts):
        if index >= len(POSTS):
            posts[index] = dataclasses.replace(original, id=f"{original.id}-{index}")

    print(f"engine: REDDIT_LLM_BACKEND={config.REDDIT_LLM_BACKEND} "
          f"synth={config.REDDIT_SYNTH_BACKEND} patch={config.DSH_PATCH_PATH or '(none)'}")
    healthy = await check_dsh_health()
    print(f"dsh health: {'ok' if healthy else 'FAILED'}")
    if not healthy:
        return 2

    service = object.__new__(RedditEnhancedService)
    from src.services.dsh_client import get_reddit_llm_client

    service._llm_client = get_reddit_llm_client()

    started = time.monotonic()
    ranked = await service._ai_rerank_posts(QUERY, posts)
    elapsed = time.monotonic() - started

    print(f"\njudge latency: {elapsed:.1f}s for {len(posts)} posts")
    verified = 0
    for p in ranked:
        ok = p.evidence_status == "verified"
        verified += int(ok)
        print(
            f"  {p.id} ai_score={p.ai_score:.2f} final={p.final_score:.3f} "
            f"evidence={p.evidence_status}"
            + (f" src={p.evidence_source}" if p.evidence_source else "")
        )
        if p.ranking_reason:
            print(f"      reason: {p.ranking_reason[:110]}")
        if p.evidence_span:
            print(f"      span:   {p.evidence_span[:110]}")

    report = {
        "latency_s": round(elapsed, 1),
        "posts": len(posts),
        "verified": verified,
        "scores": {p.id: p.ai_score for p in ranked[:5]},
        "statuses": {p.id: p.evidence_status for p in ranked[:5]},
    }
    print("\n" + json.dumps(report, ensure_ascii=False))
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
