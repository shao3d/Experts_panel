from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "build_video_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_video_matrix", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_log(path: Path, videos: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "0.1", "videos": videos}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def make_entry(
    video_id: str,
    verdict: str = "ingest",
    cells: list[str] | None = None,
    version_lock: str = "moderate",
    durable_share: float = 0.7,
) -> dict:
    return {
        "video_id": video_id,
        "title": f"Title {video_id}",
        "channel": "Channel",
        "published_at": "2026-09-01",
        "verdict": verdict,
        "scope": "full",
        "decision_basis": "basis",
        "cells": cells
        or ["creative_multimodal/ai_video_direction/build_human_ai_workflow"],
        "attributes": {
            "language": "en",
            "prompt_density": "high",
            "version_lock": version_lock,
            "durable_share": durable_share,
        },
        "decided_at": "2026-09-28",
        "decided_by": "test",
    }


def write_segments_chunked(root: Path, video_id: str, topic_ids: list[str]) -> None:
    target = root / video_id / "ingest" / "segments.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_metadata": {"title": f"Title {video_id}"},
        "segments": [
            {"segment_id": 1001 + index, "topic_id": topic}
            for index, topic in enumerate(topic_ids)
        ],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_segments_legacy(root: Path, video_id: str, topic_ids: list[str]) -> None:
    target = root / video_id / "segments.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"segment_id": 1001 + index, "topic_id": topic}
        for index, topic in enumerate(topic_ids)
    ]
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_matrix_groups_corpus_videos_by_cell(tmp_path):
    module = load_module()
    log_path = write_log(
        tmp_path / "admission_log.json",
        [
            make_entry("vidIngest", cells=["creative_multimodal/montage_language/build_human_ai_workflow"]),
            make_entry("vidScoped", verdict="ingest_scoped", cells=["creative_multimodal/montage_language/build_human_ai_workflow"]),
            make_entry("vidWait", verdict="waitlist", cells=["creative_multimodal/color_and_light/build_human_ai_workflow"]),
        ],
    )
    ingest_root = tmp_path / "ingest"
    write_segments_chunked(ingest_root, "vidIngest", ["topic_a", "topic_b"])
    write_segments_legacy(ingest_root, "vidScoped", ["topic_c"])

    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=ingest_root
    )

    assert matrix["summary"]["ingested_video_count"] == 2
    assert matrix["summary"]["non_corpus_video_count"] == 1
    assert matrix["summary"]["ingested_segment_count"] == 3
    assert len(matrix["cells"]) == 1
    cell = matrix["cells"][0]
    assert cell["cell_id"] == "creative_multimodal/montage_language/build_human_ai_workflow"
    assert [video["video_id"] for video in cell["videos"]] == ["vidIngest", "vidScoped"]
    assert matrix["non_corpus_videos"][0]["video_id"] == "vidWait"
    assert cell["taxonomy_flag"] == "core"


def test_build_matrix_reads_both_ingest_layouts_and_topics(tmp_path):
    module = load_module()
    log_path = write_log(tmp_path / "admission_log.json", [make_entry("vidChunked"), make_entry("vidLegacy")])
    ingest_root = tmp_path / "ingest"
    write_segments_chunked(ingest_root, "vidChunked", ["alpha", "beta", "alpha"])
    write_segments_legacy(ingest_root, "vidLegacy", ["gamma"])

    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=ingest_root
    )

    by_id = {video["video_id"]: video for video in matrix["videos"]}
    assert by_id["vidChunked"]["segment_count"] == 3
    assert by_id["vidChunked"]["topic_ids"] == ["alpha", "beta"]
    assert by_id["vidChunked"]["ingest_layout"] == "chunked"
    assert by_id["vidLegacy"]["segment_count"] == 1
    assert by_id["vidLegacy"]["ingest_layout"] == "legacy"


def test_ingest_stats_returns_empty_for_missing_video(tmp_path):
    module = load_module()
    stats = module.ingest_stats(tmp_path, "vidMissing")
    assert stats["segment_count"] is None
    assert stats["topic_ids"] == []
    assert stats["layout"] is None


def test_taxonomy_flag_marks_unknown_subdomain():
    module = load_module()
    assert (
        module.taxonomy_flag("creative_multimodal", "montage_language", "build_human_ai_workflow")
        == "core"
    )
    flag = module.taxonomy_flag(
        "creative_multimodal", "emotion_and_voice_consistency", "build_human_ai_workflow"
    )
    assert "unknown_subdomain" in flag


def test_creative_subdomains_stay_inside_core_taxonomy():
    module = load_module()
    assert set(module.CREATIVE_SUBDOMAIN_IDS) <= module.build_knowledge_matrix.CORE_SUBDOMAIN_IDS


def test_version_lock_bounds_and_decay_level():
    module = load_module()
    assert module.version_lock_bounds(["high", "moderate", "low-moderate"]) == (
        "low-moderate",
        "high",
    )
    assert module.version_lock_bounds([]) == (None, None)
    assert module.decay_level("high") == "high"
    assert module.decay_level("moderate") == "moderate"
    assert module.decay_level("low-moderate") == "low"


def test_gaps_list_creative_subdomains_without_video(tmp_path):
    module = load_module()
    log_path = write_log(
        tmp_path / "admission_log.json",
        [make_entry("vidOnly", cells=["creative_multimodal/montage_language/build_human_ai_workflow"])],
    )
    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=tmp_path / "ingest"
    )
    gaps = matrix["gaps"]["creative_multimodal_subdomains_without_video"]
    assert "montage_language" not in gaps
    assert "color_and_light" in gaps
    assert "lipsync_dubbing" in gaps
    assert "hybrid_ai_vfx_pipeline" in gaps


def test_taxonomy_flags_include_non_corpus_cells(tmp_path):
    module = load_module()
    log_path = write_log(
        tmp_path / "admission_log.json",
        [
            make_entry(
                "vidWait",
                verdict="waitlist",
                cells=[
                    "creative_multimodal/emotion_and_voice_consistency/build_human_ai_workflow"
                ],
            )
        ],
    )
    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=tmp_path / "ingest"
    )
    assert matrix["cells"] == []
    assert matrix["taxonomy_flags"] == [
        {
            "cell_id": "creative_multimodal/emotion_and_voice_consistency/build_human_ai_workflow",
            "flag": "unknown_subdomain",
            "video_ids": ["vidWait"],
        }
    ]
    markdown = module.render_markdown(matrix)
    assert "emotion_and_voice_consistency" in markdown
    assert "vidWait" in markdown


def test_matrix_tolerates_missing_attributes_and_cells(tmp_path):
    module = load_module()
    entry = make_entry("vidBare")
    entry["attributes"] = None
    entry["cells"] = None
    log_path = write_log(tmp_path / "admission_log.json", [entry])
    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=tmp_path / "ingest"
    )
    assert matrix["videos"][0]["attributes"] == {}
    assert matrix["videos"][0]["cells"] == []


def test_panel_experts_attached_and_marked_primary(tmp_path):
    module = load_module()
    log_path = write_log(
        tmp_path / "admission_log.json",
        [make_entry("vidA", cells=["creative_multimodal/montage_language/build_human_ai_workflow"])],
    )
    panel_path = tmp_path / "knowledge_matrix.json"
    panel_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "matrix_cell_id": "creative_multimodal/montage_language/build_human_ai_workflow",
                        "best_experts": [
                            {
                                "expert_id": "neyrograph",
                                "display_name": "Neyrograph",
                                "source_role": "primary",
                                "aggregate_score": 4.1,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    matrix = module.build_matrix(
        module.read_json(log_path),
        panel_experts=module.load_panel_experts(panel_path),
        ingest_root=tmp_path / "ingest",
    )
    experts = matrix["cells"][0]["panel_experts"]
    assert experts[0]["expert_id"] == "neyrograph"
    markdown = module.render_markdown(matrix)
    assert "neyrograph (primary)" in markdown


def test_render_markdown_includes_cells_gaps_and_scope_marker(tmp_path):
    module = load_module()
    log_path = write_log(
        tmp_path / "admission_log.json",
        [
            make_entry(
                "vidScoped",
                verdict="ingest_scoped",
                cells=["creative_multimodal/montage_language/build_human_ai_workflow"],
            )
        ],
    )
    matrix = module.build_matrix(
        module.read_json(log_path), panel_experts={}, ingest_root=tmp_path / "ingest"
    )
    markdown = module.render_markdown(matrix)
    assert "creative_multimodal/montage_language/build_human_ai_workflow" in markdown
    assert "vidScoped (scoped)" in markdown
    assert "color_and_light" in markdown
