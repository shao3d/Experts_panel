"""
Meta-Synthesis Service: Cross-expert unified analysis.

Takes responses from 2+ experts and synthesizes a single executive summary
that restructures information from "per-expert" axis to "per-topic" axis.

Runs in parallel with Reddit pipeline after all experts complete.
Returns markdown string or None on failure (graceful degradation).
"""

import json
import logging
from pathlib import Path
from string import Template
from typing import List, Optional

from ..api.models import ExpertResponse
from ..utils.language_utils import (
    prepare_prompt_with_language_instruction,
    prepare_system_message_with_language,
)
from .. import config
from .vertex_llm_client import get_vertex_llm_client

logger = logging.getLogger(__name__)


class MetaSynthesisService:
    """Service for synthesizing a unified analysis across multiple expert responses."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or config.MODEL_META_SYNTHESIS
        self._client = get_vertex_llm_client()
        self._prompt_template = self._load_prompt_template()
        logger.info(f"MetaSynthesisService initialized, model={self.model}")

    def _load_prompt_template(self) -> Template:
        prompt_dir = Path(__file__).parent.parent.parent / "prompts"
        prompt_path = prompt_dir / "meta_synthesis_prompt.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            return Template(f.read())

    async def synthesize(
        self,
        query: str,
        expert_responses: List[ExpertResponse],
    ) -> Optional[str]:
        """Synthesize a unified answer from multiple expert responses.

        Args:
            query: User's original question.
            expert_responses: List of ExpertResponse objects (2+ required).

        Returns:
            Markdown string with unified analysis, or None on failure.
        """
        # Guard: need at least 2 experts to synthesize
        if len(expert_responses) < 2:
            return None

        # 1. Format expert answers for the prompt
        expert_answers_json = self._format_expert_answers(expert_responses)

        # 2. Substitute into template
        base_prompt = self._prompt_template.substitute(
            query=query,
            expert_answers=expert_answers_json,
            expert_count=str(len(expert_responses)),
        )

        # 3. Language enforcement (reuse existing utils)
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)
        enhanced_system = prepare_system_message_with_language(
            "You are a senior analyst synthesizing reports from multiple domain experts.",
            query,
        )

        # 4. LLM call
        try:
            response = await self._client.chat_completions_create(
                model=self.model,
                messages=[
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=8192,  # Supports 30-40 experts (4096 truncates at ~15 experts)
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                logger.warning("Meta-synthesis LLM returned empty content")
                return None
            synthesis = content.strip()
            logger.info(
                f"Meta-synthesis completed: {len(synthesis)} chars, "
                f"experts={len(expert_responses)}, model={self.model}"
            )
            return synthesis
        except Exception as e:
            logger.error(f"Meta-synthesis failed: {e}")
            return None  # Graceful degradation

    def _format_expert_answers(self, expert_responses: List[ExpertResponse]) -> str:
        """Format expert responses as JSON for the LLM prompt."""
        formatted = []
        for resp in expert_responses:
            entry = {
                "expert_name": resp.expert_name,
                "confidence": resp.confidence.value
                if hasattr(resp.confidence, "value")
                else str(resp.confidence),
                "answer": resp.answer,
                "posts_analyzed": resp.posts_analyzed,
            }
            # Include comment synthesis if available (author corrections + community)
            if resp.comment_groups_synthesis:
                entry["comment_insights"] = resp.comment_groups_synthesis
            formatted.append(entry)
        return json.dumps(formatted, ensure_ascii=False, indent=2)
