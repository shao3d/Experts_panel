"""Mode contract tests for standard vs deep research prompts."""
from __future__ import annotations

from pathlib import Path

from orchestrator import (
    DEEP_RESEARCH_SKILL,
    EXTRACT_SKILL,
    SEARCH_SKILL,
    STANDARD_RESEARCH_SKILL,
    _research_suffix,
    _skills_for_mode,
    effective_max_report_chars,
)


def test_standard_prompt_forbids_delegate_task_and_requires_extracts():
    suffix = _research_suffix("standard", "auto", 6000)

    assert "MODE — STANDARD RESEARCH" in suffix
    assert STANDARD_RESEARCH_SKILL in suffix
    assert "Do NOT use delegate_task" in suffix
    assert "saved extract" in suffix
    assert "Do not put any URL" in suffix
    assert "extract file IDs alone" in suffix
    assert "Use the file write/edit tool" in suffix
    assert "Do not put the report body in the final assistant message" in suffix
    assert "verify `./report.md` exists and is non-empty" in suffix
    assert "The final assistant message must contain\nonly this marker" in suffix
    assert "Target maximum report length: 6000 characters" in suffix
    assert "Round 1" not in suffix
    assert "Round 2" not in suffix


def test_standard_skill_requires_real_report_file_before_marker():
    overlay_root = Path(__file__).resolve().parents[2]
    candidates = [
        overlay_root
        / "hermes_skills"
        / "searcharvester-standard-research"
        / "SKILL.md",
        Path("/opt/data/skills/searcharvester-standard-research/SKILL.md"),
    ]
    skill_path = next(path for path in candidates if path.exists())
    skill = skill_path.read_text(encoding="utf-8")

    assert "Write `./report.md` using the file write/edit tool" in skill
    assert "Do not put the report\n   body in the final assistant message" in skill
    assert "wc -c ./report.md" in skill
    assert "with exactly this marker and no report body" in skill
    assert "instead of claiming\n`REPORT_SAVED`" in skill


def test_deep_prompt_preserves_two_round_delegate_pipeline():
    suffix = _research_suffix("deep", "ru", 20000)

    assert "MODE — DEEP RESEARCH" in suffix
    assert DEEP_RESEARCH_SKILL in suffix
    assert "Round 1: delegate_task" in suffix
    assert "Round 2: delegate_task" in suffix
    assert "TIME BUDGET" in suffix
    assert "2 researchers" in suffix
    assert "No third round" in suffix
    assert "ROUND 2 TOOL DISCIPLINE" in suffix
    assert "google_search" in suffix
    assert "http://searxng" in suffix
    assert "Write the final report in Russian" in suffix


def test_deep_skill_has_default_completion_budget():
    overlay_root = Path(__file__).resolve().parents[2]
    candidates = [
        overlay_root
        / "hermes_skills"
        / "searcharvester-deep-research"
        / "SKILL.md",
        Path("/opt/data/skills/searcharvester-deep-research/SKILL.md"),
        Path("/opt/searcharvester-hermes-skills/searcharvester-deep-research/SKILL.md"),
    ]
    skill_path = next(path for path in candidates if path.exists())
    skill = skill_path.read_text(encoding="utf-8")

    assert "version: 2.5.0" in skill
    assert "Default time budget" in skill
    assert "Use 2 researchers" in skill
    assert "Each researcher targets 3–4 successful extracts" in skill
    assert "The fact-checker verifies the top 3 facts" in skill
    assert "Allowed terminal commands" in skill
    assert "Forbidden commands/tools" in skill
    assert "Do not use `google_search`, `skill_view`, `read_file`" in skill


def test_skills_are_filtered_by_mode():
    skills = [
        STANDARD_RESEARCH_SKILL,
        DEEP_RESEARCH_SKILL,
        SEARCH_SKILL,
        EXTRACT_SKILL,
    ]

    assert _skills_for_mode(skills, "standard") == [
        STANDARD_RESEARCH_SKILL,
        SEARCH_SKILL,
        EXTRACT_SKILL,
    ]
    assert _skills_for_mode(skills, "deep") == [
        DEEP_RESEARCH_SKILL,
        SEARCH_SKILL,
        EXTRACT_SKILL,
    ]


def test_effective_max_report_chars_defaults_by_mode():
    assert effective_max_report_chars("standard", None) == 6000
    assert effective_max_report_chars("deep", None) == 20000
    assert effective_max_report_chars("standard", 9000) == 9000
