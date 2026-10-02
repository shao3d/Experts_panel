#!/usr/bin/env python3
"""Compare two rerank implementations on identical in-memory Reddit sources.

Offline replay is the default. --live explicitly captures candidates once;
running it requires the owner's exception to the normal Reddit CLI boundary.
No dotenv loading, database access, production changes, or token output.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import dataclasses
import json
import logging
import random
import sys
import time
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config
from src.services.reddit_enhanced_service import RedditEnhancedService, RedditPost
from src.services.reddit_synthesis_service import RedditSynthesisService
from src.services.reddit_enhanced_service import EnhancedSearchResult
from src.services.reddit_evidence import match_evidence, select_evidence_passages
from src.services.vertex_llm_client import get_vertex_llm_client
from src.utils.reddit_codex_judge import RedditCodexJudgeClient


def load_baseline(path: Path):
    name = "src.services._reddit_rerank_baseline"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = "src.services"
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module.RedditEnhancedService


class MeasuredClient:
    def __init__(self, model_override=None, transport="openrouter"):
        self.client = RedditCodexJudgeClient() if transport == "codex" else get_vertex_llm_client()
        self.transport = transport
        self.model_override = model_override
        self.calls = []
        self.responses = []

    async def chat_completions_create(self, **kwargs):
        if self.model_override:
            kwargs["model"] = self.model_override
        start = time.monotonic()
        response = await self.client.chat_completions_create(**kwargs)
        self.calls.append({
            "model": response.model,
            "transport": self.transport,
            "reasoning_effort": "low" if self.transport == "codex" else None,
            "served_model_confirmed": self.transport != "codex",
            "seconds": round(time.monotonic() - start, 3),
            "prompt_chars": sum(len(m["content"]) for m in kwargs["messages"]),
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "finish_reason": response.choices[0].finish_reason,
        })
        self.responses.append(response.choices[0].message.content)
        return response


async def capture(case, baseline_class):
    """One retrieval/enrichment, stopped before judgement or reflection."""
    service = baseline_class()
    captured = {}

    async def intercept(candidates, remaining, query, target, comments, anchors,
                        plan, original, must_keep, trace):
        captured.update({
            "posts": [dataclasses.asdict(p) for p in candidates],
            "anchors": anchors,
            "query": query,
            "intent": plan.get("intent", "discussion"),
            "original": original,
            "must_keep": must_keep,
        })
        return [], candidates + remaining, [], []

    service._rank_and_filter = intercept
    try:
        await service.search_enhanced(
            query=case["query"], target_posts=8, include_comments=True,
            recent_only=case.get("recent_only", False),
            original_user_query=case.get("original", case["query"]), user_intent=case.get("intent"),
        )
    finally:
        await service.close()
    return {"case": case, **captured}


async def evaluate(corpus, service_class, model_override=None, transport="openrouter", synthesize=False):
    service = service_class()
    measured = MeasuredClient(model_override, transport)
    service._llm_client = measured
    allowed = {field.name for field in dataclasses.fields(RedditPost)}
    posts = [RedditPost(**{k: v for k, v in p.items() if k in allowed})
             for p in corpus["posts"]]
    started = time.monotonic()
    try:
        ranked = await service._ai_rerank_posts(
            corpus["query"], posts, intent=corpus["intent"],
            anchor_terms=corpus["anchors"],
            original_user_query=corpus["original"],
            must_keep_terms=corpus["must_keep"],
        )
        if not measured.calls:
            raise RuntimeError("Replay requires a completed judge call; heuristic fallback is not a model result")
        selected = service._apply_confidence_threshold(
            ranked, 8, require_anchor_match=bool(corpus["anchors"]),
            intent=corpus["intent"],
        )
        rows = []
        for p in ranked:
            passages = select_evidence_passages(p, " ".join([
                corpus["query"], corpus["original"] or "",
                *(corpus["must_keep"] or []),
            ]))
            rows.append({
                "id": p.id, "url": p.url, "title": p.title,
                "selected": p in selected,
                "score": p.final_score, "ai_score": p.ai_score,
                "reason": p.ranking_reason,
                "evidence": p.evidence_span,
                "evidence_status": p.evidence_status,
                "answer_kind": getattr(p, "answer_kind", "unrated"),
                "limitation": getattr(p, "evidence_limitation", ""),
                "evidence_source": p.evidence_source,
                "quote_in_expanded_excerpts": bool(match_evidence(p.evidence_span, passages)),
            })
        judge_seconds = round(time.monotonic() - started, 3)
        synthesis = None
        synthesis_calls = []
        if synthesize and selected:
            synth = RedditSynthesisService()
            synth._client = MeasuredClient()
            result = EnhancedSearchResult(selected, len(posts), corpus["query"], [], 0)
            synthesis = await synth.synthesize(corpus["original"] or corpus["query"], result)
            synthesis_calls = synth._client.calls
        return {"seconds": judge_seconds, "total_seconds": round(time.monotonic() - started, 3),
                "synthesis": synthesis, "synthesis_calls": synthesis_calls,
                "calls": measured.calls, "responses": measured.responses, "posts": rows}
    finally:
        await service.close()


async def main(args):
    logging.basicConfig(level=logging.CRITICAL)
    if args.transport == "codex" and (args.live or args.candidate_model):
        raise SystemExit("Codex subscription replay uses frozen --corpus and fixed Sol 6.1 low only")
    if args.transport != "codex" and not get_vertex_llm_client().is_configured():
        raise SystemExit("An inherited LLM runtime is required; credentials are never loaded by this script.")
    config.REDDIT_TELEMETRY_ENABLED = False
    config.REDDIT_REFLECTION_RETRY_ENABLED = False
    baseline_class = load_baseline(args.baseline_source)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.live:
        cases = json.loads(args.questions.read_text())["cases"]
        if args.case:
            cases = [c for c in cases if c["id"] in args.case]
        if not cases:
            raise SystemExit("No matching cases")
        corpora = []
        for case in cases:
            target = args.output / f"{case['id']}.corpus.json"
            if target.exists():
                # Reuse the exact captured sources after an interrupted run.
                corpus = json.loads(target.read_text())
            else:
                corpus = await capture(case, baseline_class)
                target.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n")
            corpora.append(corpus)
            print(json.dumps({"captured": case["id"], "candidates": len(corpus["posts"])}), flush=True)
    else:
        corpora = [json.loads(p.read_text()) for p in args.corpus]
    if not corpora:
        raise SystemExit("Supply --corpus or an explicitly authorized --live capture")

    semaphore = asyncio.Semaphore(args.concurrency)

    async def run_one(corpus, repeat, label, implementation):
        async with semaphore:
            case_id = corpus["case"]["id"]
            target = args.output / f"{case_id}.{repeat}.{label}.json"
            if target.exists():
                return
            result = await evaluate(
                copy.deepcopy(corpus), implementation,
                args.candidate_model if label == "candidate" else None,
                args.transport, args.synthesize,
            )
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({"case": case_id, "repeat": repeat, "variant": label,
                              "selected": sum(p["selected"] for p in result["posts"]),
                              "seconds": result["seconds"], "calls": result["calls"]}), flush=True)

    rng = random.Random(20261002)
    pending = []
    for corpus in corpora:
        for repeat in range(args.repeats):
            variants = [("baseline", baseline_class), ("candidate", RedditEnhancedService)]
            rng.shuffle(variants)
            for label, implementation in variants:
                if args.variant and args.variant != label:
                    continue
                pending.append(run_one(corpus, repeat, label, implementation))
    await asyncio.gather(*pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--questions", type=Path, default=BACKEND / "tests/fixtures/reddit_rerank_questions.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--synthesize", action="store_true", help="Also assess final Gemini answers")
    parser.add_argument("--case", action="append")
    parser.add_argument("--corpus", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=["baseline", "candidate"])
    parser.add_argument("--transport", choices=["openrouter", "codex"], default="openrouter")
    parser.add_argument("--candidate-model", help="Isolated judge model experiment; baseline stays unchanged")
    parser.add_argument("--repeats", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
    asyncio.run(main(parser.parse_args()))
