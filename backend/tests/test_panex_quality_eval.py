#!/usr/bin/env python3
"""BDD checks for Panex product-quality eval scaffolding."""

import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts import panex_quality_eval as quality_eval


SCENARIOS_PATH = BACKEND_DIR / "tests" / "fixtures" / "panex_quality_scenarios.json"
RUBRIC_PATH = REPO_ROOT / "docs" / "quality" / "panex-product-quality-rubric.md"


def test_quality_scenarios_fixture_has_realistic_panex_cases():
    scenarios = quality_eval.load_scenarios(SCENARIOS_PATH)
    scenario_ids = {scenario["id"] for scenario in scenarios}

    assert {
        "subagents_tradeoff",
        "context_rot",
        "file_first_embeddings",
        "llm_caching_recent",
        "weak_signal_probe",
        "expand_sources_followup",
    }.issubset(scenario_ids)
    for scenario in scenarios:
        assert scenario["query"]
        assert scenario["response_mode"] in {"expert_digest", "source_expand"}
        assert scenario["rubric"]["min_score"] >= 0.70
        assert scenario["rubric"]["must_cover_any"]
        assert scenario["rubric"]["max_answer_chars"] <= 7500


def test_quality_rubric_separates_product_answer_quality_from_api_contract():
    content = RUBRIC_PATH.read_text(encoding="utf-8")
    normalized = quality_eval.normalize(content)

    assert "api tests prove" in normalized
    assert "product-quality eval" in normalized
    assert "practitioner posts" in normalized
    assert "not as a ground-truth oracle" in normalized
    assert "source-backed signals" in normalized
    assert "must not frame practitioner opinions as proof" in normalized
    assert "panex_quality_eval.py" in content


def test_good_panex_answer_passes_product_quality_rubric():
    scenario = _scenario("subagents_tradeoff")

    result = quality_eval.evaluate_scenario(
        scenario=scenario,
        answer_text=_good_subagents_answer(),
        digest_payload=_digest_payload(scenario),
    )

    assert result["status"] == "passed"
    assert result["score"] >= scenario["rubric"]["min_score"]
    assert result["critical_issues"] == []
    checks = {check["id"]: check for check in result["checks"]}
    assert checks["source_grounding"]["score"] == 1.0
    assert checks["signal_honesty"]["score"] == 1.0
    assert checks["request_passport"]["score"] == 1.0


def test_source_expand_answer_passes_with_lean_expansion_passport():
    scenario = _scenario("expand_sources_followup")

    result = quality_eval.evaluate_scenario(
        scenario=scenario,
        answer_text=_good_source_expand_answer(),
        digest_payload=_source_expand_payload(),
    )

    assert result["status"] == "passed"
    checks = {check["id"]: check for check in result["checks"]}
    assert checks["request_passport"]["score"] == 1.0
    assert "source_expand Request passport" in checks["request_passport"]["details"]
    assert checks["source_grounding"]["score"] == 1.0
    assert checks["expand_path"]["score"] == 1.0


def test_proof_framed_ungrounded_answer_fails_quality_rubric():
    scenario = _scenario("subagents_tradeoff")
    bad_answer = (
        "Subagents всегда полезны. Это факт и строго доказано. "
        "Их надо использовать везде, потому что так система лучше. "
        "Источники не нужны: вывод очевиден."
    )

    result = quality_eval.evaluate_scenario(
        scenario=scenario,
        answer_text=bad_answer,
        digest_payload=_digest_payload(scenario),
    )

    assert result["status"] == "failed"
    assert "signal_honesty" in result["critical_issues"]
    checks = {check["id"]: check for check in result["checks"]}
    assert checks["source_grounding"]["score"] == 0.0
    assert checks["signal_honesty"]["score"] == 0.0


def test_main_writes_report_for_answer_dir_and_cached_digest(tmp_path, monkeypatch):
    scenario = _scenario("subagents_tradeoff")
    scenarios_path = tmp_path / "scenarios.json"
    answers_dir = tmp_path / "answers"
    digest_dir = tmp_path / "digests"
    report_path = tmp_path / "report.json"
    answers_dir.mkdir()
    digest_dir.mkdir()

    scenarios_path.write_text(
        json.dumps({"version": 1, "scenarios": [scenario]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (answers_dir / "subagents_tradeoff.md").write_text(
        _good_subagents_answer(),
        encoding="utf-8",
    )
    (digest_dir / "subagents_tradeoff.json").write_text(
        json.dumps(_digest_payload(scenario), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(quality_eval, "load_backend_env", lambda path: path)

    exit_code = quality_eval.main(
        [
            "--scenarios-path",
            str(scenarios_path),
            "--answers-dir",
            str(answers_dir),
            "--digest-dir",
            str(digest_dir),
            "--report-path",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["status"] == "passed"
    assert report["summary"] == {"total": 1, "passed": 1, "failed": 0, "needs_answer": 0}
    assert report["scenarios"][0]["digest_context"]["source_keys_count"] == 3


def test_main_reports_needs_answer_when_panex_answer_is_missing(tmp_path, monkeypatch):
    scenario = _scenario("subagents_tradeoff")
    scenarios_path = tmp_path / "scenarios.json"
    report_path = tmp_path / "report.json"
    scenarios_path.write_text(
        json.dumps({"version": 1, "scenarios": [scenario]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(quality_eval, "load_backend_env", lambda path: path)

    exit_code = quality_eval.main(
        [
            "--scenarios-path",
            str(scenarios_path),
            "--report-path",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["status"] == "needs_answer"
    assert report["summary"]["needs_answer"] == 1
    assert report["scenarios"][0]["critical_issues"] == ["missing_panex_answer"]


def _scenario(scenario_id: str) -> dict:
    return {
        scenario["id"]: scenario
        for scenario in quality_eval.load_scenarios(SCENARIOS_PATH)
    }[scenario_id]


def _digest_payload(scenario: dict) -> dict:
    return {
        "mode": "expert_digest",
        "query": scenario["query"],
        "selection_used": {
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov", "doronin"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_recent_only": False,
            "use_super_passport": True,
        },
        "warnings": [],
        "experts": [
            {
                "expert_id": "refat",
                "digest": {
                    "source_refs": [{"source_key": "refat:101"}],
                    "source_index": [{"source_key": "refat:101"}],
                },
            },
            {
                "expert_id": "akimov",
                "digest": {
                    "source_refs": [{"source_key": "akimov:202"}],
                    "source_index": [{"source_key": "akimov:202"}],
                },
            },
            {
                "expert_id": "doronin",
                "digest": {
                    "source_refs": [{"source_key": "doronin:303"}],
                    "source_index": [{"source_key": "doronin:303"}],
                },
            },
        ],
    }


def _source_expand_payload() -> dict:
    return {
        "mode": "source_expand",
        "sources": [
            {"source_key": "refat:238", "expert_id": "refat"},
            {"source_key": "doronin:1066", "expert_id": "doronin"},
        ],
        "not_found": [],
        "warnings": [],
    }


def _good_subagents_answer() -> str:
    return """
**Query and selection**

- query_sent: Когда стоит использовать subagents, а когда они только усложняют систему?
- experts_sent: refat, akimov, doronin
- response_mode: expert_digest
- target: https://experts-panel.fly.dev/api/v1/agent/context
- warnings: none

Короткий вывод: по этим источникам subagents выглядят полезны не как мода,
а как способ отделить разные типы работы, когда один контекст начинает мешать
решению. Это именно source-backed signals, а не доказательство: у нас мнения
практиков и выбранные посты, поэтому сильные формулировки лучше держать мягкими.

Когда помогают: если задача распадается на разные роли, например исследователь,
ревьюер и исполнитель; если нужно параллельно проверить гипотезы; если важен
чистый контекст без смешивания планирования и кодинга. Этот сигнал виден в
refat:101 и частично поддержан akimov:202.

Когда мешают: если задача маленькая, однофайловая или требует одной короткой
правки, отдельный агент добавляет latency, стоимость и coordination overhead.
По doronin:303 это скорее критерий осторожности: subagent не должен заменять
понятный основной поток.

Практическое правило выбора: заводить subagent, если есть отдельный вопрос,
отдельная зона ответственности и понятный результат. Не заводить, если
результат проще получить в основном контексте. Если нужно углубиться, я бы
раскрыл source_expand по refat:101 и doronin:303, особенно комментарии, чтобы
проверить нюансы и ограничения.
"""


def _good_source_expand_answer() -> str:
    return """
**Request passport**

- source_keys_sent: refat:238, doronin:1066
- target: https://experts-panel.fly.dev/api/v1/agent/context/expand
- mode: source_expand
- warnings: none

**Evidence Note**

- refat:238: в источнике видно не доказательство, а практический сигнал:
  автор уточняет, почему исходный тезис нельзя читать слишком широко. Комментарии
  добавляют нюанс, но не превращают это в сильный факт.
- doronin:1066: источник поддерживает осторожную интерпретацию и показывает
  ограничение: часть вывода зависит от контекста задачи. Комментарии скорее
  уточняют оговорку, чем дают новый самостоятельный вывод.
- По этим двум источникам прежний digest скорее подтверждается, но его стоит
  читать мягко: это practitioner-opinion evidence, а не ground-truth oracle.
  Следующий шаг нужен только если хочется раскрыть raw text или внешние ссылки.
"""
