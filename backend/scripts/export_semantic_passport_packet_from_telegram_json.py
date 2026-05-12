#!/usr/bin/env python3
"""Export a semantic passport packet directly from Telegram Desktop JSON.

This is a read-only candidate/control path. It does not import the channel into
the production SQLite database and does not create expert metadata. The output
packet is compatible with run_semantic_passport_vertex.py.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from export_semantic_passport_packet import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_ROOT,
    Comment,
    Expert,
    Post,
    estimate_tokens_from_chars,
    normalize_text,
    write_packet,
)
from src.utils.entities_converter import entities_to_markdown_from_json  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def message_text(message: dict[str, Any]) -> str:
    return normalize_text(
        entities_to_markdown_from_json(
            message.get("text", ""),
            message.get("text_entities"),
        )
    )


def parse_posts(data: dict[str, Any], max_posts: int | None) -> list[Post]:
    posts: list[Post] = []
    for message in data.get("messages") or []:
        if message.get("type") != "message":
            continue
        text = message_text(message)
        if not text:
            continue
        posts.append(
            Post(
                source_ref=f"P{len(posts) + 1:04d}",
                post_id=len(posts) + 1,
                telegram_message_id=int(message.get("id") or len(posts) + 1),
                created_at=message.get("date"),
                view_count=message.get("views"),
                forward_count=message.get("forwards"),
                reply_count=message.get("replies"),
                text=text,
            )
        )
        if max_posts is not None and len(posts) >= max_posts:
            break
    return posts


def infer_display_name(data: dict[str, Any], fallback: str) -> str:
    return data.get("name") or data.get("title") or fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a semantic passport packet from Telegram Desktop JSON without DB import."
    )
    parser.add_argument("--json", type=Path, required=True, help="Telegram Desktop result.json path.")
    parser.add_argument("--expert-id", required=True, help="Candidate/control expert ID.")
    parser.add_argument("--display-name", help="Display name. Defaults to JSON chat name.")
    parser.add_argument(
        "--channel-username",
        default="unknown",
        help="Channel username when known. Defaults to unknown for external control exports.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory. Defaults to output/expert_admission/semantic_passports/<expert-id>/input.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Target model ID for manifest notes.")
    parser.add_argument("--max-posts", type=int, default=None, help="Optional smoke-test cap.")
    parser.add_argument(
        "--copy-source-json",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Copy the Telegram JSON export into the packet directory for reproducibility.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = read_json(args.json)
    expert = Expert(
        expert_id=args.expert_id,
        display_name=args.display_name or infer_display_name(data, args.expert_id),
        channel_username=args.channel_username,
    )
    posts = parse_posts(data, args.max_posts)
    if not posts:
        raise SystemExit(f"No text messages found in {args.json}")

    out_dir = args.out_dir or (DEFAULT_OUTPUT_ROOT / args.expert_id / "input")
    comments_by_post_id: dict[int, list[Comment]] = {post.post_id: [] for post in posts}
    manifest = write_packet(
        expert=expert,
        posts=posts,
        comments_by_post_id=comments_by_post_id,
        output_dir=out_dir,
        model=args.model,
        max_comments_per_post=0,
    )

    manifest_path = out_dir / "run_manifest.json"
    manifest["script"] = "backend/scripts/export_semantic_passport_packet_from_telegram_json.py"
    manifest["source_export"] = {
        "path": str(args.json),
        "chat_name": data.get("name") or data.get("title"),
        "chat_type": data.get("type"),
        "chat_id": data.get("id"),
        "message_count_raw": len(data.get("messages") or []),
        "message_count_text_in_packet": len(posts),
        "has_comments_in_export": False,
    }
    if args.copy_source_json:
        copied_name = f"{args.expert_id}_telegram_export.json"
        shutil.copyfile(args.json, out_dir / copied_name)
        manifest["files"]["source_export_json"] = copied_name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stats = manifest["corpus_stats"]
    artifact_stats = manifest["artifact_stats"]
    print(f"Wrote semantic passport packet: {out_dir}")
    print(
        "Corpus: "
        f"{stats['post_count']} posts, "
        f"{stats['comment_count']} comments, "
        f"{stats['total_chars']} chars, "
        f"~{stats['estimated_input_tokens_from_corpus_chars']['chars_div_4']} tokens chars/4"
    )
    print(
        "Combined prompt estimate: "
        f"{artifact_stats['combined_prompt_chars']} chars, "
        f"{artifact_stats['combined_prompt_utf8_bytes']} utf8 bytes, "
        f"~{artifact_stats['estimated_input_tokens_from_combined_prompt_chars']['chars_div_4']} tokens chars/4, "
        f"~{estimate_tokens_from_chars(artifact_stats['combined_prompt_utf8_bytes'])['chars_div_3']} tokens bytes/3"
    )
    print(f"Combined prompt: {out_dir / manifest['files']['combined_prompt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
