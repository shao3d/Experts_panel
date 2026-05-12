#!/usr/bin/env python3
"""Build a deterministic manual-review packet for coverage-map calibration.

This does not decide admission and does not mutate the database. It samples
real posts, applies the same offline labels as expert_coverage_report.py, and
writes a compact packet that can be reviewed for label precision and blind spots.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import expert_coverage_report as coverage


DEFAULT_OUTPUT_DIR = (
    coverage.REPO_ROOT / "output" / "expert_admission" / "calibration"
)
DEFAULT_EXPERTS = ("akimov", "kornish", "neuraldeep", "refat", "silicbag")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic calibration samples for coverage labels.",
    )
    parser.add_argument(
        "--db-path",
        default=str(coverage.DEFAULT_DB_PATH),
        help=f"SQLite DB path. Default: {coverage.DEFAULT_DB_PATH}.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory. Default: {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--experts",
        default=",".join(DEFAULT_EXPERTS),
        help="Comma-separated expert IDs to sample.",
    )
    parser.add_argument(
        "--posts-per-expert",
        type=int,
        default=8,
        help="Maximum sampled posts per expert. Default: 8.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)
    expert_ids = [item.strip() for item in args.experts.split(",") if item.strip()]

    if not db_path.exists():
        print(f"SQLite DB not found: {db_path}", file=sys.stderr)
        return 2
    if not expert_ids:
        print("No experts selected for calibration.", file=sys.stderr)
        return 2

    with coverage.open_readonly_connection(db_path) as conn:
        packet = build_calibration_packet(
            conn,
            db_path=db_path,
            expert_ids=expert_ids,
            posts_per_expert=args.posts_per_expert,
        )

    write_artifacts(packet, output_dir)
    print(f"Calibration packet written to: {output_dir}")
    print(f"Experts sampled: {len(packet['experts'])}")
    print(f"Posts sampled: {packet['summary']['sampled_post_count']}")
    return 0


def build_calibration_packet(
    conn: Any,
    *,
    db_path: Path,
    expert_ids: list[str],
    posts_per_expert: int,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    experts = []
    missing_experts = []

    for expert_id in expert_ids:
        expert = load_expert(conn, expert_id)
        if not expert:
            missing_experts.append(expert_id)
            continue
        classified_posts = classify_expert_posts(conn, expert_id)
        sampled_posts = select_sample(
            classified_posts,
            max_posts=max(1, posts_per_expert),
        )
        experts.append(
            {
                "expert_id": expert_id,
                "display_name": expert.get("display_name") or expert_id,
                "channel_username": expert.get("channel_username") or "",
                "classified_post_count": len(classified_posts),
                "sampled_post_count": len(sampled_posts),
                "sample_coverage_counts": coverage_counts(sampled_posts),
                "sample_depth_counts": depth_counts(sampled_posts),
                "sampled_posts": sampled_posts,
            }
        )

    return {
        "version": 1,
        "generated_at": generated_at,
        "db_path": str(db_path),
        "purpose": (
            "Manual calibration packet for checking whether current offline "
            "coverage labels are grounded in representative real posts."
        ),
        "summary": {
            "requested_experts": expert_ids,
            "missing_experts": missing_experts,
            "expert_count": len(experts),
            "sampled_post_count": sum(
                expert["sampled_post_count"] for expert in experts
            ),
        },
        "review_guidance": [
            "Mark each post as ok, partial, wrong, or blind_spot.",
            "Treat labels as grounded only when the excerpt supports the topic directly.",
            "Watch for broad terms such as product, model, agent, workflow, and news.",
            "Depth labels are advisory and should be reviewed separately from coverage labels.",
        ],
        "experts": experts,
    }


def load_expert(conn: Any, expert_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT expert_id, display_name, channel_username
        FROM expert_metadata
        WHERE expert_id = ?
        """,
        (expert_id,),
    ).fetchone()
    return dict(row) if row else None


def classify_expert_posts(conn: Any, expert_id: str) -> list[dict[str, Any]]:
    items = []
    for post in coverage.load_posts(conn, expert_id):
        if not coverage.is_text_post(post["message_text"]):
            continue
        metadata = coverage.safe_json_loads(post["post_metadata"])
        if coverage.is_offtopic_post(post["message_text"]):
            labels = []
            depth = "low_signal"
            matched_terms = {}
            depth_terms = []
        else:
            match_context = coverage.build_match_context(post["message_text"], None)
            labels = coverage.classify_coverage_context(match_context)
            depth = coverage.classify_depth_context(match_context)
            matched_terms = matched_coverage_terms(match_context, labels)
            depth_terms = matched_depth_terms(match_context, depth)
        if not labels:
            continue
        items.append(
            {
                "post_id": post["post_id"],
                "telegram_message_id": post["telegram_message_id"],
                "created_at": coverage.normalize_date_string(post["created_at"]),
                "coverage_labels": labels,
                "depth_label": depth,
                "matched_terms": matched_terms,
                "matched_depth_terms": depth_terms,
                "excerpt": coverage.excerpt(post["message_text"], limit=700),
                "review": {
                    "coverage_groundedness": "unreviewed",
                    "depth_groundedness": "unreviewed",
                    "notes": "",
                },
            }
        )
    return items


def matched_coverage_terms(
    match_context: tuple[str, frozenset[str], int],
    labels: list[str],
) -> dict[str, list[str]]:
    return {
        label: matched_terms(match_context, coverage.COVERAGE_MATCHERS[label])
        for label in labels
    }


def matched_depth_terms(
    match_context: tuple[str, frozenset[str], int],
    depth: str,
) -> list[str]:
    for label, matcher in coverage.DEPTH_MATCHERS:
        if label == depth:
            return matched_terms(match_context, matcher)
    return []


def matched_terms(
    match_context: tuple[str, frozenset[str], int],
    matcher: tuple[frozenset[str], tuple[str, ...]],
) -> list[str]:
    text, tokens, _ = match_context
    token_terms, phrase_terms = matcher
    matches = sorted(term for term in token_terms if term in tokens)
    matches.extend(phrase for phrase in phrase_terms if phrase in text)
    return matches


def select_sample(
    classified_posts: list[dict[str, Any]],
    *,
    max_posts: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    seen_areas: set[str] = set()
    sorted_posts = sorted(
        classified_posts,
        key=lambda item: (
            coverage.depth_rank(item["depth_label"]),
            item.get("created_at") or "",
            int(item["telegram_message_id"] or 0),
        ),
        reverse=True,
    )

    for item in sorted_posts:
        labels = set(item["coverage_labels"])
        if not labels.difference(seen_areas):
            continue
        selected.append(item)
        selected_ids.add(int(item["post_id"]))
        seen_areas.update(labels)
        if len(selected) >= max_posts:
            return selected

    for item in spread_sample(sorted_posts, max_posts=max_posts):
        post_id = int(item["post_id"])
        if post_id in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(post_id)
        if len(selected) >= max_posts:
            break
    return selected


def spread_sample(items: list[dict[str, Any]], *, max_posts: int) -> list[dict[str, Any]]:
    if len(items) <= max_posts:
        return items
    step = max(1, len(items) // max_posts)
    return [items[index] for index in range(0, len(items), step)][:max_posts]


def coverage_counts(posts: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for post in posts:
        counts.update(post["coverage_labels"])
    return dict(sorted(counts.items()))


def depth_counts(posts: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(post["depth_label"] for post in posts)
    return dict(sorted(counts.items()))


def write_artifacts(packet: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "calibration_sample.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "calibration_sample.md").write_text(
        render_markdown(packet),
        encoding="utf-8",
    )


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Expert Coverage Calibration Sample",
        "",
        f"Generated: `{packet['generated_at']}`",
        f"DB: `{packet['db_path']}`",
        f"Experts sampled: `{packet['summary']['expert_count']}`",
        f"Posts sampled: `{packet['summary']['sampled_post_count']}`",
        "",
        "## Review Guidance",
        "",
    ]
    for item in packet["review_guidance"]:
        lines.append(f"- {item}")
    if packet["summary"]["missing_experts"]:
        lines.extend(["", "Missing experts:"])
        for expert_id in packet["summary"]["missing_experts"]:
            lines.append(f"- `{expert_id}`")

    for expert in packet["experts"]:
        lines.extend(
            [
                "",
                f"## {expert['expert_id']}",
                "",
                f"Display: `{expert['display_name']}`",
                f"Channel: `{expert['channel_username']}`",
                f"Classified posts: `{expert['classified_post_count']}`",
                f"Sampled posts: `{expert['sampled_post_count']}`",
                "",
                "Sample coverage counts:",
            ]
        )
        for label, count in expert["sample_coverage_counts"].items():
            lines.append(f"- `{label}`: {count}")
        lines.extend(["", "Sample depth counts:"])
        for label, count in expert["sample_depth_counts"].items():
            lines.append(f"- `{label}`: {count}")
        lines.extend(["", "### Posts", ""])

        for post in expert["sampled_posts"]:
            labels = ", ".join(f"`{label}`" for label in post["coverage_labels"])
            lines.extend(
                [
                    f"#### `{expert['expert_id']}:{post['telegram_message_id']}`",
                    "",
                    f"- Date: `{post['created_at'] or 'unknown'}`",
                    f"- Coverage labels: {labels}",
                    f"- Depth label: `{post['depth_label']}`",
                    f"- Matched terms: {format_matched_terms(post)}",
                    f"- Review: `unreviewed`",
                    "",
                    post["excerpt"],
                    "",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def format_matched_terms(post: dict[str, Any]) -> str:
    parts = []
    for label, terms in post.get("matched_terms", {}).items():
        if terms:
            parts.append(f"{label}=[{', '.join(terms[:6])}]")
    depth_terms = post.get("matched_depth_terms") or []
    if depth_terms:
        parts.append(f"depth=[{', '.join(depth_terms[:6])}]")
    return "`" + "; ".join(parts) + "`" if parts else "`-`"


if __name__ == "__main__":
    raise SystemExit(main())
