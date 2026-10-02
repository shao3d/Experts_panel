"""Render only the answer scope declared by the Reddit synthesis model.

Scope assessment is semantic and remains the model's responsibility. This
boundary guarantees that an insufficient/partial assessment cannot carry an
unrestricted answer or action plan through extra response fields.
"""

import json
import re


class SynthesisContractError(ValueError):
    """Unusable model output, distinct from a valid evidence abstention."""


def abstention(language: str) -> str:
    return (
        "Релевантных обсуждений на Reddit по этой конкретной теме не найдено."
        if language == "Russian"
        else "No relevant Reddit discussions found for this specific topic."
    )


def render_synthesis(raw: str, language: str, source_count: int) -> str:
    """Validate one JSON assessment and render a bounded, cited answer."""
    text = raw.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SynthesisContractError("Synthesis is not valid JSON") from exc
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("coverage"), str)
        or data.get("coverage")
        not in {
            "sufficient",
            "partial",
            "insufficient",
        }
    ):
        raise SynthesisContractError("Missing valid coverage assessment")
    coverage = data["coverage"]
    if coverage == "insufficient":
        # Intentionally ignore any generated answer, findings or actions.
        return abstention(language)

    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 8:
        raise SynthesisContractError("Missing question requirements")
    missing = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise SynthesisContractError("Invalid question requirement")
        name, supported = requirement.get("requirement"), requirement.get("supported")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 300
            or type(supported) is not bool
        ):
            raise SynthesisContractError("Invalid requirement assessment")
        if not supported:
            missing.append(" ".join(name.split()))
    if len(missing) == len(requirements):
        return abstention(language)

    gap = data.get("gap")
    if not isinstance(gap, str) or len(gap) > 800:
        raise SynthesisContractError("Invalid evidence gap")
    gap = " ".join(gap.split())
    if missing:
        coverage = "partial"
        missing_notice = (
            "Не подтверждено источниками: "
            if language == "Russian"
            else "Not established by the sources: "
        ) + "; ".join(missing)
        gap = missing_notice + (". " + gap if gap else "")
    if coverage == "partial" and not gap:
        raise SynthesisContractError("Partial coverage requires an evidence gap")
    # A model cannot declare complete coverage while also declaring a gap.
    if gap:
        coverage = "partial"

    def entries(value, limit):
        if not isinstance(value, list) or len(value) > 8:
            raise SynthesisContractError("Invalid findings/actions list")
        rendered = []
        for entry in value[:limit]:
            if not isinstance(entry, dict):
                raise SynthesisContractError("Invalid finding")
            claim, sources = entry.get("text"), entry.get("sources")
            kind = entry.get("kind")
            if not isinstance(kind, str) or kind not in {
                "reported",
                "suggested",
                "transferable",
            }:
                raise SynthesisContractError("Missing evidence type")
            if not isinstance(claim, str) or not claim.strip() or len(claim) > 1600:
                raise SynthesisContractError("Invalid finding text")
            if (
                not isinstance(sources, list)
                or not sources
                or any(
                    type(i) is not int or not 1 <= i <= source_count for i in sources
                )
            ):
                raise SynthesisContractError("Finding references an unavailable source")
            # Citation numbers come only from validated structured source IDs.
            claim = re.sub(r"\[S\d+(?:\s*,\s*S\d+)*\]", "", claim, flags=re.I).strip()
            if coverage == "partial":
                if len(claim) > 600:
                    raise SynthesisContractError("Partial finding exceeds its budget")
                claim = " ".join(claim.split())
            labels = {
                "reported": "Из обсуждения" if language == "Russian" else "Reported",
                "suggested": "Предложенный совет, не результат теста"
                if language == "Russian"
                else "Suggestion, not a test result",
                "transferable": "Опыт другого контекста, применимость не проверена"
                if language == "Russian"
                else "Other-context experience; applicability untested",
            }
            refs = " ".join(f"[S{i}]" for i in dict.fromkeys(sources))
            rendered.append(f"- **{labels[kind]}:** {claim} {refs}")
        return rendered

    findings = entries(data.get("findings"), 3 if coverage == "partial" else 8)
    if not findings:
        raise SynthesisContractError("Non-abstaining synthesis requires findings")
    if coverage == "partial":
        # No actions, summary or free-form answer are rendered on this branch.
        intro = (
            "**Данных достаточно только для частичного ответа.**"
            if language == "Russian"
            else "**The evidence supports only a partial answer.**"
        )
        return "\n\n".join([intro, gap, "\n".join(findings)])

    actions = entries(data.get("actions", []), 4)
    parts = []
    if actions:
        parts.append(
            (
                "**Что можно сделать по этим обсуждениям**"
                if language == "Russian"
                else "**Actions supported by these discussions**"
            )
            + "\n\n"
            + "\n".join(actions)
        )
    parts.append(
        (
            "**Что сообщают источники**"
            if language == "Russian"
            else "**What the sources report**"
        )
        + "\n\n"
        + "\n".join(findings)
    )
    return "\n\n".join(parts)
