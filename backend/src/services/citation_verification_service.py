"""Citation verification: check answer claims against their cited sources.

After Reduce produces the answer with ``[post:ID]`` citations, every claim
(a sentence containing at least one citation) is checked against the text of
the posts it cites:

1. Deterministic lexical layer: normalized token containment between the
   claim and the source text. Fast, explainable, language-local.
2. Optional LLM layer (``MODEL_ANALYSIS``): one batched call judges all
   claim/source pairs and may override the lexical verdict either way.

Fail-open by design: any error yields ``None`` and the UI simply does not
render the verification badge. Verdicts are keyed by ``telegram_message_id``,
so they stay valid for the RU/EN translation the user actually sees —
translation preserves ``[post:ID]`` markers.

This is a trust signal with methodology (``verified_count``/``total_count``),
not a stamp of truth: the report always shows how many citations were checked
and how many passed.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .. import config
from ..utils.llm_json import parse_llm_json
from .vertex_llm_client import get_vertex_llm_client

logger = logging.getLogger(__name__)

# Citation markers as produced by Reduce and accepted by the frontend:
# single "[post:123]" and multi "[post:1, post:2]" / "[1, 2]" formats.
# Markdown links like "[text](url)" never match (digits only inside brackets).
CITATION_RE = re.compile(
    r"\[((?:post:\s*\d+|\d+)(?:\s*,\s*(?:post:\s*\d+|\d+))*)\]"
)

# Claim granularity: a line of the markdown answer (paragraph/bullet/table
# row) is the smallest unit that still reads as a statement. Splitting
# markdown lines into raw sentences corrupts bullets and tables.
_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")

_VERDICT_SUPPORTED = "supported"
_VERDICT_PARTIAL = "partial"
_VERDICT_UNSUPPORTED = "unsupported"
_VERDICT_UNVERIFIED = "unverified"

# Share of the claim's informative tokens that must appear in the source
# text for the lexical layer to call it supported / partial.
_LEXICAL_SUPPORTED_THRESHOLD = 0.6
_LEXICAL_PARTIAL_THRESHOLD = 0.3

# Common RU/EN function words that carry no evidence value.
_STOPWORDS = frozenset(
    """
    и в во не что он на я с со как а то все она так его но да ты к у же вы
    за бы по только ее мне было вот от меня еще нет о из ему теперь когда
    даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам
    сказал ведь там потом себя ничего ей может они тут где есть надо ней для
    мы тебя их чем была сам чтоб без будто человек чего раз тоже себе под
    жизнь будет ж тогда кто этот говорил того потому этого какой совсем ним
    здесь этом один почти мой тем чтобы нее кажется сейчас были куда зачем
    say all can said just like when more one about into over than them these
    there what with your from this that have will been they are was were
    which their would there could should about other some more very
    """.split()
)


def extract_citation_claims(answer: str) -> List[Dict[str, Any]]:
    """Split the answer into claims: text fragments citing one or more posts.

    Returns a list of ``{"text": str, "post_ids": [int]}`` — the citation
    markers are stripped from the claim text.
    """
    claims: List[Dict[str, Any]] = []
    if not answer:
        return claims

    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for sentence in _CLAIM_SPLIT_RE.split(line):
            post_ids = [
                int(number)
                for match in CITATION_RE.finditer(sentence)
                for number in re.findall(r"\d+", match.group(1))
            ]
            if not post_ids:
                continue
            text = CITATION_RE.sub("", sentence).strip(" \t-*#|")
            if len(text.strip(" .,;:!?-")) < 10:
                # A bare citation with no statement behind it has nothing to
                # verify; skipping keeps the report about real claims.
                continue
            claims.append({"text": text, "post_ids": sorted(set(post_ids))})

    return claims


def _light_stem(token: str) -> str:
    """Cheap RU/EN suffix strip so flexions collapse to one token.

    Not a real stemmer: just enough for containment scoring, where
    'пайплайна/пайплайн' or 'базы/базе' should hit the same stem.
    """
    if len(token) > 4 and re.match(r"^[а-яё]+$", token) and token[-1] in "аеиоуыэюяйь":
        return token[:-1]
    if len(token) > 3 and re.match(r"^[a-z]+$", token) and token.endswith("s"):
        return token[:-1]
    return token


def _normalize_tokens(text: str) -> List[str]:
    """Lowercase, strip punctuation, drop stopwords and 1-char tokens."""
    tokens = re.findall(r"[\wа-яё-]+", text.lower(), re.UNICODE)
    return [
        _light_stem(token)
        for token in tokens
        if len(token) > 1 and token not in _STOPWORDS and not token.startswith("-")
    ]


def _lexical_containment(claim_text: str, source_text: str) -> float:
    """Share of the claim's informative tokens present in the source text."""
    claim_tokens = _normalize_tokens(claim_text)
    if not claim_tokens:
        return 0.0
    source_tokens = set(_normalize_tokens(source_text))
    hits = sum(1 for token in claim_tokens if token in source_tokens)
    return hits / len(claim_tokens)


# Source-word spans grouped into one highlight cluster must be no further
# apart than this; otherwise they read as unrelated passages.
_EVIDENCE_CLUSTER_GAP_CHARS = 120


def _lexical_evidence(
    claim_text: str, source_text: str
) -> Optional[Dict[str, Any]]:
    """Locate the author's words behind a claim inside the source text.

    Returns ``{"start", "end", "text", "matched_terms"}`` — the tightest
    cluster of source words that match the claim's tokens — or None when no
    claim token appears in the source. The fragment is a plain substring of
    the source text, so the frontend can anchor it with a simple search.
    """
    claim_stems = set(_normalize_tokens(claim_text))
    if not claim_stems:
        return None

    lowered = source_text.lower()
    matched_spans: List[tuple] = []
    matched_terms: List[str] = []
    for match in re.finditer(r"[\wа-яё-]+", lowered):
        token = match.group(0)
        if len(token) <= 1:
            continue
        stemmed = _light_stem(token)
        if stemmed in claim_stems:
            matched_spans.append((match.start(), match.end()))
            matched_terms.append(token)

    if not matched_spans:
        return None

    # Group spans into clusters by gap size; keep the densest cluster
    # (ties go to the earliest) so the highlight reads as one passage.
    clusters: List[List[tuple]] = [[matched_spans[0]]]
    for span in matched_spans[1:]:
        if span[0] - clusters[-1][-1][1] <= _EVIDENCE_CLUSTER_GAP_CHARS:
            clusters[-1].append(span)
        else:
            clusters.append([span])

    def cluster_weight(cluster: List[tuple]) -> tuple:
        return (len(cluster), -cluster[0][0])

    best = max(clusters, key=cluster_weight)
    start = min(span[0] for span in best)
    end = max(span[1] for span in best)
    return {
        "start": start,
        "end": end,
        "text": source_text[start:end],
        "matched_terms": sorted(set(matched_terms)),
    }


class CitationVerificationService:
    """Verifies that answer claims are supported by their cited sources."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or config.MODEL_ANALYSIS
        self.llm_client = None
        try:
            self.llm_client = get_vertex_llm_client()
        except Exception as e:
            logger.warning(f"CitationVerificationService: LLM client unavailable: {e}")

    async def verify(
        self,
        answer: str,
        posts_by_id: Dict[int, str],
        expert_id: str = "unknown",
    ) -> Optional[Dict[str, Any]]:
        """Verify citations and return a report dict, or None (fail-open).

        The returned dict matches ``CitationVerificationReport`` in
        ``api/models.py``: total/verified/partial counts, a per-citation
        verdict map keyed by string message id, and the method used.
        """
        if not config.CITATION_VERIFICATION_ENABLED:
            return None

        claims = extract_citation_claims(answer)
        if not claims or not posts_by_id:
            return None

        # Claim/source pairs, capped so one verbose answer cannot explode
        # the judge prompt or the latency budget.
        pairs: List[Dict[str, Any]] = []
        for claim_index, claim in enumerate(claims):
            for post_id in claim["post_ids"]:
                if len(pairs) >= config.CITATION_VERIFICATION_MAX_PAIRS:
                    break
                source_text = posts_by_id.get(post_id)
                if source_text is None:
                    pairs.append(
                        {
                            "claim_index": claim_index,
                            "post_id": post_id,
                            "claim_text": claim["text"],
                            "source_text": None,
                        }
                    )
                    continue
                pairs.append(
                    {
                        "claim_index": claim_index,
                        "post_id": post_id,
                        "claim_text": claim["text"],
                        "source_text": source_text[
                            : config.CITATION_VERIFICATION_SOURCE_CHAR_CAP
                        ],
                    }
                )
            if len(pairs) >= config.CITATION_VERIFICATION_MAX_PAIRS:
                break

        verdicts: Dict[int, str] = {}
        lexical_scores: Dict[int, float] = {}
        lexical_evidence: Dict[int, Optional[Dict[str, Any]]] = {}
        for pair in pairs:
            pair_key = (pair["claim_index"], pair["post_id"])
            if pair["source_text"] is None:
                verdicts[pair_key] = _VERDICT_UNVERIFIED
                lexical_evidence[pair_key] = None
                continue
            score = _lexical_containment(pair["claim_text"], pair["source_text"])
            lexical_scores[pair_key] = score
            lexical_evidence[pair_key] = _lexical_evidence(
                pair["claim_text"], pair["source_text"]
            )
            if score >= _LEXICAL_SUPPORTED_THRESHOLD:
                verdicts[pair_key] = _VERDICT_SUPPORTED
            elif score >= _LEXICAL_PARTIAL_THRESHOLD:
                verdicts[pair_key] = _VERDICT_PARTIAL
            else:
                verdicts[pair_key] = _VERDICT_UNSUPPORTED

        method = "lexical"
        if config.CITATION_VERIFICATION_USE_LLM and self.llm_client:
            llm_verdicts = await self._judge_with_llm(pairs, expert_id)
            if llm_verdicts:
                method = "lexical+llm"
                for pair in pairs:
                    pair_key = (pair["claim_index"], pair["post_id"])
                    if pair_key in llm_verdicts:
                        verdicts[pair_key] = llm_verdicts[pair_key]

        verdict_by_id: Dict[str, str] = {}
        for (claim_index, post_id), verdict in verdicts.items():
            # The same post may be cited by several claims: the weakest
            # verdict wins, so the report never overstates support.
            existing = verdict_by_id.get(str(post_id))
            if existing is None or _verdict_rank(verdict) < _verdict_rank(existing):
                verdict_by_id[str(post_id)] = verdict

        # Evidence per post: the fragment from the pair with the strongest
        # lexical support (the clearest word-level anchor found in the post).
        evidence_by_id: Dict[str, Dict[str, Any]] = {}
        best_pair: Dict[str, tuple] = {}
        for pair_key, score in lexical_scores.items():
            post_id_str = str(pair_key[1])
            if lexical_evidence.get(pair_key) is None:
                continue
            current = best_pair.get(post_id_str)
            if current is None or score > current[0]:
                best_pair[post_id_str] = (score, pair_key)
        for post_id_str, (_, pair_key) in best_pair.items():
            evidence = lexical_evidence.get(pair_key)
            if evidence is not None:
                evidence_by_id[post_id_str] = evidence

        report = {
            "total_count": len(verdict_by_id),
            "verified_count": sum(
                1 for v in verdict_by_id.values() if v == _VERDICT_SUPPORTED
            ),
            "partial_count": sum(
                1 for v in verdict_by_id.values() if v == _VERDICT_PARTIAL
            ),
            "unsupported_count": sum(
                1 for v in verdict_by_id.values() if v == _VERDICT_UNSUPPORTED
            ),
            "verdicts": verdict_by_id,
            "evidence": evidence_by_id,
            "method": method,
        }
        logger.info(
            f"[{expert_id}] Citation verification: "
            f"{report['verified_count']}/{report['total_count']} supported, "
            f"{report['partial_count']} partial, "
            f"{report['unsupported_count']} unsupported ({method})"
        )
        return report

    async def _judge_with_llm(
        self, pairs: List[Dict[str, Any]], expert_id: str
    ) -> Optional[Dict[tuple, str]]:
        """One batched LLM call over all claim/source pairs; None on failure."""
        try:
            blocks = []
            for index, pair in enumerate(pairs, start=1):
                if pair["source_text"] is None:
                    continue
                blocks.append(
                    f"[{index}] CLAIM: {pair['claim_text']}\n"
                    f"    SOURCE [post:{pair['post_id']}]: {pair['source_text']}"
                )
            if not blocks:
                return None

            prompt = (
                "You are a strict citation checker. For every CLAIM/SOURCE pair "
                "decide whether the source text supports the claim.\n"
                "Rules:\n"
                "- supported: the source directly states or clearly entails the claim.\n"
                "- partial: the source supports part of the claim or supports it "
                "indirectly.\n"
                "- unsupported: the substance of the claim is absent from the source.\n"
                "- Judge substance, not wording; numbers must actually appear in "
                "the source.\n"
                "- The claim and the source may be in Russian or English; judge "
                "the meaning across languages.\n"
                'Respond with JSON only: {"verdicts": [{"pair": <number>, '
                '"verdict": "supported|partial|unsupported"}]}\n\n'
                "PAIRS:\n" + "\n\n".join(blocks)
            )

            response = await self.llm_client.chat_completions_create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2048,
            )
            if (
                not response
                or not hasattr(response, "choices")
                or len(response.choices) == 0
            ):
                return None
            raw_content = response.choices[0].message.content
            parsed = parse_llm_json(raw_content, context="citation_verification")
            entries = parsed.get("verdicts") if isinstance(parsed, dict) else None
            if not isinstance(entries, list):
                return None

            result: Dict[tuple, str] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                pair_number = entry.get("pair")
                verdict = entry.get("verdict")
                if (
                    not isinstance(pair_number, int)
                    or pair_number < 1
                    or pair_number > len(pairs)
                    or verdict not in (_VERDICT_SUPPORTED, _VERDICT_PARTIAL, _VERDICT_UNSUPPORTED)
                ):
                    continue
                pair = pairs[pair_number - 1]
                result[(pair["claim_index"], pair["post_id"])] = verdict
            return result
        except Exception as e:
            logger.warning(
                f"[{expert_id}] Citation LLM judge failed, keeping lexical "
                f"verdicts: {e}"
            )
            return None


def _verdict_rank(verdict: str) -> int:
    """Lower rank = weaker support; used to keep the worst verdict per post."""
    return {
        _VERDICT_SUPPORTED: 3,
        _VERDICT_PARTIAL: 2,
        _VERDICT_UNVERIFIED: 1,
        _VERDICT_UNSUPPORTED: 0,
    }.get(verdict, 0)
