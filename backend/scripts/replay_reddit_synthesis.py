#!/usr/bin/env python3
"""Isolated synthesis A/B on previously authorized, frozen Reddit shortlists.

No retrieval, reranking, DB or credential loading. Both variants receive the
same ordered posts and evidence excerpts; output never alters production.
"""

import argparse
import asyncio
import copy
import dataclasses
import hashlib
import json
import logging
import random
import re
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.services.reddit_enhanced_service import EnhancedSearchResult, RedditPost
from src.services.reddit_evidence import select_evidence_passages
from src.services.reddit_synthesis_service import RedditSynthesisService
from replay_reddit_rerank import MeasuredClient


class RecordingClient(MeasuredClient):
    def __init__(self):
        super().__init__()
        self.failures = []

    async def chat_completions_create(self, **kwargs):
        try:
            return await super().chat_completions_create(**kwargs)
        except Exception as exc:
            self.failures.append(
                {
                    "type": type(exc).__name__,
                    "status_code": getattr(exc, "status_code", None),
                    "error_type": getattr(exc, "error_type", None),
                    "affordable_output_tokens": next(
                        iter(re.findall(r"can only afford (\d+)", str(exc))), None
                    ),
                }
            )
            raise


def baseline_class(path):
    name = "src.services._reddit_synthesis_baseline"
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), "src.services"
    sys.modules[name] = module
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module.RedditSynthesisService


def frozen_shortlist(corpus, ranking):
    allowed = {f.name for f in dataclasses.fields(RedditPost)}
    by_id = {p["id"]: p for p in corpus["posts"]}
    posts = []
    for row in ranking["posts"]:
        if not row["selected"]:
            continue
        p = RedditPost(**{k: v for k, v in by_id[row["id"]].items() if k in allowed})
        p.evidence_span = row["evidence"]
        p.evidence_status = row["evidence_status"]
        p.evidence_source = row.get("evidence_source", "")
        p.evidence_context = (
            "\n".join(
                x.render()
                for x in select_evidence_passages(
                    p,
                    " ".join(
                        [
                            corpus["query"],
                            corpus["original"] or "",
                            *(corpus["must_keep"] or []),
                        ]
                    ),
                )
            )
            if p.evidence_status == "verified"
            else ""
        )
        posts.append(p)
    return EnhancedSearchResult(posts, len(corpus["posts"]), corpus["query"], [], 0)


async def main(args):
    logging.basicConfig(level=logging.CRITICAL)
    config.REDDIT_TELEMETRY_ENABLED = False
    config.REDDIT_SYNTH_BACKEND = "gemini"
    if args.max_tokens:
        config.REDDIT_SYNTH_MAX_TOKENS = args.max_tokens
    old = baseline_class(args.baseline_source)
    args.output.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(2)

    async def run(case_id, corpus, frozen, label, implementation, repeat):
        target = args.output / f"{case_id}.{repeat}.{label}.json"
        if target.exists():
            return
        async with sem:
            service = implementation()
            measured = RecordingClient()
            service._client = measured
            start = time.monotonic()
            answer = await service.synthesize(
                corpus["original"] or corpus["query"], copy.deepcopy(frozen)
            )
            elapsed = time.monotonic() - start
            if not measured.calls:
                raise RuntimeError(
                    "No completed model response: " + json.dumps(measured.failures)
                )
            raw = measured.responses[-1]
            try:
                decision = (
                    json.loads(raw).get("coverage") if label == "candidate" else None
                )
            except (ValueError, AttributeError):
                decision = "invalid"
            record = dict(
                case=case_id,
                variant=label,
                seconds=round(elapsed, 3),
                coverage=decision,
                answer=answer,
                calls=measured.calls,
                responses=measured.responses,
                abstained=service.is_explicit_abstention(answer),
                fallback="Synthesis is temporarily unavailable" in answer
                or "Синтез временно недоступен" in answer,
                input_sha256=hashlib.sha256(
                    json.dumps(dataclasses.asdict(frozen), sort_keys=True).encode()
                ).hexdigest(),
                source_ids=[p.id for p in frozen.posts],
            )
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        k: record[k]
                        for k in [
                            "case",
                            "variant",
                            "seconds",
                            "coverage",
                            "abstained",
                            "fallback",
                        ]
                    }
                ),
                flush=True,
            )

    tasks = []
    rng = random.Random(20261002)
    for path in sorted(args.rankings.glob("*.candidate.json")):
        case_id = path.name.split(".")[0]
        if args.case and case_id not in args.case:
            continue
        corpus_path = next(
            (
                root / f"{case_id}.corpus.json"
                for root in args.corpora
                if (root / f"{case_id}.corpus.json").exists()
            ),
            None,
        )
        if corpus_path is None:
            raise RuntimeError(f"No corpus for {case_id}")
        corpus = json.loads(corpus_path.read_text())
        frozen = frozen_shortlist(corpus, json.loads(path.read_text()))
        for repeat in range(args.repeats):
            variants = [("baseline", old), ("candidate", RedditSynthesisService)]
            rng.shuffle(variants)
            for label, implementation in variants:
                if not args.variant or args.variant == label:
                    tasks.append(
                        run(case_id, corpus, frozen, label, implementation, repeat)
                    )
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--corpora", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append")
    parser.add_argument(
        "--max-tokens",
        type=int,
        choices=[1024, 2048, 4096],
        help="Isolated diagnostic output budget; default uses runtime config",
    )
    parser.add_argument("--variant", choices=["baseline", "candidate"])
    parser.add_argument("--repeats", type=int, choices=[1, 2], default=1)
    asyncio.run(main(parser.parse_args()))
