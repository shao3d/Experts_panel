"""Comment synthesis service for extracting insights from comment discussions."""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from string import Template

from tenacity import retry, stop_after_attempt, wait_exponential

from .monitored_client import create_monitored_client
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
        # Use monitored client (Google Gemini)
        self.client = create_monitored_client()
        logger.info("CommentSynthesisService initialized with monitored Google AI Studio client")

        self.model = config.MODEL_SYNTHESIS
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
        comment_groups: List[Dict[str, Any]],
        expert_name: str = ""
    ) -> str:
        """Format comment groups for the synthesis prompt with author separation.

        Args:
            comment_groups: List of comment group data
            expert_name: Name of the expert to separate their comments

        Returns:
            Formatted JSON string of comment groups with author attribution
        """
        formatted_groups = []

        for group in comment_groups:
            expert_comments = []
            community_comments = []

            for comment in group.get("comments", []):
                text = comment.get("text", "").strip()
                author = comment.get("author", "Unknown")
                if text:
                    comment_data = {"author": author, "text": text}
                    # Separate expert's comments from community
                    if expert_name and author.lower() == expert_name.lower():
                        expert_comments.append(comment_data)
                    else:
                        community_comments.append(comment_data)

            if expert_comments or community_comments:
                formatted_groups.append({
                    "anchor_post_id": group.get("anchor_post", {}).get("id"),
                    "relevance": group.get("relevance", "MEDIUM"),
                    "reason": group.get("reason", ""),
                    "expert_comments": expert_comments,
                    "community_comments": community_comments
                })

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
        expert_name: str = "",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Call LLM to synthesize insights from comments.

        Args:
            query: User's original query
            main_answer: Main answer from Reduce phase
            comment_groups_json: JSON string of formatted comment groups
            expert_name: Name of the expert for attribution
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

        # Create base prompt with expert_name
        base_prompt = self._prompt_template.substitute(
            query=query,
            main_answer=main_answer,
            comment_groups=comment_groups_json,
            expert_name=expert_name
        )

        # Apply language instruction based on query language
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)

        # Prepare enhanced system message with language instruction
        enhanced_system = prepare_system_message_with_language(
            "You are a helpful assistant that extracts insights from comment discussions.",
            query
        )

        # Call LLM API (Google AI Studio)
        response = await self.client.chat_completions_create(
            model=self.model,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            service_name="comment_synthesis"
        )

        # Parse response
        raw_content = response.choices[0].message.content
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw content (first 500 chars): {raw_content[:500]}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

        # Handle new format with expert/community split
        import re
        expert_insights = result.get("expert_insights", "")
        community_insights = result.get("community_insights", "")

        # Handle list format if LLM returns it
        if isinstance(expert_insights, list):
            expert_insights = "\n".join(expert_insights)
        if isinstance(community_insights, list):
            community_insights = "\n".join(community_insights)

        # Sanitize strings (remove invalid escape sequences)
        if expert_insights:
            expert_insights = re.sub(r'\\(?![ntr"\\/])', '', expert_insights)
        if community_insights:
            community_insights = re.sub(r'\\(?![ntr"\\/])', '', community_insights)

        # Combine into final synthesis with sections
        parts = []
        if expert_insights and expert_insights.strip():
            parts.append(f"**Уточнения автора:**\n{expert_insights}")
        if community_insights and community_insights.strip():
            parts.append(f"**Мнения сообщества:**\n{community_insights}")

        result["synthesis"] = "\n\n".join(parts) if parts else ""
        logger.info(f"Synthesis combined: expert={bool(expert_insights)}, community={bool(community_insights)}")

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

        # Get expert display name for comment attribution
        from ..api.models import get_expert_name
        expert_name = get_expert_name(expert_id)

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

        # Format comment groups with expert name for separation
        comment_groups_json = self._format_comment_groups(relevant_groups, expert_name)

        # Synthesize insights with expert name
        synthesis = await self._synthesize_insights(
            query,
            main_answer,
            comment_groups_json,
            expert_name,
            progress_callback
        )

        # Log phase completion with timing
        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Comment Synthesis Phase END: {duration_ms}ms, "
            f"processed {len(relevant_groups)} comment groups"
        )

        return synthesis.get("synthesis", "")
