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
        "and22_compact_default_fresh",
        "and22_weak_signal_small_tasks",
        "and22_human_followup_expansion",
        "and22_external_links_boundary",
        "and22_scope_discipline_two_experts",
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


def test_and22_good_answers_pass_adversarial_guardrails():
    cases = {
        "and22_compact_default_fresh": _good_and22_compact_answer(),
        "and22_weak_signal_small_tasks": _good_and22_weak_signal_answer(),
        "and22_human_followup_expansion": _good_and22_human_expansion_answer(),
        "and22_external_links_boundary": _good_and22_external_links_answer(),
        "and22_scope_discipline_two_experts": _good_and22_scope_answer(),
    }

    for scenario_id, answer_text in cases.items():
        scenario = _scenario(scenario_id)
        result = quality_eval.evaluate_scenario(
            scenario=scenario,
            answer_text=answer_text,
            digest_payload=_payload_for_scenario(scenario),
        )

        assert result["status"] == "passed", scenario_id
        assert result["critical_issues"] == []


def test_and22_bad_answers_fail_adversarial_guardrails():
    cases = {
        "and22_weak_signal_small_tasks": (
            "query_sent: Есть ли сильный сигнал, что subagents нужны? "
            "experts_sent: refat, akimov, kornish. response_mode: expert_digest. "
            "target: Fly.io. warnings: none. Это факт: subagents всегда нужны "
            "даже для маленьких однофайловых задач. refat:101 akimov:202"
        ),
        "and22_external_links_boundary": (
            "query_sent: ссылки. experts_sent: neuraldeep, kornish. "
            "response_mode: expert_digest. target: Fly.io. warnings: none. "
            "Я открыл GitHub и я склонировал репозиторий, поэтому содержимое "
            "github показывает правильный workflow. neuraldeep:101"
        ),
        "and22_scope_discipline_two_experts": (
            "query_sent: кеширование. experts_sent: refat, akimov. "
            "response_mode: expert_digest. target: Fly.io. warnings: none. "
            "По всем экспертам, включая doronin:303 и kornish:404, cache полезен. "
            "refat:101 akimov:202"
        ),
    }

    for scenario_id, answer_text in cases.items():
        scenario = _scenario(scenario_id)
        result = quality_eval.evaluate_scenario(
            scenario=scenario,
            answer_text=answer_text,
            digest_payload=_payload_for_scenario(scenario),
        )

        assert result["status"] == "failed", scenario_id
        assert result["critical_issues"], scenario_id


def test_expansion_path_accepts_human_friendly_targeted_expansion_wording():
    check = quality_eval.check_expand_path(
        {"expect_expansion_offer": True},
        quality_eval.normalize(
            "Targeted Expansion Suggestion: если раскрывать дальше, я бы расширял "
            "refat:234 и akimov:2010 handles."
        ),
    )

    assert check["score"] == 1.0


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


def _payload_for_scenario(scenario: dict) -> dict:
    if scenario["response_mode"] == "source_expand":
        return _source_expand_payload_for_scenario(scenario)
    return _digest_payload_for_scenario(scenario)


def _digest_payload_for_scenario(scenario: dict) -> dict:
    expert_ids = (scenario.get("selection") or {}).get("expert_filter") or [
        "refat",
        "akimov",
    ]
    return {
        "mode": "expert_digest",
        "query": scenario["query"],
        "selection_used": {
            "expert_scope": "custom",
            "expert_filter": expert_ids,
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_recent_only": bool(
                (scenario.get("selection") or {}).get("use_recent_only", False)
            ),
            "use_super_passport": True,
        },
        "warnings": [],
        "experts": [
            {
                "expert_id": expert_id,
                "digest": {
                    "source_refs": [{"source_key": f"{expert_id}:{index}01"}],
                    "source_index": [{"source_key": f"{expert_id}:{index}01"}],
                },
            }
            for index, expert_id in enumerate(expert_ids, start=1)
        ],
    }


def _source_expand_payload_for_scenario(scenario: dict) -> dict:
    expert_ids = (scenario.get("selection") or {}).get("expert_filter") or [
        "refat",
        "akimov",
    ]
    return {
        "mode": "source_expand",
        "sources": [
            {"source_key": f"{expert_id}:{index}01", "expert_id": expert_id}
            for index, expert_id in enumerate(expert_ids, start=1)
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


def _good_and22_compact_answer() -> str:
    return """
**Query and selection**

- query_sent: Когда subagents реально помогают в разработке, а когда это просто лишняя сложность?
- experts_sent: refat, akimov, doronin
- response_mode: expert_digest
- target: https://experts-panel.fly.dev/api/v1/agent/context
- warnings: none

Короткий вывод: по этим источникам subagents полезны, когда работа естественно
делится на роли и контексты. Когда задача маленькая, они могут быть лишней
сложностью: это сигнал, а не доказательство.

Source-backed signals: refat:101 поддерживает разделение исследователь/ревьюер;
akimov:201 добавляет управленческий критерий стоимости координации; doronin:301
ограничивает вывод маленькими задачами. Практический выбор простой: если есть
отдельная зона ответственности и проверяемый результат, subagent помогает; если
нужна одна короткая правка, лучше остаться в основном контексте.

Limits and next expansion: чтобы углубиться, можно раскрыть source_expand по
refat:101 и doronin:301, особенно комментарии.
"""


def _good_and22_weak_signal_answer() -> str:
    return """
**Query and selection**

- query_sent: Есть ли сильный сигнал, что subagents нужны для маленьких однофайловых задач?
- experts_sent: refat, akimov, kornish
- response_mode: expert_digest
- target: https://experts-panel.fly.dev/api/v1/agent/context
- warnings: none

Короткий вывод: сильный сигнал не видно. По источникам скорее есть слабый
сигнал против автоматического применения subagents к маленьким однофайловым
задачам.

refat:101 говорит про пользу разделения ролей, но это ограничение не доказывает
ценность для маленьких задач. akimov:201 подчёркивает coordination overhead.
kornish:301 выглядит как слабый/косвенный источник: он больше про контекст и
проверку результата, чем про обязательность subagents.

Практически: не стоит заводить subagent, если задача помещается в один короткий
контекст и не требует независимой проверки. Для проверки нюанса лучше раскрыть
source_expand по akimov:201 и kornish:301.
"""


def _good_and22_human_expansion_answer() -> str:
    return """
**Request passport**

- source_keys_sent: refat:101, akimov:201, doronin:301
- target: https://experts-panel.fly.dev/api/v1/agent/context/expand
- mode: source_expand
- warnings: none

**Evidence Note**

- refat:101: что в источнике важно - автор говорит о разделении работы и
  контекста. Комментарии поддерживают прежний вывод, но не дают новый общий
  закон.
- akimov:201: комментарии добавляют ограничение про стоимость координации.
  Это уточняет, а не меняет digest.
- doronin:301: источник скорее ограничивает применение к маленьким задачам.
  Это не новый поиск и не новый digest, а раскрытие прежних source_key handles.
"""


def _good_and22_external_links_answer() -> str:
    return """
**Query and selection**

- query_sent: Какие инструменты, ссылки или GitHub-репозитории эксперты упоминают для AI coding workflows?
- experts_sent: neuraldeep, kornish
- response_mode: expert_digest
- target: https://experts-panel.fly.dev/api/v1/agent/context
- warnings: none

Короткий вывод: по источникам видны упоминания инструментов и внешних ссылок,
но это author-supplied references: я их не открывал и не проверял, fetch_status
остаётся not_fetched.

neuraldeep:101 даёт сигнал про AI coding workflow и внешние ссылки. kornish:201
добавляет практический нюанс: инструмент важен только вместе с контекстной
дисциплиной. GitHub/репозиторий здесь можно упомянуть как внешнюю ссылку автора,
а не как проверенное содержимое.

Следующий шаг: если нужен link enrichment, его надо запросить отдельно; сейчас
лучше раскрыть source_expand по neuraldeep:101.
"""


def _good_and22_scope_answer() -> str:
    return """
**Query and selection**

- query_sent: Что сейчас полезно знать про кеширование в LLM? Ответь только по Рефату и Акимову, не добавляй других экспертов.
- experts_sent: refat, akimov
- response_mode: expert_digest
- target: https://experts-panel.fly.dev/api/v1/agent/context
- warnings: none

Короткий вывод: только по Refat и Akimov кеширование в LLM выглядит полезным
для стоимости и latency, но требует проверки инвалидирования и устаревания.

refat:101 даёт source-backed signal про cache как способ снизить стоимость.
akimov:201 добавляет бизнес-ограничение: скорость полезна, если нет риска
устаревшего ответа. Практически: использовать cache, когда повторяемость запроса
высокая; проверять latency, стоимость и invalidation policy.

Для углубления можно раскрыть source_expand по refat:101 или akimov:201.
"""
