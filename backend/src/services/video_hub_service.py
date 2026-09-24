"""Video Hub Service for deep analysis of video transcripts.

Handles segment-level semantic mapping, thread-based context expansion, 
and high-fidelity stylistic synthesis.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_none,
)

from .. import config
from ..utils.language_utils import detect_query_language
from .language_validation_service import LanguageValidationService
from .vertex_llm_client import get_vertex_llm_client

logger = logging.getLogger(__name__)

_RELEVANCE_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


class VideoMapUnavailable(Exception):
    """Map phase could not score segments after retries.

    Infrastructure failure (LLM errors, broken responses), NOT an honest
    "no relevant segments" verdict: callers must surface it as a temporary
    problem instead of the empty-result fallback.
    """


class VideoHubService:
    def __init__(
        self,
        llm_client=None,
        *,
        map_max_attempts: int = 3,
        retry_wait_min: float = 4.0,
        map_chunk_size: int | None = None,
        map_max_parallel: int | None = None,
    ):
        self.llm_client = llm_client or get_vertex_llm_client()
        self.map_model = config.MODEL_MAP
        self.synthesis_model = config.MODEL_VIDEO_PRO # gemini-3.0-pro
        self.map_max_attempts = map_max_attempts
        self.retry_wait_min = retry_wait_min
        # Score in chunks like MapService: one prompt per 50 segments keeps the
        # prompt and the scores JSON far below model limits at any corpus size.
        self.map_chunk_size = map_chunk_size if map_chunk_size is not None else config.MAP_CHUNK_SIZE
        self.map_max_parallel = map_max_parallel if map_max_parallel is not None else config.MAP_MAX_PARALLEL

    def _retrying(self) -> AsyncRetrying:
        """Three knocks with exponential backoff (same shape as MapService).

        `retry_wait_min=0` disables waiting entirely (used by tests).
        """
        wait = (
            wait_none()
            if self.retry_wait_min <= 0
            else wait_exponential(multiplier=2, min=self.retry_wait_min, max=90)
        )
        return AsyncRetrying(
            stop=stop_after_attempt(self.map_max_attempts),
            wait=wait,
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

    @staticmethod
    def _unavailable_answer(query: str) -> str:
        """Honest 'temporary problem' text in the query's language.

        Distinct from the empty-result fallback: the archive is fine, we just
        failed to read it right now — say so instead of claiming "nothing
        relevant".
        """
        if detect_query_language(query) == "Russian":
            return (
                "Видеоархив сейчас недоступен: не удалось оценить сегменты видео. "
                "Попробуйте ещё раз чуть позже."
            )
        return (
            "The video archive is temporarily unavailable: video segments could "
            "not be scored. Please try again in a moment."
        )

    async def process(
        self,
        query: str,
        video_segments: list[Any], # List of Post objects
        expert_id: str = "video_hub",
        progress_callback: Callable | None = None
    ) -> dict[str, Any]:
        """Process the 4-phase video pipeline with segment-level precision."""

        # 1. Video Map Phase (Segment-Level Scoring)
        if progress_callback:
            await progress_callback({"phase": "map", "status": "processing", "message": "🎥 Scoring video segments..."})

        try:
            scored_segments = await self._map_segments(query, video_segments)
        except VideoMapUnavailable:
            # Not an empty result: the scorer itself failed. Say "temporarily
            # unavailable" instead of lying "nothing relevant was found".
            return {
                "answer": self._unavailable_answer(query),
                "main_sources": [],
                "confidence": "LOW",
                "posts_analyzed": len(video_segments),
            }

        # Filter out only HIGH and MEDIUM
        high_segments = [s for s in scored_segments if s["relevance"] == "HIGH"]
        medium_segments = [s for s in scored_segments if s["relevance"] == "MEDIUM"]

        if not high_segments and not medium_segments:
            # Honest empty result: Map ran fine and every segment scored LOW.
            # (Map failures never reach this branch — they raise
            # VideoMapUnavailable and return the temporary-unavailable answer.)
            # Match the fallback language to the query language; the synthesis
            # phase is language-aware too, so both paths answer in the query's
            # language instead of always Russian.
            not_found = (
                "В видео-архиве не найдено достаточно релевантных сегментов для ответа на этот вопрос."
                if detect_query_language(query) == "Russian"
                else "The video archive does not contain segments relevant enough to answer this question."
            )
            return {
                "answer": not_found,
                "main_sources": [],
                "confidence": "LOW",
                "posts_analyzed": len(video_segments)
            }

        # 2. Video Resolve Phase (Semantic Thread Expansion)
        if progress_callback:
            await progress_callback({"phase": "resolve", "status": "processing", "message": "🎥 Expanding knowledge threads..."})

        thread_context = self._resolve_threads(scored_segments, video_segments)

        # 3. Video Synthesis Phase (The Digital Twin)
        if progress_callback:
            await progress_callback({"phase": "reduce", "status": "processing", "message": "🎥 Synthesizing digital twin response..."})

        answer = await self._synthesize_response(query, thread_context)

        # 4. Language Validation (Style-Preserving)
        if progress_callback:
            await progress_callback({"phase": "language_validation", "status": "processing", "message": "🎥 Style-aware translation..."})

        validator = LanguageValidationService()
        validation_result = await validator.process(answer, query, expert_id)
        final_answer = validation_result.get("answer", answer)

        return {
            "answer": final_answer,
            "main_sources": [s["telegram_message_id"] for s in thread_context],
            "confidence": "HIGH" if high_segments else "MEDIUM",
            "posts_analyzed": len(video_segments)
        }

    async def _map_segments(self, query: str, segments: list[Any]) -> list[dict[str, Any]]:
        """Score each segment individually based on its summary.

        Segments are scored in chunks (MapService-style, parallel with a
        concurrency cap) so prompt size and the scores JSON stay bounded at any
        corpus size. Each chunk retries flaky calls/broken responses on its own;
        one chunk that still fails after retries fails the whole Map honestly
        (VideoMapUnavailable) — never a silent partial score that would quietly
        drop the failed chunk's segments.
        """
        if not segments:
            return []

        chunks = [
            segments[i:i + self.map_chunk_size]
            for i in range(0, len(segments), self.map_chunk_size)
        ]
        semaphore = asyncio.Semaphore(max(1, min(self.map_max_parallel, len(chunks))))

        async def run_chunk(chunk: list[Any]) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._map_chunk(query, chunk)

        results = await asyncio.gather(
            *(run_chunk(chunk) for chunk in chunks),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            logger.error(f"Video Map failed after retries: {errors[0]}")
            raise VideoMapUnavailable(str(errors[0])) from errors[0]
        cleaned = [item for chunk_scores in results for item in chunk_scores]
        if not cleaned:
            raise VideoMapUnavailable("Video Map produced no scores")
        return cleaned

    async def _map_chunk(self, query: str, chunk: list[Any]) -> list[dict[str, Any]]:
        """Score one chunk of segments (single prompt, retried on failure)."""
        map_input = []
        for s in chunk:
            try:
                meta = json.loads(s.media_metadata) if isinstance(s.media_metadata, str) else s.media_metadata
                if not meta: meta = {}
            except Exception:
                meta = {}

            map_input.append({
                "id": s.telegram_message_id,
                "topic_id": meta.get("topic_id", "unknown"),
                "title": seg_title_from_text(s.message_text),
                "summary": seg_summary_from_text(s.message_text)
            })

        prompt = f"""You are a Video Content Scorer.
User Query: "{query}"

Task: Rate the relevance of each video segment to the query.
- HIGH: Direct answer, deep explanation, or crucial technical detail.
- MEDIUM: Related context, introductory remarks, or logical bridge.
- LOW: Unrelated, generic talk, or "noise".

Segments:
{json.dumps(map_input, ensure_ascii=False, indent=2)}

Output JSON ONLY, no explanations (keep it compact: id + relevance per segment):
{{
  "scores": [
    {{"id": 123, "relevance": "HIGH"}},
    {{"id": 456, "relevance": "LOW"}}
  ]
}}
"""
        try:
            async for attempt in self._retrying():
                with attempt:
                    response = await self.llm_client.chat_completions_create(
                        model=self.map_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        response_format={"type": "json_object"},
                        max_tokens=4096,  # Scores JSON; 402 guard
                    )
                    data = json.loads(response.choices[0].message.content)
                    cleaned = self._normalize_scores(data.get("scores", []), chunk)
                    if not cleaned:
                        # The contract scores every segment: a response with no
                        # usable scores is a broken response, so it gets retried
                        # like a crash instead of reading as "nothing relevant".
                        raise ValueError("Video Map returned no usable scores")
                    return cleaned
        except Exception as e:
            logger.error(f"Video Map chunk failed after retries: {e}")
            raise
        raise VideoMapUnavailable("Video Map chunk produced no scores")  # pragma: no cover

    @staticmethod
    def _normalize_scores(raw_scores: Any, segments: list[Any]) -> list[dict[str, Any]]:
        """Keep only well-formed scores that reference real segments, one per segment.

        The Map LLM may hallucinate IDs or drift from the contract; unknown IDs
        or relevance labels are dropped instead of poisoning Resolve/Synthesis
        (a raw check upstream would otherwise pass on phantom HIGH scores while
        the context stays empty). Duplicate scores collapse to the strongest
        relevance per segment, so HIGH/MEDIUM counts cannot be inflated.
        """
        valid_ids = {str(s.telegram_message_id) for s in segments}
        cleaned_by_id: dict[str, dict[str, Any]] = {}
        if not isinstance(raw_scores, list):
            logger.warning("Video Map: scores is %s, expected a list", type(raw_scores).__name__)
            return []
        for item in raw_scores:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if isinstance(raw_id, bool):
                continue
            if isinstance(raw_id, float) and raw_id.is_integer():
                raw_id = int(raw_id)
            if str(raw_id) not in valid_ids:
                continue
            relevance = item.get("relevance")
            if relevance not in ("HIGH", "MEDIUM", "LOW"):
                continue
            entry = {"id": raw_id, "relevance": relevance}
            existing = cleaned_by_id.get(str(raw_id))
            if existing is None or _RELEVANCE_RANK[relevance] < _RELEVANCE_RANK[existing["relevance"]]:
                cleaned_by_id[str(raw_id)] = entry
        cleaned = list(cleaned_by_id.values())
        if len(cleaned) != len(raw_scores):
            logger.warning(
                "Video Map: dropped %d/%d malformed or duplicate scores",
                len(raw_scores) - len(cleaned), len(raw_scores),
            )
        return cleaned

    def _resolve_threads(self, scored_segments: list[dict[str, Any]], all_posts: list[Any]) -> list[dict[str, Any]]:
        """
        Assemble the final context:
        1. Keep all HIGH segments (Full Text).
        2. Keep all MEDIUM segments (Summary).
        3. For every HIGH segment, find its 'siblings' in the same topic_id and include them as MEDIUM (Summary).
        """
        # Create lookup for posts and their initial scores (using strings for keys to be type-safe)
        posts_by_id = {str(p.telegram_message_id): p for p in all_posts}
        scores_by_id = {str(s["id"]): s["relevance"] for s in scored_segments}

        # Identify winning topic_ids (those having at least one HIGH segment)
        winning_topics = set()
        for s in scored_segments:
            if s["relevance"] == "HIGH":
                p = posts_by_id.get(str(s["id"]))
                if p:
                    meta = json.loads(p.media_metadata) if isinstance(p.media_metadata, str) else p.media_metadata
                    if meta.get("topic_id"):
                        winning_topics.add(meta.get("topic_id"))

        final_context_map = {} # id -> context_item

        for p_id_str, post in posts_by_id.items():
            meta = json.loads(post.media_metadata) if isinstance(post.media_metadata, str) else post.media_metadata
            t_id = meta.get("topic_id")
            initial_rel = scores_by_id.get(p_id_str, "LOW")

            # Decision Logic:
            # Case A: Segment is scored HIGH -> Full Content
            if initial_rel == "HIGH":
                final_context_map[p_id_str] = {
                    "telegram_message_id": post.telegram_message_id,
                    "relevance": "HIGH",
                    "content": seg_content_from_text(post.message_text),
                    "timestamp": meta.get("timestamp_seconds", 0)
                }
            # Case B: Segment is scored MEDIUM OR belongs to a HIGH topic -> Summary
            elif initial_rel == "MEDIUM" or t_id in winning_topics:
                # Don't overwrite if it was already marked HIGH
                if p_id_str not in final_context_map:
                    final_context_map[p_id_str] = {
                        "telegram_message_id": post.telegram_message_id,
                        "relevance": "MEDIUM",
                        "content": seg_summary_from_text(post.message_text),
                        "timestamp": meta.get("timestamp_seconds", 0)
                    }

        # Convert to list and sort by timestamp for narrative flow
        context = list(final_context_map.values())
        context.sort(key=lambda x: x["timestamp"])
        return context

    async def _synthesize_response(self, query: str, context: list[dict[str, Any]]) -> str:
        """The Frontier Beast synthesis with explicit content labeling."""

        formatted_parts = []
        for c in context:
            content_type = "FULL TRANSCRIPT" if c["relevance"] == "HIGH" else "SUMMARY (NARRATIVE BRIDGE)"
            formatted_parts.append(
                f"--- SEGMENT [{c['telegram_message_id']}] at {c['timestamp']}s [{content_type}] ---\n{c['content']}"
            )

        formatted_context = "\n\n".join(formatted_parts)

        # Match the synthesis language to the query language up front; the
        # post-synthesis LanguageValidationService stays as a safety net, but
        # generating in the right language avoids a second (style-losing) pass.
        target_language = detect_query_language(query)
        language_rule = (
            "Output must be in Russian, matching the expert's original speaking style."
            if target_language == "Russian"
            else "Output must be in English regardless of the transcript language."
        )

        system_prompt = f"""<?xml version="1.0" encoding="UTF-8"?>
<system_prompt>
    <role>You are the Expert's Digital Twin. Your task is to synthesize a full-text response in the expert's original style.</role>
    <context>
        <date>TODAY is {datetime.now().strftime('%Y-%m-%d')}.</date>
    </context>
    <guardrails>
        <rule priority="CRITICAL">DO NOT SUMMARIZE. Reconstruct the expert's original reasoning flow and vocabulary.</rule>
        <rule>Use segments marked [FULL TRANSCRIPT] for detailed technical explanations and citations.</rule>
        <rule>Use segments marked [SUMMARY] strictly as narrative bridges to connect the gaps between detailed parts.</rule>
        <rule>The output must feel like a continuous lecture or detailed answer from the expert.</rule>
        <rule>Maintain technical depth, specific metaphors, and engineering slang used by the expert.</rule>
        <rule priority="CRITICAL">VISUAL ELEMENTS — AMBIENT: For incidental on-screen context (e.g., the expert on camera, a browser, a generic slide background), do NOT literally quote the markers "[НА ЭКРАНЕ: ...]"/"[SLIDE: ...]" and do NOT use phrases like "На экране показано" or "На слайде написано". Extract the core meaning and ORGANICALLY WEAVE it into the expert's narrative, so it reads as if the expert is speaking it.</rule>
        <rule priority="CRITICAL">VISUAL ELEMENTS — INFORMATIONAL (surface it, do not hide): When the marker carries the actual payload — a PROMPT, model or generation settings (model name, aspect ratio, duration, seed, guidance/CFG, steps), code, formulas, exact figures, or a title/label the viewer must read — PRESERVE IT LITERALLY. Reproduce prompt text and parameter values exactly as shown (e.g., Prompt: "..."), and present settings as a short list. Do NOT paraphrase, translate, round, drop, or dissolve these values into narration.</rule>
        <rule priority="CRITICAL">VISUAL ELEMENTS — UNREADABLE: If on-screen text is marked unreadable/uncertain or is clearly garbled, say that the content could not be read. Never invent or guess on-screen text.</rule>
        <rule priority="CRITICAL">MANDATORY CITATIONS: Cite sources using [post:ID] format where ID is the segment ID. Every technical claim or specific insight should be cited.</rule>
    </guardrails>
    <formatting>
        <language>{language_rule}</language>
    </formatting>
</system_prompt>"""

        user_prompt = f"""Question: {query}

Expert Video Segments:
{formatted_context}

Please provide a detailed, high-fidelity retelling of the expert's insights:"""

        async for attempt in self._retrying():
            with attempt:
                response = await self.llm_client.chat_completions_create(
                    model=self.synthesis_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=8192
                )
                return response.choices[0].message.content
        raise RuntimeError("Video Synthesis produced no response")  # pragma: no cover

# Helper functions to extract parts from our custom message_text format with robustness
def seg_title_from_text(text: str) -> str:
    try:
        if "TITLE: " in text and "\nSUMMARY: " in text:
            return text.split("TITLE: ", 1)[1].split("\nSUMMARY: ", 1)[0].strip()
        if "TITLE: " in text:
            return text.split("TITLE: ", 1)[1].split("\n", 1)[0].strip()
    except Exception:
        pass
    return "Untitled Segment"

def seg_summary_from_text(text: str) -> str:
    try:
        if "\nSUMMARY: " in text and "\n---\n" in text:
            return text.split("\nSUMMARY: ", 1)[1].split("\n---\n", 1)[0].strip()
        if "SUMMARY: " in text:
            parts = text.split("SUMMARY: ", 1)[1].split("---", 1)
            if len(parts) > 1:
                return parts[0].strip()
    except Exception:
        pass
    return ""

def seg_content_from_text(text: str) -> str:
    try:
        if "\nCONTENT:\n" in text:
            return text.split("\nCONTENT:\n", 1)[1].strip()
        if "CONTENT:" in text:
            return text.split("CONTENT:", 1)[1].strip()
        if "---" in text:
            return text.split("---")[-1].strip()
    except Exception:
        pass
    return text
