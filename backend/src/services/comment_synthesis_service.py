"""Comment synthesis service for extracting insights from comment discussions."""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .openrouter_adapter import create_openrouter_client, convert_model_name
from .hybrid_llm_adapter import create_hybrid_client, is_hybrid_mode_enabled
from .. import config
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language, get_response_language_instruction

logger = logging.getLogger(__name__)


class CommentSynthesisService:
    """Service for synthesizing insights from comment group discussions.

    Takes relevant comment groups and extracts additional insights that
    complement the main answer from the Reduce phase.
    """

    def __init__(self):
        """Initialize CommentSynthesisService.
        """
        # Use hybrid client if enabled, otherwise fallback to OpenRouter
        if is_hybrid_mode_enabled():
            self.client = create_hybrid_client(
                openrouter_api_key=config.OPENROUTER_API_KEY,
                google_ai_studio_api_key=config.GOOGLE_AI_STUDIO_API_KEY,
                fallback_model=config.MODEL_SYNTHESIS_FALLBACK,
                enable_hybrid=True
            )
            logger.info("CommentSynthesisService initialized with hybrid LLM client (Google AI Studio + OpenRouter)")
        else:
            self.client = create_openrouter_client(api_key=config.OPENROUTER_API_KEY)
            logger.info("CommentSynthesisService initialized with OpenRouter client only")

        self.model = config.MODEL_SYNTHESIS_PRIMARY
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        """Load the comment synthesis prompt template."""
        try:
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "comment_synthesis_prompt.txt"

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Comment synthesis prompt template not found at {prompt_path}")
            raise

    def _format_comment_groups(
        self,
        comment_groups: List[Dict[str, Any]]
    ) -> str:
        """Format comment groups for the synthesis prompt.

        Args:
            comment_groups: List of comment group data

        Returns:
            Formatted JSON string of comment groups
        """
        formatted_groups = []

        for group in comment_groups:
            # Extract only comments text (no anchor post)
            comments_text = []
            for comment in group.get("comments", []):
                comment_text = comment.get("text", "").strip()
                if comment_text:
                    comments_text.append(comment_text)

            if comments_text:
                formatted_group = {
                    "anchor_post_id": group.get("anchor_post", {}).get("id"),
                    "relevance": group.get("relevance", "MEDIUM"),
                    "reason": group.get("reason", ""),
                    "comments": comments_text,
                    "comment_count": len(comments_text)
                }
                formatted_groups.append(formatted_group)

        return json.dumps(formatted_groups, ensure_ascii=False, indent=2)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def _synthesize_insights(
        self,
        query: str,
        main_answer: str,
        comment_groups_json: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Call GPT-4o-mini to synthesize insights from comments.

        Args:
            query: User's original query
            main_answer: Main answer from Reduce phase
            comment_groups_json: JSON string of formatted comment groups
            progress_callback: Optional callback for progress updates

        Returns:
            Synthesized insights response
        """
        if progress_callback:
            await progress_callback({
                "phase": "comment_synthesis",
                "status": "synthesizing",
                "message": "Synthesizing insights from comment discussions"
            })

        # Create base prompt
        base_prompt = self._prompt_template.substitute(
            query=query,
            main_answer=main_answer,
            comment_groups=comment_groups_json
        )

        # Apply language instruction based on query language
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)

        # Prepare enhanced system message with language instruction
        enhanced_system = prepare_system_message_with_language(
            "You are a helpful assistant that extracts insights from comment discussions.",
            query
        )

        # Call LLM API (Google AI Studio first, then OpenRouter)
        if hasattr(self.client, 'chat_completions_create'):
            # Hybrid client
            response = await self.client.chat_completions_create(
                model=self.model,
                messages=[
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
                service_name="comment_synthesis"
            )
        else:
            # OpenRouter client
            response = await self.client.chat.completions.create(
                model=convert_model_name(self.model),
                messages=[
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                response_format={"type": "json_object"}
            )

        # Parse response
        raw_content = response.choices[0].message.content
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw content (first 500 chars): {raw_content[:500]}")
            raise ValueError(f"Failed to parse GPT response as JSON: {e}") from e

        # Handle both string and list formats from GPT
        if "synthesis" in result:
            synthesis = result["synthesis"]

            # If GPT returned a list of bullet points, join them into a string
            if isinstance(synthesis, list):
                synthesis = "\n".join(synthesis)
                logger.info(f"Converted synthesis from list ({len(result['synthesis'])} items) to string")
            elif isinstance(synthesis, str):
                logger.info("Synthesis already in string format")
            else:
                logger.warning(f"Unexpected synthesis type: {type(synthesis)}")
                synthesis = str(synthesis)

            # Sanitize synthesis string (same as in ReduceService)
            import re
            # Remove invalid escape sequences
            synthesis = re.sub(r'\\(?![ntr"\\/])', '', synthesis)
            result["synthesis"] = synthesis
            logger.info("Sanitized synthesis string for safe JSON transmission")

        # Track token usage
        if response.usage:
            result["token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        if progress_callback:
            await progress_callback({
                "phase": "comment_synthesis",
                "status": "completed",
                "message": "Comment synthesis completed"
            })

        return result

    async def process(
        self,
        query: str,
        main_answer: str,
        comment_groups: List[Dict[str, Any]],
        expert_id: str = "unknown",
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """Process and synthesize insights from comment groups.

        Args:
            query: User's original query
            main_answer: Main answer from Reduce phase
            comment_groups: List of relevant comment groups (HIGH/MEDIUM only)
            expert_id: Expert identifier for logging
            progress_callback: Optional callback for progress updates

        Returns:
            Synthesized insights string or None if no relevant groups
        """
        import time
        phase_start_time = time.time()

        # Filter to only HIGH/MEDIUM relevance
        relevant_groups = [
            g for g in comment_groups
            if g.get("relevance") in ["HIGH", "MEDIUM"]
        ]

        if not relevant_groups:
            logger.info(f"[{expert_id}] No HIGH/MEDIUM comment groups found, skipping synthesis")
            return None

        logger.info(f"[{expert_id}] Comment Synthesis Phase START: Synthesizing insights from {len(relevant_groups)} comment groups")

        if progress_callback:
            await progress_callback({
                "phase": "comment_synthesis",
                "status": "starting",
                "message": f"Starting comment synthesis with {len(relevant_groups)} groups"
            })

        # Format comment groups
        comment_groups_json = self._format_comment_groups(relevant_groups)

        # Synthesize insights
        synthesis = await self._synthesize_insights(
            query,
            main_answer,
            comment_groups_json,
            progress_callback
        )

        # Log phase completion with timing
        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Comment Synthesis Phase END: {duration_ms}ms, "
            f"processed {len(relevant_groups)} comment groups"
        )

        return synthesis.get("synthesis", "")
