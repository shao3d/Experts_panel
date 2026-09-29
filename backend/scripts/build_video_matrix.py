#!/usr/bin/env python3
"""Build the VideoHub knowledge matrix from the admission log.

Deterministic aggregation over `output/video_admission/admission_log.json`
(no LLM calls): groups corpus videos by taxonomy cell, attaches decay
attributes, panel experts from the panel knowledge matrix, and lists coverage
gaps. Outputs `output/video_admission/video_matrix/video_matrix.{md,json}`.

Usage:
  backend/.venv/bin/python backend/scripts/build_video_matrix.py
  backend/.venv/bin/python backend/scripts/build_video_matrix.py --output-dir /tmp/matrix
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))
import build_knowledge_matrix  # noqa: E402

DEFAULT_ADMISSION_LOG = REPO_ROOT / "output" / "video_admission" / "admission_log.json"
DEFAULT_PANEL_MATRIX = (
    REPO_ROOT / "output" / "expert_admission" / "knowledge_matrix" / "knowledge_matrix.json"
)
DEFAULT_INGEST_ROOT = REPO_ROOT / "output" / "video_ingest"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "video_admission" / "video_matrix"

CORPUS_VERDICTS = {"ingest", "ingest_scoped"}

CREATIVE_SUBDOMAIN_IDS = (
    "multimodal_generation",
    "cg_craft_to_ai",
    "hybrid_ai_vfx_pipeline",
    "ai_video_direction",
    "scene_blocking",
    "montage_language",
    "color_and_light",
    "3d_previz_pipeline",
    "character_consistency",
    "lipsync_dubbing",
    "image_model_workflow",
    "prompt_architecture",
)

VERSION_LOCK_ORDER = {
    "low": 0,
    "low-moderate": 1,
    "moderate": 2,
    "moderate-high": 3,
    "high": 4,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def split_cell_id(cell_id: str) -> tuple[str, str, str]:
    parts = cell_id.split("/")
    domain_id = parts[0] if parts else "unknown_domain"
    subdomain_id = parts[1] if len(parts) > 1 else "unknown_subdomain"
    query_intent_id = parts[2] if len(parts) > 2 else "unknown_query_intent"
    return domain_id, subdomain_id, query_intent_id


def taxonomy_flag(domain_id: str, subdomain_id: str, query_intent_id: str) -> str:
    flags: list[str] = []
    if domain_id not in build_knowledge_matrix.CORE_DOMAIN_IDS:
        flags.append("unknown_domain")
    if subdomain_id not in build_knowledge_matrix.CORE_SUBDOMAIN_IDS:
        flags.append("unknown_subdomain")
    if query_intent_id not in build_knowledge_matrix.CORE_QUERY_INTENT_IDS:
        flags.append("unknown_query_intent")
    return "+".join(flags) if flags else "core"


def ingest_stats(ingest_root: Path, video_id: str) -> dict[str, Any]:
    candidates = (
        (ingest_root / video_id / "ingest" / "segments.json", "chunked"),
        (ingest_root / video_id / "segments.json", "legacy"),
    )
    for path, layout in candidates:
        if not path.is_file():
            continue
        try:
            payload = read_json(path)
        except (ValueError, OSError):
            continue
        segments = payload if isinstance(payload, list) else payload.get("segments", [])
        topic_ids = sorted(
            {str(seg.get("topic_id")) for seg in segments if seg.get("topic_id")}
        )
        return {
            "segment_count": len(segments),
            "topic_ids": topic_ids,
            "layout": layout,
            "source_path": display_path(path),
        }
    return {"segment_count": None, "topic_ids": [], "layout": None, "source_path": None}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_panel_experts(panel_matrix_path: Path) -> dict[str, list[dict[str, Any]]]:
    if not panel_matrix_path.is_file():
        return {}
    payload = read_json(panel_matrix_path)
    experts_by_cell: dict[str, list[dict[str, Any]]] = {}
    for cell in payload.get("cells", []):
        cell_id = cell.get("matrix_cell_id")
        if not cell_id:
            continue
        experts_by_cell[cell_id] = [
            {
                "expert_id": expert.get("expert_id"),
                "display_name": expert.get("display_name"),
                "source_role": expert.get("source_role"),
                "aggregate_score": expert.get("aggregate_score"),
            }
            for expert in cell.get("best_experts", [])
        ]
    return experts_by_cell


def version_lock_bounds(values: list[Any]) -> tuple[str | None, str | None]:
    known = [str(value) for value in values if value]
    if not known:
        return None, None
    ordered = sorted(known, key=lambda value: VERSION_LOCK_ORDER.get(value, -1))
    return ordered[0], ordered[-1]


def decay_level(version_lock: str | None) -> str | None:
    if version_lock is None:
        return None
    score = VERSION_LOCK_ORDER.get(version_lock, -1)
    if score >= VERSION_LOCK_ORDER["moderate-high"]:
        return "high"
    if score == VERSION_LOCK_ORDER["moderate"]:
        return "moderate"
    if score >= 0:
        return "low"
    return None


def entry_attributes(entry: dict[str, Any]) -> dict[str, Any]:
    attributes = entry.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def decay_payload(videos: list[dict[str, Any]]) -> dict[str, Any]:
    version_locks = [entry_attributes(video).get("version_lock") for video in videos]
    durable_shares = [
        entry_attributes(video).get("durable_share") for video in videos
    ]
    known_shares = [float(value) for value in durable_shares if value is not None]
    best, worst = version_lock_bounds(version_locks)
    return {
        "level": decay_level(worst),
        "worst_version_lock": worst,
        "best_version_lock": best,
        "min_durable_share": min(known_shares) if known_shares else None,
        "max_durable_share": max(known_shares) if known_shares else None,
    }


def video_record(entry: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": entry.get("video_id"),
        "title": entry.get("title"),
        "channel": entry.get("channel"),
        "published_at": entry.get("published_at"),
        "verdict": entry.get("verdict"),
        "scope": entry.get("scope"),
        "in_corpus": entry.get("verdict") in CORPUS_VERDICTS,
        "segment_count": stats.get("segment_count"),
        "topic_ids": stats.get("topic_ids"),
        "ingest_layout": stats.get("layout"),
        "cells": list(entry.get("cells") or []),
        "attributes": dict(entry_attributes(entry)),
        "decided_at": entry.get("decided_at"),
        "decided_by": entry.get("decided_by"),
        "ingested_at": entry.get("ingested_at"),
    }


def build_matrix(
    log: dict[str, Any],
    panel_experts: dict[str, list[dict[str, Any]]],
    ingest_root: Path,
    source_admission_log: str | None = None,
) -> dict[str, Any]:
    entries = log.get("videos", [])
    records: list[dict[str, Any]] = []
    cells_map: dict[str, dict[str, Any]] = {}

    for entry in entries:
        stats = ingest_stats(ingest_root, str(entry.get("video_id", "")))
        record = video_record(entry, stats)
        records.append(record)
        if not record["in_corpus"]:
            continue
        for cell_id in record["cells"]:
            cell = cells_map.setdefault(
                cell_id,
                {
                    "cell_id": cell_id,
                    "videos": [],
                },
            )
            cell["videos"].append(record)

    cells_payload: list[dict[str, Any]] = []
    for cell_id in sorted(cells_map):
        domain_id, subdomain_id, query_intent_id = split_cell_id(cell_id)
        flag = taxonomy_flag(domain_id, subdomain_id, query_intent_id)
        videos = cells_map[cell_id]["videos"]
        cells_payload.append(
            {
                "cell_id": cell_id,
                "domain_id": domain_id,
                "subdomain_id": subdomain_id,
                "query_intent_id": query_intent_id,
                "taxonomy_flag": flag,
                "video_count": len(videos),
                "videos": [
                    {
                        "video_id": video["video_id"],
                        "title": video["title"],
                        "channel": video["channel"],
                        "verdict": video["verdict"],
                        "scope": video["scope"],
                        "version_lock": entry_attributes(video).get("version_lock"),
                        "durable_share": entry_attributes(video).get("durable_share"),
                    }
                    for video in videos
                ],
                "panel_experts": panel_experts.get(cell_id, []),
                "decay": decay_payload(videos),
            }
        )

    taxonomy_flags: list[dict[str, Any]] = []
    flag_videos: dict[str, list[str]] = {}
    for record in records:
        for cell_id in record["cells"]:
            flag_videos.setdefault(cell_id, []).append(str(record["video_id"]))
    for cell_id in sorted(flag_videos):
        domain_id, subdomain_id, query_intent_id = split_cell_id(cell_id)
        flag = taxonomy_flag(domain_id, subdomain_id, query_intent_id)
        if flag != "core":
            taxonomy_flags.append(
                {
                    "cell_id": cell_id,
                    "flag": flag,
                    "video_ids": flag_videos[cell_id],
                }
            )

    covered_subdomains = {
        cell["subdomain_id"] for cell in cells_payload if cell["domain_id"] == "creative_multimodal"
    }
    gaps = sorted(set(CREATIVE_SUBDOMAIN_IDS) - covered_subdomains)
    corpus_records = [record for record in records if record["in_corpus"]]
    waitlist_records = [
        record
        for record in records
        if record["verdict"] not in CORPUS_VERDICTS
    ]

    return {
        "schema_version": "video_hub_knowledge_matrix.v0.1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_admission_log": source_admission_log
        or display_path(DEFAULT_ADMISSION_LOG),
        "summary": {
            "log_video_count": len(records),
            "ingested_video_count": len(corpus_records),
            "non_corpus_video_count": len(waitlist_records),
            "ingested_segment_count": sum(
                record["segment_count"] or 0 for record in corpus_records
            ),
            "covered_cell_count": len(cells_payload),
            "covered_subdomain_count": len(covered_subdomains),
            "gap_subdomain_count": len(gaps),
        },
        "cells": cells_payload,
        "videos": records,
        "gaps": {
            "creative_multimodal_subdomains_without_video": gaps,
        },
        "taxonomy_flags": taxonomy_flags,
        "non_corpus_videos": [
            {
                "video_id": record["video_id"],
                "title": record["title"],
                "verdict": record["verdict"],
                "cells": record["cells"],
            }
            for record in waitlist_records
        ],
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    summary = matrix["summary"]
    lines: list[str] = []
    lines.append("# VideoHub Knowledge Matrix")
    lines.append("")
    lines.append(
        "Автогенерация: `backend/.venv/bin/python backend/scripts/build_video_matrix.py`"
    )
    lines.append(
        f"Источник: `{matrix['source_admission_log']}` "
        "(механика гейта: `docs/architecture/expert-admission-control.md` §16 "
        "«VideoHub Sidecar Admission»)"
    )
    lines.append(f"Last updated: {matrix['created_at'][:10]} (generated)")
    lines.append("")
    lines.append(
        f"Видео в журнале: **{summary['log_video_count']}** "
        f"(в корпусе: {summary['ingested_video_count']}, "
        f"вне корпуса: {summary['non_corpus_video_count']}), "
        f"сегментов: **{summary['ingested_segment_count']}**, "
        f"клеток с покрытием: **{summary['covered_cell_count']}** "
        f"(subdomains: {summary['covered_subdomain_count']} из {len(CREATIVE_SUBDOMAIN_IDS)})."
    )
    lines.append("")

    lines.append("## Покрытие клеток (корпус)")
    lines.append("")
    lines.append("| Клетка | Видео | Эксперты Панели (RU) | Распад |")
    lines.append("|---|---|---|---|")
    for cell in matrix["cells"]:
        video_parts = []
        for video in cell["videos"]:
            label = video["video_id"]
            if video.get("verdict") == "ingest_scoped":
                label += " (scoped)"
            video_parts.append(label)
        experts = ", ".join(
            expert["expert_id"]
            + (" (primary)" if expert.get("source_role") == "primary" else "")
            for expert in cell["panel_experts"]
        ) or "—"
        decay = cell["decay"]
        if decay["level"] is None:
            decay_text = "—"
        else:
            vl_text = (
                decay["best_version_lock"]
                if decay["best_version_lock"] == decay["worst_version_lock"]
                else f"{decay['best_version_lock']}–{decay['worst_version_lock']}"
            )
            shares = decay["min_durable_share"]
            share_text = (
                f"ds {decay['min_durable_share']}–{decay['max_durable_share']}"
                if shares is not None
                else ""
            )
            decay_text = f"vl {vl_text}" + (f", {share_text}" if share_text else "")
        flag = "" if cell["taxonomy_flag"] == "core" else f" ⚠ {cell['taxonomy_flag']}"
        lines.append(
            f"| `{cell['cell_id']}`{flag} | {', '.join(video_parts)} | {experts} | {decay_text} |"
        )
    lines.append("")
    lines.append(
        "Распад — агрегат видео-атрибутов журнала (`version_lock` min–max, "
        "`durable_share` min–max по видео клетки); per-cell уточнение — Фаза 1."
    )
    lines.append("")

    lines.append("## Видео в журнале")
    lines.append("")
    lines.append(
        "| ID | Видео | Канал | Вердикт | Сегменты | Клетки | version_lock | durable_share |"
    )
    lines.append("|---|---|---|---|---:|---|---|---|")
    for video in matrix["videos"]:
        segments = video["segment_count"] if video["segment_count"] is not None else "—"
        version_lock = entry_attributes(video).get("version_lock", "—")
        durable_share = entry_attributes(video).get("durable_share", "—")
        title = (video.get("title") or "").replace("|", "\\|")
        channel = (video.get("channel") or "—").replace("|", "\\|")
        lines.append(
            f"| `{video['video_id']}` | {title} | {channel} | "
            f"{video.get('verdict') or '—'} | {segments} | {len(video['cells'])} | "
            f"{version_lock} | {durable_share} |"
        )
    lines.append("")

    lines.append("## Gaps (creative_multimodal без видео-покрытия)")
    lines.append("")
    gaps = matrix["gaps"]["creative_multimodal_subdomains_without_video"]
    if gaps:
        for subdomain in gaps:
            lines.append(f"- `{subdomain}`")
    else:
        lines.append("— все поддомены покрыты.")
    lines.append("")

    non_corpus = matrix["non_corpus_videos"]
    if non_corpus:
        lines.append("## Вне корпуса (журнал)")
        lines.append("")
        for video in non_corpus:
            lines.append(
                f"- `{video['video_id']}` — {video.get('verdict')} "
                f"({video.get('title') or 'без названия'})"
            )
        lines.append("")

    flags = matrix["taxonomy_flags"]
    if flags:
        lines.append("## Флаги таксономии")
        lines.append("")
        for flag in flags:
            video_ids = ", ".join(flag.get("video_ids", []))
            lines.append(
                f"- `{flag['cell_id']}` — {flag['flag']} "
                f"(видео: {video_ids or '—'}; кандидат в `alias_to_*` / "
                "`promote_to_core`, решает владелец)"
            )
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the VideoHub knowledge matrix from the admission log."
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_ADMISSION_LOG)
    parser.add_argument("--panel-matrix", type=Path, default=DEFAULT_PANEL_MATRIX)
    parser.add_argument("--ingest-root", type=Path, default=DEFAULT_INGEST_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log = read_json(args.log)
    panel_experts = load_panel_experts(args.panel_matrix)
    matrix = build_matrix(
        log,
        panel_experts,
        args.ingest_root,
        source_admission_log=display_path(args.log),
    )

    json_path = args.output_dir / "video_matrix.json"
    md_path = args.output_dir / "video_matrix.md"
    write_json(json_path, matrix)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(matrix), encoding="utf-8")

    if not args.quiet:
        summary = matrix["summary"]
        print(
            f"video_matrix: {summary['ingested_video_count']} видео в корпусе, "
            f"{summary['ingested_segment_count']} сегментов, "
            f"{summary['covered_cell_count']} клеток, "
            f"{summary['gap_subdomain_count']} gaps"
        )
        print(f"written: {md_path}")
        print(f"written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
