"""Canonical expert group map for Agent Context and Expert Scout.

Single source of truth for group-based expert selection. Imported by the
Agent Context API endpoint (`src.api.agent_context_endpoint`) and by the
read-only Expert Scout helper (`backend/scripts/expert_scout.py`) so that
adding or moving an expert inside a group requires editing this map only.
"""

from __future__ import annotations


AGENT_CONTEXT_EXPERT_GROUPS: dict[str, list[str]] = {
    "tech": [
        "ai_architect",
        "neuraldeep",
        "ilia_izmailov",
        "polyakov",
        "etechlead",
        "glebkudr",
        "ostrikov",
        "pashazloy",
    ],
    "tech_business": [
        "ai_grabli",
        "refat",
        "akimov",
        "llm_under_hood",
        "elkornacio",
        "doronin",
        "air_ai",
        "silicbag",
        "kornish",
    ],
    "visual": [
        "strangedalle",
        "acidcrunch",
        "cgevent",
    ],
}


def resolve_expert_group(name: str) -> list[str]:
    """Return expert ids for a known group name.

    Raises `KeyError` for an unknown group so callers can return an actionable
    error instead of silently searching nothing.
    """
    return list(AGENT_CONTEXT_EXPERT_GROUPS[name])


def groups_for_expert(expert_id: str) -> list[str]:
    """Return the group names that contain `expert_id` (stable order)."""
    return [
        group
        for group, expert_ids in AGENT_CONTEXT_EXPERT_GROUPS.items()
        if expert_id in expert_ids
    ]
