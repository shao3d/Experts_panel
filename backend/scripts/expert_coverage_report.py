#!/usr/bin/env python3
"""Build read-only Experts Panel coverage/passport reports from SQLite.

This is the first implementation slice of docs/architecture/expert-admission-control.md.
It intentionally does not call Vertex, Panex, Agent Context, Telegram, or mutate
the database. It reads the current local corpus and writes JSON/Markdown
artifacts for human review.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "experts.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "expert_admission"
VIDEO_HUB_EXPERT_ID = "video_hub"
WHITESPACE_RE = re.compile(r"\s+")
ASCII_TOKEN_RE = re.compile(r"^[a-z0-9_+#.]+$")
TEXT_TOKEN_RE = re.compile(r"[a-z0-9_+#.]+")
KEYWORD_SPLIT_RE = re.compile(r"[,;|\s]+")
KEYWORD_TRIM_RE = re.compile(r"^[^\wа-яА-ЯёЁ+#.]+|[^\wа-яА-ЯёЁ+#.]+$")
OFFTOPIC_MARKERS = ("#оффтоп", "#offtopic", "#off-topic", "off topic")


COVERAGE_RULES: dict[str, tuple[str, ...]] = {
    "coding_agents": (
        "claude code",
        "codex",
        "cursor",
        "copilot",
        "windsurf",
        "ai coding",
        "agentic coding",
        "vibe coding",
        "вайб",
        "кодинг",
        "агентное программирование",
    ),
    "agent_ops": (
        "mcp",
        "multi-agent",
        "multi agent",
        "subagent",
        "agent orchestration",
        "hooks",
        "skills",
        "tool calling",
        "tool use",
        "function calling",
        "агентн",
        "агент",
        "скил",
        "оркестрац",
    ),
    "evals_quality": (
        "eval",
        "benchmark",
        "regression",
        "quality measurement",
        "test suite",
        "golden",
        "failure analysis",
        "метрик",
        "бенчмарк",
        "оценк качества",
        "регрессион",
    ),
    "rag_retrieval_knowledge": (
        "rag",
        "retrieval",
        "vector search",
        "embedding",
        "embeddings",
        "knowledge base",
        "fts",
        "search quality",
        "вектор",
        "эмбеддинг",
        "база знаний",
    ),
    "ai_product_pm": (
        "product",
        "pm",
        "prd",
        "roadmap",
        "user value",
        "product manager",
        "продукт",
        "продакт",
        "ценность",
    ),
    "business_adoption": (
        "business",
        "roi",
        "adoption",
        "enterprise",
        "workflow automation",
        "go-to-market",
        "arr",
        "бизнес",
        "внедрен",
        "эконом",
        "окупаем",
    ),
    "ai_ux_workflow": (
        "ux",
        "workflow",
        "human-in-the-loop",
        "collaboration",
        "productivity",
        "воркфлоу",
        "пользовательский опыт",
        "продуктив",
    ),
    "security_privacy_governance": (
        "security",
        "privacy",
        "governance",
        "compliance",
        "security policy",
        "ai risk",
        "data leak",
        "безопас",
        "приват",
        "комплаенс",
        "регулир",
        "утечк",
    ),
    "ai_engineering_infra": (
        "inference",
        "deploy",
        "deployment",
        "latency",
        "observability",
        "backend",
        "runtime",
        "gpu",
        "инфра",
        "деплой",
        "латент",
    ),
    "model_landscape": (
        "gpt",
        "gemini",
        "claude",
        "llama",
        "mistral",
        "openai",
        "anthropic",
        "model",
        "модель",
        "llm",
    ),
    "creative_multimodal": (
        "image generation",
        "video generation",
        "audio",
        "voice",
        "multimodal",
        "генерация изображ",
        "генерация видео",
        "мультимод",
    ),
    "general_ai_news": (
        "ai news",
        "искусственный интеллект",
        "нейросет",
    ),
}


DEPTH_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "benchmark_or_eval",
        (
            "benchmark",
            "eval",
            "measurement",
            "metric",
            "бенчмарк",
            "метрик",
            "оценк качества",
        ),
    ),
    (
        "case_study",
        (
            "case study",
            "case",
            "implemented",
            "we built",
            "we used",
            "кейс",
            "внедрил",
            "запустил",
            "сделали",
        ),
    ),
    (
        "practitioner_experience",
        (
            "my experience",
            "our experience",
            "in production",
            "lesson",
            "практи",
            "опыт",
            "в прод",
            "урок",
        ),
    ),
    (
        "architecture_analysis",
        (
            "architecture",
            "tradeoff",
            "trade-off",
            "pattern",
            "why",
            "because",
            "design",
            "архитект",
            "паттерн",
            "компромисс",
            "почему",
        ),
    ),
    (
        "howto_or_checklist",
        (
            "how to",
            "guide",
            "checklist",
            "step by step",
            "tutorial",
            "гайд",
            "чеклист",
            "инструкц",
            "как ",
        ),
    ),
    (
        "tool_release",
        (
            "launch",
            "released",
            "release",
            "introducing",
            "new version",
            "анонс",
            "релиз",
            "запуст",
            "вышел",
        ),
    ),
)


DEPTH_LABELS = (
    "practitioner_experience",
    "case_study",
    "architecture_analysis",
    "benchmark_or_eval",
    "howto_or_checklist",
    "tool_release",
    "announcement_or_news",
    "low_signal",
)


STOP_KEYWORDS = {
    "and",
    "the",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "что",
    "как",
    "это",
    "для",
    "или",
    "the",
    "ai",
    "ии",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build read-only current expert coverage reports.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite DB path. Default: {DEFAULT_DB_PATH}.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory. Default: {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--include-video-hub",
        action="store_true",
        help="Include video_hub in the report. Defaults to human Telegram experts only.",
    )
    parser.add_argument(
        "--max-representatives-per-expert",
        type=int,
        default=8,
        help="Maximum representative posts per expert passport. Default: 8.",
    )
    parser.add_argument(
        "--max-representatives-per-area",
        type=int,
        default=5,
        help="Maximum representative posts per coverage area in summary. Default: 5.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)

    if not db_path.exists():
        print(f"SQLite DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_readonly_connection(db_path) as conn:
        report = build_report(
            conn,
            db_path=db_path,
            include_video_hub=args.include_video_hub,
            max_representatives_per_expert=args.max_representatives_per_expert,
            max_representatives_per_area=args.max_representatives_per_area,
        )

    write_artifacts(report, output_dir)
    print(f"Coverage report written to: {output_dir}")
    print(f"Experts: {report['summary']['expert_count']}")
    print(f"Human experts excluded video_hub: {not args.include_video_hub}")
    print(f"Warnings: {len(report['warnings'])}")
    return 0


def open_readonly_connection(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.resolve()
    uri = f"file:{quote(str(resolved), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def build_report(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    include_video_hub: bool = False,
    max_representatives_per_expert: int = 8,
    max_representatives_per_area: int = 5,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    table_names = get_table_names(conn)
    experts = load_experts(conn, include_video_hub=include_video_hub)
    global_counts = load_global_counts(conn, table_names=table_names)

    passports = []
    warnings: list[str] = []
    coverage_area_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for expert in experts:
        passport = build_expert_passport(
            conn,
            expert,
            table_names=table_names,
            max_representatives=max_representatives_per_expert,
        )
        passports.append(passport)
        warnings.extend(passport["warnings"])
        for representative in passport["representative_posts"]:
            for area in representative["coverage_labels"]:
                coverage_area_sources[area].append(
                    {
                        "expert_id": passport["expert_id"],
                        "telegram_message_id": representative["telegram_message_id"],
                        "created_at": representative["created_at"],
                        "depth_label": representative["depth_label"],
                        "excerpt": representative["excerpt"],
                    }
                )

    coverage_map = build_coverage_map(
        passports,
        coverage_area_sources=coverage_area_sources,
        max_representatives_per_area=max_representatives_per_area,
    )
    gaps = identify_gaps(passports, coverage_map)
    interpretation = build_interpretation(passports, coverage_map, gaps)

    return {
        "version": 1,
        "generated_at": generated_at,
        "db_path": str(db_path),
        "include_video_hub": include_video_hub,
        "summary": {
            "expert_count": len(passports),
            "global_counts": global_counts,
        },
        "coverage_map": coverage_map,
        "gaps": gaps,
        "interpretation": interpretation,
        "warnings": warnings,
        "experts": passports,
    }


def get_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def load_global_counts(
    conn: sqlite3.Connection,
    *,
    table_names: set[str],
) -> dict[str, int]:
    counts = {
        "expert_metadata": scalar_int(conn, "SELECT COUNT(*) FROM expert_metadata"),
        "human_expert_metadata": scalar_int(
            conn,
            "SELECT COUNT(*) FROM expert_metadata WHERE expert_id != ?",
            (VIDEO_HUB_EXPERT_ID,),
        ),
        "posts": scalar_int(conn, "SELECT COUNT(*) FROM posts"),
        "text_posts": scalar_int(
            conn,
            "SELECT COUNT(*) FROM posts WHERE message_text IS NOT NULL AND length(message_text) > 30",
        ),
        "post_embeddings": 0,
        "posts_fts": 0,
    }
    if "post_embeddings" in table_names:
        counts["post_embeddings"] = scalar_int(
            conn, "SELECT COUNT(*) FROM post_embeddings"
        )
    if "posts_fts" in table_names:
        counts["posts_fts"] = scalar_int(conn, "SELECT COUNT(*) FROM posts_fts")
    return counts


def load_experts(
    conn: sqlite3.Connection,
    *,
    include_video_hub: bool,
) -> list[dict[str, Any]]:
    sql = """
        SELECT expert_id, display_name, channel_username
        FROM expert_metadata
    """
    params: tuple[Any, ...] = ()
    if not include_video_hub:
        sql += " WHERE expert_id != ?"
        params = (VIDEO_HUB_EXPERT_ID,)
    sql += " ORDER BY expert_id"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def build_expert_passport(
    conn: sqlite3.Connection,
    expert: dict[str, Any],
    *,
    table_names: set[str],
    max_representatives: int,
) -> dict[str, Any]:
    expert_id = expert["expert_id"]
    posts = load_posts(conn, expert_id)
    post_count = len(posts)
    text_posts = [p for p in posts if is_text_post(p["message_text"])]
    metadata_entries = [safe_json_loads(p["post_metadata"]) for p in posts]
    valid_metadata_entries = [m for m in metadata_entries if isinstance(m, dict)]

    primary_topics: Counter[str] = Counter()
    concepts: Counter[str] = Counter()
    keywords: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    depth_profile: Counter[str] = Counter()
    representatives: list[dict[str, Any]] = []

    for post, metadata in zip(posts, metadata_entries):
        if isinstance(metadata, dict):
            topic = clean_label(metadata.get("primary_topic"))
            if topic:
                primary_topics[topic] += 1
            for concept in as_string_list(metadata.get("concepts")):
                concepts[concept] += 1
            for keyword in extract_keywords(metadata.get("keywords")):
                keywords[keyword] += 1

        is_offtopic = is_offtopic_post(post["message_text"])
        if is_offtopic:
            labels = []
            depth = "low_signal"
        else:
            match_context = build_match_context(post["message_text"], None)
            labels = classify_coverage_context(match_context)
            depth = classify_depth_context(match_context)

        for label in labels:
            coverage[label] += 1
        depth_profile[depth] += 1

        if labels and len(representatives) < max_representatives * 3:
            representatives.append(
                build_representative_post(post, labels=labels, depth=depth)
            )

    representative_posts = select_representatives(
        representatives,
        max_representatives=max_representatives,
    )
    embedding_count = count_embeddings(conn, expert_id, table_names=table_names)
    fts_count = count_fts(conn, expert_id, table_names=table_names)
    date_range = build_date_range(posts)
    warnings = build_expert_warnings(
        expert_id=expert_id,
        post_count=post_count,
        text_post_count=len(text_posts),
        metadata_valid_count=len(valid_metadata_entries),
        embedding_count=embedding_count,
        fts_count=fts_count,
    )

    return {
        "expert_id": expert_id,
        "display_name": expert.get("display_name") or expert_id,
        "channel_username": expert.get("channel_username") or "",
        "post_count": post_count,
        "text_post_count": len(text_posts),
        "metadata_valid_count": len(valid_metadata_entries),
        "embedding_count": embedding_count,
        "fts_count": fts_count,
        "date_range": date_range,
        "metadata_coverage_ratio": ratio(len(valid_metadata_entries), post_count),
        "embedding_coverage_ratio": ratio(embedding_count, len(text_posts)),
        "runtime_readiness": {
            "text_posts_ready": bool(text_posts),
            "fts_ready": fts_count > 0,
            "embeddings_ready": embedding_count > 0,
            "metadata_advisory_ready": len(valid_metadata_entries) > 0,
        },
        "top_primary_topics": counter_items(primary_topics, 12),
        "top_concepts": counter_items(concepts, 12),
        "top_keywords": counter_items(keywords, 20),
        "coverage": {area: int(coverage.get(area, 0)) for area in COVERAGE_RULES},
        "coverage_strength": {
            area: coverage_strength(int(coverage.get(area, 0)), len(text_posts))
            for area in COVERAGE_RULES
        },
        "depth_profile": {label: int(depth_profile.get(label, 0)) for label in DEPTH_LABELS},
        "representative_posts": representative_posts,
        "warnings": warnings,
    }


def load_posts(conn: sqlite3.Connection, expert_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT post_id, telegram_message_id, message_text, created_at, post_metadata
        FROM posts
        WHERE expert_id = ?
        ORDER BY created_at DESC, telegram_message_id DESC
        """,
        (expert_id,),
    ).fetchall()


def is_text_post(text: str | None) -> bool:
    return bool(text and len(text.strip()) > 30)


def is_offtopic_post(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    return any(marker in normalized[:240] for marker in OFFTOPIC_MARKERS)


def safe_json_loads(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def classify_coverage(text: str | None, metadata: dict[str, Any] | None) -> list[str]:
    return classify_coverage_context(build_match_context(text, metadata))


def classify_coverage_context(
    match_context: tuple[str, frozenset[str], int],
) -> list[str]:
    labels = []
    for area, matcher in COVERAGE_MATCHERS.items():
        if matches_any(match_context, matcher):
            labels.append(area)
    if labels and "general_ai_news" in labels and len(labels) > 1:
        labels.remove("general_ai_news")
    return labels


def classify_depth(text: str | None, metadata: dict[str, Any] | None) -> str:
    return classify_depth_context(build_match_context(text, metadata))


def classify_depth_context(match_context: tuple[str, frozenset[str], int]) -> str:
    char_count = match_context[2]
    for label, matcher in DEPTH_MATCHERS:
        if matches_any(match_context, matcher):
            return label
    if matches_any(match_context, ANNOUNCEMENT_MATCHER):
        return "announcement_or_news"
    if char_count < 220:
        return "low_signal"
    return "announcement_or_news"


def build_match_context(
    text: str | None,
    metadata: dict[str, Any] | None,
) -> tuple[str, frozenset[str], int]:
    combined = combined_text(text, metadata)
    return (
        combined,
        frozenset(TEXT_TOKEN_RE.findall(combined)),
        len((text or "").strip()),
    )


def combined_text(text: str | None, metadata: dict[str, Any] | None) -> str:
    parts = [text or ""]
    if isinstance(metadata, dict):
        parts.append(str(metadata.get("primary_topic") or ""))
        parts.extend(as_string_list(metadata.get("entities")))
        parts.extend(as_string_list(metadata.get("concepts")))
        parts.append(str(metadata.get("keywords") or ""))
    return normalize_text(" ".join(parts))


def normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value.lower()).strip()


def compile_match_terms(terms: tuple[str, ...]) -> tuple[frozenset[str], tuple[str, ...]]:
    token_terms = []
    phrase_terms = []
    for term in terms:
        normalized = normalize_text(term)
        if not normalized:
            continue
        if ASCII_TOKEN_RE.fullmatch(normalized):
            token_terms.append(normalized)
        else:
            phrase_terms.append(normalized)
    return frozenset(token_terms), tuple(phrase_terms)


def matches_any(
    match_context: tuple[str, frozenset[str], int],
    matcher: tuple[frozenset[str], tuple[str, ...]],
) -> bool:
    text, tokens, _ = match_context
    token_terms, phrase_terms = matcher
    if token_terms and not token_terms.isdisjoint(tokens):
        return True
    return any(phrase in text for phrase in phrase_terms)


COVERAGE_MATCHERS = {
    area: compile_match_terms(terms) for area, terms in COVERAGE_RULES.items()
}
DEPTH_MATCHERS = tuple(
    (label, compile_match_terms(terms)) for label, terms in DEPTH_RULES
)
ANNOUNCEMENT_MATCHER = compile_match_terms(
    ("news", "announcement", "анонс", "релиз")
)


def clean_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        labels = []
        for item in value:
            cleaned = clean_label(item)
            if cleaned:
                labels.append(cleaned)
        return labels
    if isinstance(value, str):
        cleaned = clean_label(value)
        return [cleaned] if cleaned else []
    return []


def extract_keywords(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    raw_tokens = KEYWORD_SPLIT_RE.split(value.lower())
    keywords = []
    for token in raw_tokens:
        cleaned = KEYWORD_TRIM_RE.sub("", token)
        if len(cleaned) < 3 or cleaned in STOP_KEYWORDS:
            continue
        keywords.append(cleaned)
    return keywords


def build_representative_post(
    post: sqlite3.Row,
    *,
    labels: list[str],
    depth: str,
) -> dict[str, Any]:
    text = post["message_text"] or ""
    return {
        "telegram_message_id": post["telegram_message_id"],
        "created_at": normalize_date_string(post["created_at"]),
        "coverage_labels": labels,
        "depth_label": depth,
        "excerpt": excerpt(text),
        "reason": f"{', '.join(labels[:3])}; depth={depth}",
    }


def select_representatives(
    representatives: list[dict[str, Any]],
    *,
    max_representatives: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_areas: set[str] = set()
    seen_messages: set[int] = set()

    sorted_reps = sorted(
        representatives,
        key=lambda rep: (
            depth_rank(rep["depth_label"]),
            rep.get("created_at") or "",
        ),
        reverse=True,
    )
    for rep in sorted_reps:
        message_id = int(rep["telegram_message_id"])
        if message_id in seen_messages:
            continue
        labels = list(rep.get("coverage_labels") or [])
        if labels and any(label not in seen_areas for label in labels):
            selected.append(rep)
            seen_messages.add(message_id)
            seen_areas.update(labels)
        if len(selected) >= max_representatives:
            return selected

    for rep in sorted_reps:
        message_id = int(rep["telegram_message_id"])
        if message_id in seen_messages:
            continue
        selected.append(rep)
        seen_messages.add(message_id)
        if len(selected) >= max_representatives:
            break
    return selected


def depth_rank(label: str) -> int:
    ranks = {
        "benchmark_or_eval": 7,
        "case_study": 6,
        "practitioner_experience": 5,
        "architecture_analysis": 4,
        "howto_or_checklist": 3,
        "tool_release": 2,
        "announcement_or_news": 1,
        "low_signal": 0,
    }
    return ranks.get(label, 0)


def count_embeddings(
    conn: sqlite3.Connection,
    expert_id: str,
    *,
    table_names: set[str],
) -> int:
    if "post_embeddings" not in table_names:
        return 0
    return scalar_int(
        conn,
        """
        SELECT COUNT(*)
        FROM post_embeddings pe
        JOIN posts p ON p.post_id = pe.post_id
        WHERE p.expert_id = ?
        """,
        (expert_id,),
    )


def count_fts(
    conn: sqlite3.Connection,
    expert_id: str,
    *,
    table_names: set[str],
) -> int:
    if "posts_fts" not in table_names:
        return 0
    return scalar_int(
        conn,
        """
        SELECT COUNT(*)
        FROM posts_fts f
        JOIN posts p ON p.post_id = f.rowid
        WHERE p.expert_id = ?
        """,
        (expert_id,),
    )


def build_date_range(posts: list[sqlite3.Row]) -> dict[str, str | None]:
    dates = [normalize_date_string(post["created_at"]) for post in posts if post["created_at"]]
    dates = [date for date in dates if date]
    if not dates:
        return {"first_post": None, "last_post": None}
    return {"first_post": min(dates), "last_post": max(dates)}


def normalize_date_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:10]


def build_expert_warnings(
    *,
    expert_id: str,
    post_count: int,
    text_post_count: int,
    metadata_valid_count: int,
    embedding_count: int,
    fts_count: int,
) -> list[str]:
    warnings = []
    if post_count == 0:
        warnings.append(f"{expert_id}: no posts")
    if text_post_count == 0 and post_count > 0:
        warnings.append(f"{expert_id}: no text posts longer than 30 chars")
    if metadata_valid_count == 0 and text_post_count > 0:
        warnings.append(f"{expert_id}: no valid post_metadata; coverage is text-only")
    elif text_post_count and metadata_valid_count / max(1, text_post_count) < 0.5:
        warnings.append(f"{expert_id}: post_metadata coverage below 50%")
    if embedding_count == 0 and text_post_count > 0:
        warnings.append(f"{expert_id}: no embeddings for text posts")
    elif text_post_count and embedding_count / max(1, text_post_count) < 0.8:
        warnings.append(f"{expert_id}: embedding coverage below 80% of text posts")
    if fts_count == 0 and text_post_count > 0:
        warnings.append(f"{expert_id}: no FTS rows for text posts")
    return warnings


def build_coverage_map(
    passports: list[dict[str, Any]],
    *,
    coverage_area_sources: dict[str, list[dict[str, Any]]],
    max_representatives_per_area: int,
) -> dict[str, Any]:
    coverage_map = {}
    for area in COVERAGE_RULES:
        expert_counts = [
            {
                "expert_id": passport["expert_id"],
                "count": int(passport["coverage"].get(area, 0)),
                "strength": passport["coverage_strength"].get(area, "none"),
            }
            for passport in passports
            if int(passport["coverage"].get(area, 0)) > 0
        ]
        expert_counts.sort(key=lambda item: (-item["count"], item["expert_id"]))
        total_posts = sum(item["count"] for item in expert_counts)
        coverage_map[area] = {
            "total_matching_posts": total_posts,
            "expert_count": len(expert_counts),
            "status": area_status(total_posts, len(expert_counts)),
            "top_experts": expert_counts[:8],
            "representative_posts": coverage_area_sources.get(area, [])[
                :max_representatives_per_area
            ],
        }
    return coverage_map


def identify_gaps(
    passports: list[dict[str, Any]],
    coverage_map: dict[str, Any],
) -> dict[str, Any]:
    return {
        "thin_or_missing_areas": [
            area
            for area, info in coverage_map.items()
            if info["status"] in {"gap", "thin"}
        ],
        "experts_without_metadata": [
            passport["expert_id"]
            for passport in passports
            if passport["metadata_valid_count"] == 0 and passport["text_post_count"] > 0
        ],
        "experts_with_embedding_gaps": [
            passport["expert_id"]
            for passport in passports
            if passport["text_post_count"] > 0
            and passport["embedding_coverage_ratio"] < 0.8
        ],
    }


def build_interpretation(
    passports: list[dict[str, Any]],
    coverage_map: dict[str, Any],
    gaps: dict[str, Any],
) -> list[str]:
    notes = [
        "Coverage status is raw-text keyword density only; it is not an admission verdict.",
    ]
    if not gaps["thin_or_missing_areas"]:
        notes.append(
            "No missing areas were found at the current coarse taxonomy level; "
            "candidate decisions should focus on incremental query utility, depth, "
            "freshness, and duplicate risk."
        )
    dense_news = [
        area
        for area, info in coverage_map.items()
        if area in {"model_landscape", "general_ai_news"}
        and info["status"] == "strong"
    ]
    if dense_news:
        notes.append(
            "Dense news/model coverage means another broad-news expert needs "
            "strong source-level evidence before admission."
        )
    metadata_gaps = [
        passport["expert_id"]
        for passport in passports
        if passport["metadata_valid_count"] == 0 and passport["text_post_count"] > 0
    ]
    if metadata_gaps:
        notes.append(
            "Some experts lack valid post_metadata, so current-roster coverage "
            "must be treated as text-derived for them: "
            + ", ".join(metadata_gaps)
            + "."
        )
    return notes


def area_status(total_posts: int, expert_count: int) -> str:
    if total_posts == 0 or expert_count == 0:
        return "gap"
    if expert_count < 2 or total_posts < 10:
        return "thin"
    if expert_count < 4 or total_posts < 40:
        return "medium"
    return "strong"


def coverage_strength(count: int, text_post_count: int) -> str:
    if count <= 0 or text_post_count <= 0:
        return "none"
    share = count / text_post_count
    if count >= 40 and share >= 0.10:
        return "strong"
    if count >= 12 and share >= 0.04:
        return "medium"
    return "thin"


def counter_items(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": int(count)}
        for value, count in counter.most_common(limit)
    ]


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def scalar_int(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def excerpt(text: str | None, limit: int = 320) -> str:
    cleaned = WHITESPACE_RE.sub(" ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    passports_dir = output_dir / "passports"
    passports_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / "current_coverage.json", report)
    (output_dir / "current_coverage.md").write_text(
        render_current_coverage_markdown(report),
        encoding="utf-8",
    )

    for passport in report["experts"]:
        expert_id = passport["expert_id"]
        write_json(passports_dir / f"{expert_id}.json", passport)
        (passports_dir / f"{expert_id}.md").write_text(
            render_passport_markdown(passport),
            encoding="utf-8",
        )


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_current_coverage_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Expert Coverage Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"DB: `{report['db_path']}`",
        f"Experts included: `{report['summary']['expert_count']}`",
        "",
        "This report is read-only and uses heuristic offline labels. Runtime proof",
        "still requires source-level query probes through Agent Context.",
        "",
        "## Interpretation",
        "",
    ]
    for note in report.get("interpretation", []):
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Global Counts",
            "",
            "| Metric | Count |",
            "|---|---:|",
        ]
    )
    for key, value in report["summary"]["global_counts"].items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend(
        [
            "",
            "## Coverage Map",
            "",
            "| Area | Status | Matching Posts | Experts | Top Experts |",
            "|---|---|---:|---:|---|",
        ]
    )
    for area, info in report["coverage_map"].items():
        top_experts = ", ".join(
            f"{item['expert_id']} ({item['count']})"
            for item in info["top_experts"][:4]
        )
        lines.append(
            f"| `{area}` | {info['status']} | {info['total_matching_posts']} | "
            f"{info['expert_count']} | {top_experts or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Gaps",
            "",
            "Thin or missing areas:",
        ]
    )
    for area in report["gaps"]["thin_or_missing_areas"]:
        lines.append(f"- `{area}`")
    if not report["gaps"]["thin_or_missing_areas"]:
        lines.append("- none")

    lines.extend(["", "Experts without valid post_metadata:"])
    for expert_id in report["gaps"]["experts_without_metadata"]:
        lines.append(f"- `{expert_id}`")
    if not report["gaps"]["experts_without_metadata"]:
        lines.append("- none")

    lines.extend(["", "Experts with embedding gaps:"])
    for expert_id in report["gaps"]["experts_with_embedding_gaps"]:
        lines.append(f"- `{expert_id}`")
    if not report["gaps"]["experts_with_embedding_gaps"]:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Expert Summary",
            "",
            "| Expert | Posts | Text | Metadata | Embeddings | Top Coverage | Warnings |",
            "|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    for passport in report["experts"]:
        top_coverage = top_coverage_string(passport)
        lines.append(
            f"| `{passport['expert_id']}` | {passport['post_count']} | "
            f"{passport['text_post_count']} | {passport['metadata_valid_count']} | "
            f"{passport['embedding_count']} | {top_coverage or '-'} | "
            f"{len(passport['warnings'])} |"
        )

    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")

    lines.append("")
    return "\n".join(lines)


def render_passport_markdown(passport: dict[str, Any]) -> str:
    lines = [
        f"# Expert Passport: {passport['expert_id']}",
        "",
        f"Display name: `{passport['display_name']}`",
        f"Channel: `{passport['channel_username']}`",
        "",
        "## Counts",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Posts | {passport['post_count']} |",
        f"| Text posts | {passport['text_post_count']} |",
        f"| Valid post_metadata | {passport['metadata_valid_count']} |",
        f"| Embeddings | {passport['embedding_count']} |",
        f"| FTS rows | {passport['fts_count']} |",
        "",
        "## Coverage",
        "",
        "| Area | Count | Strength |",
        "|---|---:|---|",
    ]
    for area, count in sorted(
        passport["coverage"].items(),
        key=lambda item: (-int(item[1]), item[0]),
    ):
        if int(count) <= 0:
            continue
        lines.append(
            f"| `{area}` | {count} | {passport['coverage_strength'][area]} |"
        )
    if not any(passport["coverage"].values()):
        lines.append("| - | 0 | none |")

    lines.extend(
        [
            "",
            "## Depth Profile",
            "",
            "| Depth | Count |",
            "|---|---:|",
        ]
    )
    for label in DEPTH_LABELS:
        lines.append(f"| `{label}` | {passport['depth_profile'].get(label, 0)} |")

    lines.extend(["", "## Top Metadata Signals", ""])
    append_counter_section(lines, "Primary topics", passport["top_primary_topics"])
    append_counter_section(lines, "Concepts", passport["top_concepts"])
    append_counter_section(lines, "Keywords", passport["top_keywords"])

    lines.extend(["", "## Representative Posts", ""])
    if passport["representative_posts"]:
        for post in passport["representative_posts"]:
            labels = ", ".join(f"`{label}`" for label in post["coverage_labels"])
            lines.append(
                f"- `{passport['expert_id']}:{post['telegram_message_id']}` "
                f"({post.get('created_at') or 'unknown'}, {post['depth_label']}; "
                f"{labels}) - {post['excerpt']}"
            )
    else:
        lines.append("- none")

    if passport["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in passport["warnings"]:
            lines.append(f"- {warning}")

    lines.append("")
    return "\n".join(lines)


def append_counter_section(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
) -> None:
    lines.append(f"### {title}")
    if not items:
        lines.append("")
        lines.append("- none")
        lines.append("")
        return
    lines.append("")
    for item in items[:10]:
        lines.append(f"- `{item['value']}`: {item['count']}")
    lines.append("")


def top_coverage_string(passport: dict[str, Any]) -> str:
    items = [
        (area, int(count))
        for area, count in passport["coverage"].items()
        if int(count) > 0
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{area}:{count}" for area, count in items[:3])


if __name__ == "__main__":
    raise SystemExit(main())
