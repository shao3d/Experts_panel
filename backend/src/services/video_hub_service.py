"""Video Hub Service for deep analysis of video transcripts.

Handles segment-level semantic mapping, thread-based context expansion, 
and high-fidelity stylistic synthesis.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .. import config
from .google_ai_studio_client import create_google_ai_studio_client
from .language_validation_service import LanguageValidationService

logger = logging.getLogger(__name__)

class VideoHubService:
    def __init__(self):
        self.llm_client = create_google_ai_studio_client()
        self.map_model = config.MODEL_MAP
        self.synthesis_model = config.MODEL_VIDEO_PRO # gemini-3.0-pro
        self.flash_model = config.MODEL_VIDEO_FLASH   # gemini-3.0-flash

    async def process(
        self,
        query: str,
        video_segments: List[Any], # List of Post objects
        expert_id: str = "video_hub",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process the 4-phase video pipeline with segment-level precision."""
        
        # 1. Video Map Phase (Segment-Level Scoring)
        if progress_callback:
            await progress_callback({"phase": "video_map", "status": "processing", "message": "Scoring individual video segments..."})
        
        scored_segments = await self._map_segments(query, video_segments)
        
        # Filter out only HIGH and MEDIUM
        high_segments = [s for s in scored_segments if s["relevance"] == "HIGH"]
        medium_segments = [s for s in scored_segments if s["relevance"] == "MEDIUM"]

        if not high_segments and not medium_segments:
            return {
                "answer": "В видео-архиве не найдено достаточно релевантных сегментов для ответа на этот вопрос.",
                "main_sources": [],
                "confidence": "LOW",
                "posts_analyzed": len(video_segments)
            }

        # 2. Video Resolve Phase (Semantic Thread Expansion)
        if progress_callback:
            await progress_callback({"phase": "video_resolve", "status": "processing", "message": "Expanding knowledge threads for continuity..."})
        
        thread_context = self._resolve_threads(scored_segments, video_segments)

        # 3. Video Synthesis Phase (The Digital Twin)
        if progress_callback:
            await progress_callback({"phase": "video_synthesis", "status": "processing", "message": "Synthesizing expert response (Gemini 3.0 Pro)..."})
        
        answer = await self._synthesize_response(query, thread_context)

        # 4. Language Validation (Style-Preserving)
        if progress_callback:
            await progress_callback({"phase": "video_validation", "status": "processing", "message": "Applying style-aware translation..."})
        
        validator = LanguageValidationService(model=self.flash_model)
        validation_result = await validator.process(answer, query, expert_id)
        final_answer = validation_result.get("answer", answer)

        return {
            "answer": final_answer,
            "main_sources": [s["telegram_message_id"] for s in thread_context if s["relevance"] == "HIGH"],
            "confidence": "HIGH" if high_segments else "MEDIUM",
            "posts_analyzed": len(video_segments)
        }

    async def _map_segments(self, query: str, segments: List[Any]) -> List[Dict[str, Any]]:
        """Score each segment individually based on its summary."""
        
        map_input = []
        for s in segments:
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

Output JSON ONLY:
{{
  "scores": [
    {{"id": 123, "relevance": "HIGH", "reason": "..."}},
    {{"id": 456, "relevance": "LOW", "reason": "..."}}
  ]
}}
"""
        try:
            response = await self.llm_client.chat_completions_create(
                model=self.map_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return data.get("scores", [])
        except Exception as e:
            logger.error(f"Video Map failed: {e}")
            return []

    def _resolve_threads(self, scored_segments: List[Dict[str, Any]], all_posts: List[Any]) -> List[Dict[str, Any]]:
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

    async def _synthesize_response(self, query: str, context: List[Dict[str, Any]]) -> str:
        """The Frontier Beast synthesis with explicit content labeling."""
        
        formatted_parts = []
        for c in context:
            content_type = "FULL TRANSCRIPT" if c["relevance"] == "HIGH" else "SUMMARY (NARRATIVE BRIDGE)"
            formatted_parts.append(
                f"--- SEGMENT [{c['telegram_message_id']}] at {c['timestamp']}s [{content_type}] ---\n{c['content']}"
            )
            
        formatted_context = "\n\n".join(formatted_parts)

        system_prompt = """You are the Expert's Digital Twin. Your task is to synthesize a full-text response in the expert's original style.
TODAY is 2026.

RULES:
1. DO NOT SUMMARIZE. Reconstruct the expert's original reasoning flow and vocabulary.
2. Use segments marked [FULL TRANSCRIPT] for detailed technical explanations and citations.
3. Use segments marked [SUMMARY] strictly as narrative bridges to connect the gaps between detailed parts.
4. The output must feel like a continuous lecture or detailed answer from the expert.
5. Maintain technical depth, specific metaphors, and engineering slang used by the expert.
6. MANDATORY: Cite sources using [post:ID] format where ID is the segment ID.

Output must be in Russian unless specified otherwise."""

        user_prompt = f"""Question: {query}

Expert Video Segments:
{formatted_context}

Please provide a detailed, high-fidelity retelling of the expert's insights:"""

        response = await self.llm_client.chat_completions_create(
            model=self.synthesis_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content

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
