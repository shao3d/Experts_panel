"""Canonical author identity for VideoHub segments.

The same YouTube channel may be labelled differently in different ingests
(for example ``JOEY`` vs ``JOEY (noisygroup)``).  The corpus then splits one
author into two catalog entries, the generated index grows two sections, and
"latest video by author" checks start to lie.

This module keeps a single alias -> canonical map.  Both the importer and the
one-off migration script use it, so new ingests land canonically and old rows
can be repaired with the same rules.

The map is keyed by the *slugified* author id the importer already computes
(``author_id``), because that id is what lives in ``media_metadata``.
"""

from __future__ import annotations

# alias author_id -> (canonical display name, canonical author id)
_CANONICAL_BY_ID: dict[str, tuple[str, str]] = {
    "joey": ("JOEY (noisygroup)", "joey_noisygroup"),
}

# Channel-level facts worth keeping next to the map: the display name is
# ambiguous, the YouTube channel id is not.
CANONICAL_CHANNEL_IDS: dict[str, str] = {
    "UCG0sRL6J1x62Y-FQTrJmP1w": "joey_noisygroup",
}


def canonical_author_by_id(author_id: str | None) -> tuple[str, str] | None:
    """Return ``(display_name, author_id)`` for a known alias, else ``None``."""
    if not author_id:
        return None
    return _CANONICAL_BY_ID.get(author_id.strip().lower())


def canonical_author(name: str, author_id: str | None = None) -> tuple[str, str]:
    """Return the canonical ``(display_name, author_id)`` for a raw label."""
    resolved = canonical_author_by_id(author_id)
    if resolved:
        return resolved
    return name, (author_id or "")
