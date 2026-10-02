"""Bounded, query-aware excerpts and source-local evidence validation.

This module only selects text already retrieved by Reddit Search. It neither
fetches sources nor treats lexical relevance as proof of answerability.
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any

RERANK_CONTEXT_CHAR_BUDGET = 3600
PASSAGE_CHARS = 650
MAX_COMMENTS = 300
MAX_DEPTH = 8
_STOPWORDS = frozenset(
    "a an and are as at be been but by can do does for from had has have how "
    "i if in into is it its me my of on or our that the their them there these "
    "they this to use using was we were what when where which who why will with "
    "would you your please find people users reddit actual specific practical "
    "reports report examples evidence question".split()
)


def normalize_evidence(text: str) -> str:
    """Allow HTML/Unicode/whitespace differences, never paraphrases."""
    return " ".join(unicodedata.normalize("NFC", html.unescape(text)).split())


def _terms(text: str) -> set[str]:
    return {
        word.strip(".-")
        for word in re.findall(r"[\w+#.-]{2,}", text.casefold())
        if word.strip(".-") not in _STOPWORDS and len(word.strip(".-")) > 1
    }


@dataclass(frozen=True)
class EvidencePassage:
    key: str
    text: str
    parent: str | None = None

    def render(self) -> str:
        relation = f"; reply to {self.parent}" if self.parent else ""
        return f"[{self.key}{relation}] {self.text}"


def _windows(text: str) -> list[str]:
    """Overlapping source substrings keep later fixes and local negations."""
    # Keep indentation and line breaks for configs/code. Whitespace is
    # normalized only when checking the returned quotation.
    text = unicodedata.normalize("NFC", html.unescape(text)).strip()[:100_000]
    if not text:
        return []
    return [text[start : start + PASSAGE_CHARS]
            for start in range(0, len(text), PASSAGE_CHARS - 150)]


def select_evidence_passages(
    post: Any, query: str, *, budget: int = RERANK_CONTEXT_CHAR_BUDGET
) -> list[EvidencePassage]:
    """Keep opening context plus relevant body/comment windows and replies.

    Parents and direct replies accompany a selected comment when they fit.
    No upvote sorting: a low-score answer can be more useful than a popular
    opening remark. IDs refer to positions in this retrieved thread only.
    """
    candidates: list[EvidencePassage] = []
    body = getattr(post, "full_content", None) or getattr(post, "selftext", "")
    body_windows = _windows(body or "")
    candidates.extend(EvidencePassage(f"body:{i}", text)
                      for i, text in enumerate(body_windows))
    first_comments: dict[str, EvidencePassage] = {}
    children: dict[str, list[str]] = {}
    visited = 0

    def walk(comments: list, prefix: str = "", depth: int = 0) -> None:
        nonlocal visited
        if depth > MAX_DEPTH:
            return
        for i, comment in enumerate(comments):
            if visited >= MAX_COMMENTS:
                return
            visited += 1
            if not isinstance(comment, dict):
                continue
            path = f"{prefix}.{i}" if prefix else str(i)
            key = f"comment:{path}"
            parent = f"comment:{prefix}" if prefix else None
            windows = _windows(comment.get("body") or comment.get("text") or "")
            if windows:
                first_comments[key] = EvidencePassage(key, windows[0], parent)
                for index, text in enumerate(windows):
                    candidates.append(EvidencePassage(f"{key}:{index}", text, parent))
                if parent:
                    children.setdefault(parent, []).append(key)
            replies = comment.get("replies")
            if isinstance(replies, list):
                walk(replies, path, depth + 1)

    walk(getattr(post, "top_comments", None) or [])
    query_terms = _terms(query)
    token_sets = [_terms(p.text) for p in candidates]
    counts = Counter(term for terms in token_sets for term in terms)
    weights = {term: 1 + math.log((len(candidates) + 1) / (counts[term] + 1))
               for term in query_terms}

    def relevance(passage: EvidencePassage) -> float:
        terms = _terms(passage.text)
        score = sum(weights[t] for t in query_terms & terms)
        # Short replies like "No, this broke on macOS" need the topic of
        # their parent to compete with keyword-rich top-level comments.
        parent = first_comments.get(passage.parent or "")
        if parent:
            score += 0.25 * sum(weights[t] for t in query_terms & _terms(parent.text))
        return score

    ranked = sorted(candidates, key=relevance, reverse=True)
    selected: list[EvidencePassage] = []
    seen: set[str] = set()
    used = 0

    def add(passage: EvidencePassage) -> bool:
        nonlocal used
        if not passage.text or passage.key in seen:
            return False
        if any(passage.text in other.text for other in selected):
            return False
        cost = len(passage.render()) + 1
        if used + cost > budget:
            return False
        selected.append(passage)
        seen.add(passage.key)
        used += cost
        return True

    add(EvidencePassage("title", normalize_evidence(post.title or "")[:400]))
    if body_windows:
        add(EvidencePassage("opening", body_windows[0][:240]))
    # Preserve the old opening-comment visibility as a small fallback.
    # Elliptical answers ("Disable that checkbox") often repeat no query
    # terms and must not disappear behind keyword-rich body windows.
    for key in ("comment:0", "comment:1"):
        comment = first_comments.get(key)
        if comment:
            add(EvidencePassage(key, comment.text[:220], comment.parent))

    for passage in ranked:
        parent = first_comments.get(passage.parent or "")
        companions: list[EvidencePassage] = []
        if parent:
            companions.append(EvidencePassage(parent.key, parent.text[:260], parent.parent))
        if passage.key.startswith("comment:"):
            root_key = passage.key.rsplit(":", 1)[0]
            # Preserve up to two direct responses, including contrary
            # evidence, instead of presenting a suggestion in isolation.
            for child_key in children.get(root_key, [])[:2]:
                child = first_comments[child_key]
                companions.append(EvidencePassage(child.key, child.text[:350], child.parent))
        needed = sum(len(p.render()) + 1 for p in [passage, *companions]
                     if p.key not in seen)
        if used + needed > budget:
            continue
        if parent and companions:
            add(companions.pop(0))
        add(passage)
        for companion in companions:
            add(companion)

    return selected


def match_evidence(
    evidence: Any, passages: list[EvidencePassage], source_key: Any = None
) -> EvidencePassage | None:
    """Verify one quote in one shown passage of the current post."""
    if not isinstance(evidence, str):
        return None
    quote = normalize_evidence(evidence)
    if not quote or len(quote) > 300:
        return None
    if source_key is not None and not isinstance(source_key, str):
        return None
    for passage in passages:
        if source_key is not None and source_key != passage.key:
            continue
        if quote in normalize_evidence(passage.text):
            return passage
    return None
