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


def _message_id(message: dict[str, Any]) -> int:
    return int(message.get("id") or 0)


def _message_in_date_range(
    message: dict[str, Any],
    min_date: str | None,
    max_date: str | None,
) -> bool:
    message_date = message.get("date")
    if not message_date:
        return True
    if min_date and message_date < min_date:
        return False
    if max_date and message_date > max_date:
        return False
    return True


def _root_message_id(
    message: dict[str, Any],
    messages_by_id: dict[int, dict[str, Any]],
    text_by_message_id: dict[int, str],
) -> int:
    """Resolve Telegram reply chains to the nearest text root in the export."""

    original_id = _message_id(message)
    current_id = original_id
    seen: set[int] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        current = messages_by_id.get(current_id)
        if not current:
            return original_id
        parent_id = current.get("reply_to_message_id")
        if not parent_id:
            return current_id if current_id in text_by_message_id else original_id
        parent_id = int(parent_id)
        if parent_id not in messages_by_id:
            return original_id
        current_id = parent_id

    return original_id


def parse_posts_and_comments(
    data: dict[str, Any],
    max_posts: int | None,
    include_reply_messages_as_comments: bool,
    min_date: str | None,
    max_date: str | None,
) -> tuple[list[Post], dict[int, list[Comment]], dict[str, Any]]:
    messages = [
        message
        for message in data.get("messages") or []
        if message.get("type") == "message"
        and _message_in_date_range(message, min_date, max_date)
    ]
    messages_by_id = {_message_id(message): message for message in messages if _message_id(message)}
    text_by_message_id = {
        _message_id(message): message_text(message)
        for message in messages
        if _message_id(message) and message_text(message)
    }

    root_ids: list[int] = []
    comments_by_root_id: dict[int, list[dict[str, Any]]] = {}
    for message in messages:
        text = message_text(message)
        if not text:
            continue
        message_id = _message_id(message)
        root_id = (
            _root_message_id(message, messages_by_id, text_by_message_id)
            if include_reply_messages_as_comments
            else message_id
        )
        if root_id != message_id and root_id in text_by_message_id:
            comments_by_root_id.setdefault(root_id, []).append(message)
        else:
            root_ids.append(message_id)

    posts: list[Post] = []
    post_by_root_id: dict[int, Post] = {}
    for root_id in root_ids:
        message = messages_by_id[root_id]
        posts.append(
            Post(
                source_ref=f"P{len(posts) + 1:04d}",
                post_id=len(posts) + 1,
                telegram_message_id=root_id,
                created_at=message.get("date"),
                view_count=message.get("views"),
                forward_count=message.get("forwards"),
                reply_count=message.get("replies"),
                text=text_by_message_id[root_id],
            )
        )
        post_by_root_id[root_id] = posts[-1]
        if max_posts is not None and len(posts) >= max_posts:
            break

    comments_by_post_id: dict[int, list[Comment]] = {post.post_id: [] for post in posts}
    for root_id, reply_messages in comments_by_root_id.items():
        post = post_by_root_id.get(root_id)
        if post is None:
            continue
        for reply_message in reply_messages:
            reply_id = _message_id(reply_message)
            text = text_by_message_id.get(reply_id)
            if not text:
                continue
            comment_count = len(comments_by_post_id[post.post_id]) + 1
            comments_by_post_id[post.post_id].append(
                Comment(
                    source_ref=f"{post.source_ref}.C{comment_count:04d}",
                    comment_id=comment_count,
                    telegram_comment_id=reply_id,
                    post_id=post.post_id,
                    author_name=normalize_text(reply_message.get("from") or reply_message.get("actor") or ""),
                    created_at=reply_message.get("date"),
                    text=text,
                )
            )

    parse_stats = {
        "raw_message_count": len(data.get("messages") or []),
        "text_message_count": len(text_by_message_id),
        "post_message_count_in_packet": len(posts),
        "reply_message_count_in_packet": sum(len(comments) for comments in comments_by_post_id.values()),
        "reply_messages_as_comments": include_reply_messages_as_comments,
        "min_date": min_date,
        "max_date": max_date,
    }
    return posts, comments_by_post_id, parse_stats


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
        "--min-date",
        help="Optional inclusive ISO date lower bound for messages, e.g. 2025-01-01.",
    )
    parser.add_argument(
        "--max-date",
        help="Optional inclusive ISO date upper bound for messages.",
    )
    parser.add_argument(
        "--thread-replies-as-comments",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Treat Telegram reply messages in the export as comments under the replied root post.",
    )
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
    posts, comments_by_post_id, parse_stats = parse_posts_and_comments(
        data=data,
        max_posts=args.max_posts,
        include_reply_messages_as_comments=args.thread_replies_as_comments,
        min_date=args.min_date,
        max_date=args.max_date,
    )
    if not posts:
        raise SystemExit(f"No text messages found in {args.json}")

    out_dir = args.out_dir or (DEFAULT_OUTPUT_ROOT / args.expert_id / "input")
    manifest = write_packet(
        expert=expert,
        posts=posts,
        comments_by_post_id=comments_by_post_id,
        output_dir=out_dir,
        model=args.model,
        max_comments_per_post=None,
    )

    manifest_path = out_dir / "run_manifest.json"
    manifest["script"] = "backend/scripts/export_semantic_passport_packet_from_telegram_json.py"
    manifest["source_export"] = {
        "path": str(args.json),
        "chat_name": data.get("name") or data.get("title"),
        "chat_type": data.get("type"),
        "chat_id": data.get("id"),
        "message_count_raw": len(data.get("messages") or []),
        "message_count_text_in_packet": parse_stats["text_message_count"],
        "post_message_count_in_packet": parse_stats["post_message_count_in_packet"],
        "comment_message_count_in_packet": parse_stats["reply_message_count_in_packet"],
        "thread_replies_as_comments": parse_stats["reply_messages_as_comments"],
        "min_date": parse_stats["min_date"],
        "max_date": parse_stats["max_date"],
        "has_comments_in_export": parse_stats["reply_message_count_in_packet"] > 0,
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
