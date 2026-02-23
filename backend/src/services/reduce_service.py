"""Reduce service for synthesizing comprehensive answers from posts."""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from string import Template

from tenacity import retry, stop_after_attempt, wait_exponential

from .monitored_client import create_monitored_client
from .. import config
from ..models.base import SessionLocal
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

logger = logging.getLogger(__name__)


class ReduceService:
    """Service for the Reduce phase of the Map-Resolve-Reduce pipeline.

    Synthesizes a comprehensive answer from all gathered posts,
    using a configurable LLM to create a coherent response with source attribution.
    """

    MAX_CONTEXT_POSTS = 50  # Limit for token management

    def __init__(self, use_personal_style: bool = True):
        """Initialize ReduceService.

        Args:
            use_personal_style: Use Refat's personal writing style (default True)
        """
        # Use monitored client (Google Gemini)
        self.client = create_monitored_client()
        logger.info("ReduceService initialized with monitored Google AI Studio client")

        self.model = config.MODEL_SYNTHESIS
        self.use_personal_style = use_personal_style
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        """Load the reduce phase prompt template."""
        try:
            # Use relative path from current file location
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            # Choose prompt based on style preference
            prompt_filename = "reduce_prompt_personal.txt" if self.use_personal_style else "reduce_prompt.txt"
            prompt_path = prompt_dir / prompt_filename

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Reduce prompt template not found at {prompt_path}")
            raise


    def _format_posts_for_synthesis(
        self,
        enriched_posts: List[Dict[str, Any]]
    ) -> str:
        """Format enriched posts for the synthesis prompt.

        Args:
            enriched_posts: List of enriched post data

        Returns:
            Formatted JSON string of posts
        """
        # Sort by relevance FIRST (before limiting)
        relevance_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "CONTEXT": 3}
        sorted_posts = sorted(
            enriched_posts,
            key=lambda x: relevance_order.get(x.get("relevance", "MEDIUM"), 3)
        )

        # Then limit to MAX_CONTEXT_POSTS (50)
        posts_to_include = sorted_posts[:self.MAX_CONTEXT_POSTS]

        if len(enriched_posts) > self.MAX_CONTEXT_POSTS:
            logger.warning(
                f"Limiting context to {self.MAX_CONTEXT_POSTS} posts "
                f"(had {len(enriched_posts)}). Kept best by relevance."
            )

        # Format posts for prompt
        formatted_posts = []
        for post in posts_to_include:
            formatted_post = {
                "telegram_message_id": post["telegram_message_id"],
                "date": post.get("created_at", "Unknown"),
                "content": post.get("content") or "[Media only]",
                "author": post.get("author") or "Unknown",
                "relevance": post.get("relevance", "MEDIUM"),
                "is_original": post.get("is_original", True)
            }
            formatted_posts.append(formatted_post)

        return json.dumps(formatted_posts, ensure_ascii=False, indent=2)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def _synthesize_answer(
        self,
        query: str,
        posts_json: str,
        expert_id: str = "unknown",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Call Gemini to synthesize the final answer.

        Args:
            query: User's query
            posts_json: JSON string of formatted posts
            progress_callback: Optional callback for progress updates

        Returns:
            Synthesized answer response
        """
        if progress_callback:
            await progress_callback({
                "phase": "reduce",
                "status": "synthesizing",
                "message": "Synthesizing comprehensive answer",
                "processed": 0,
                "total": 1
            })

        # Create base prompt
        base_prompt = self._prompt_template.substitute(
            query=query,
            posts=posts_json
        )

        # Apply language instruction based on query language
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)

        # Prepare enhanced system message with language instruction
        enhanced_system = prepare_system_message_with_language(
            "You are a helpful assistant that synthesizes information from Telegram posts.",
            query
        )

        # Call LLM API (Google AI Studio)
        response = await self.client.chat_completions_create(
            model=self.model,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,  # Balance between accuracy and natural language
            response_format={"type": "json_object"},
            max_tokens=4096,
            service_name="reduce"
        )

        # Parse response with robust error handling
        raw_content = response.choices[0].message.content
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw content (first 500 chars): {raw_content[:500]}")

            # Try to fix common escape issues
            try:
                # Fix invalid escape sequences by escaping backslashes
                fixed_content = raw_content.replace('\\', '\\\\')
                # But preserve valid JSON escapes
                fixed_content = (fixed_content
                    .replace('\\\\n', '\\n')
                    .replace('\\\\t', '\\t')
                    .replace('\\\\r', '\\r')
                    .replace('\\\\"', '\\"')
                    .replace('\\\\/', '\\/')
                )
                result = json.loads(fixed_content)
                logger.info("Successfully parsed JSON after fixing escape sequences")
            except json.JSONDecodeError as e2:
                logger.error(f"JSON parsing failed even after fixes: {e2}")
                logger.error(f"Full raw content: {raw_content}")
                raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

        # ALWAYS sanitize answer string to prevent frontend JSON parsing errors
        # This is critical: even if JSON parsing succeeded, the answer string may
        # contain invalid escape sequences that will break frontend JSON.parse()
        if "answer" in result and isinstance(result["answer"], str):
            import re
            answer = result["answer"]
            # Remove invalid escape sequences by cleaning backslashes
            # Keep only valid JSON escapes: \n \t \r \" \/ \\
            answer = re.sub(r'\\(?![ntr"\\/])', '', answer)
            result["answer"] = answer
            logger.info("Sanitized answer string for safe JSON transmission")

        # Track token usage
        if response.usage:
            result["token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        if progress_callback:
            await progress_callback({
                "phase": "reduce",
                "status": "synthesized",
                "message": "Answer synthesis completed",
                "processed": 1,
                "total": 1
            })

        # Validate that all referenced posts are in main_sources (important for Gemini)
        import re
        mentioned_ids = re.findall(r'\[post:(\d+)\]', result.get("answer", ""))
        main_sources = result.get("main_sources", [])

        # Check for any missing IDs
        missing_ids = []
        for post_id_str in mentioned_ids:
            post_id = int(post_id_str)
            if post_id not in main_sources:
                missing_ids.append(post_id)
                logger.warning(f"Post {post_id} mentioned in answer but not in main_sources!")

        # Add missing IDs to main_sources to maintain consistency
        if missing_ids:
            logger.info(f"Adding {len(missing_ids)} missing IDs to main_sources: {missing_ids}")
            result["main_sources"] = sorted(list(set(main_sources + missing_ids)))

        # Add fact validation
        try:
            from .fact_validator import FactValidator

            with SessionLocal() as db:
                validator = FactValidator(db)
                validation_report = validator.generate_validation_report(
                    answer=result.get("answer", ""),
                    post_ids=result.get("main_sources", [])
                )
                result["validation"] = validation_report
                result["accuracy_score"] = validation_report.get("accuracy_score", 1.0)

                # Log validation results
                logger.info(f"[{expert_id}] Fact validation completed - Accuracy: {result['accuracy_score']:.2%}")
                if result["accuracy_score"] < 1.0:
                    logger.warning(f"[{expert_id}] Some referenced posts may not exist or have incorrect dates")
        except Exception as e:
            logger.error(f"Fact validation failed: {e}")
            # Don't fail the request, just log the error
            result["validation"] = {"error": str(e)}

        return result

    async def process(
        self,
        enriched_posts: List[Dict[str, Any]],
        query: str,
        expert_id: str = "unknown",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process and synthesize a comprehensive answer.

        Args:
            enriched_posts: List of enriched post data from Resolve phase
            query: User's query
            expert_id: Expert identifier for logging
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with final answer and metadata
        """
        import time
        phase_start_time = time.time()

        if not enriched_posts:
            return {
                "answer": "Unfortunately, I don't have any highly relevant posts about this topic in my knowledge base.",
                "main_sources": [],
                "confidence": "LOW",
                "has_expert_comments": False,
                "language": "ru",
                "posts_analyzed": 0,
                "summary": "No relevant posts found"
            }

        logger.info(f"[{expert_id}] Synthesizing answer from {len(enriched_posts)} posts")

        if progress_callback:
            await progress_callback({
                "phase": "reduce",
                "status": "starting",
                "message": f"Starting Reduce phase with {len(enriched_posts)} posts",
                "processed": 0,
                "total": 1
            })

        # Format posts for synthesis
        posts_json = self._format_posts_for_synthesis(enriched_posts)

        # Synthesize the answer (no comments needed)
        synthesis = await self._synthesize_answer(
            query,
            posts_json,
            expert_id,
            progress_callback
        )

        # Extract main sources from synthesis or derive from high-relevance posts
        main_sources = synthesis.get("main_sources", [])
        if not main_sources:
            # Fallback to high-relevance posts
            main_sources = [
                p["telegram_message_id"]
                for p in enriched_posts
                if p.get("relevance") == "HIGH"
            ][:5]  # Top 5

        # Count posts by relevance
        relevance_counts = {
            "HIGH": sum(1 for p in enriched_posts if p.get("relevance") == "HIGH"),
            "MEDIUM": sum(1 for p in enriched_posts if p.get("relevance") == "MEDIUM"),
            "LOW": sum(1 for p in enriched_posts if p.get("relevance") == "LOW"),
            "CONTEXT": sum(1 for p in enriched_posts if p.get("relevance") == "CONTEXT")
        }

        summary = (
            f"Synthesized answer from {len(enriched_posts)} posts. "
            f"Distribution: {relevance_counts['HIGH']} HIGH, "
            f"{relevance_counts['MEDIUM']} MEDIUM, "
            f"{relevance_counts['LOW']} LOW, "
            f"{relevance_counts['CONTEXT']} CONTEXT."
        )

        # Log phase completion with timing
        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Reduce Phase END: {duration_ms}ms, "
            f"synthesized answer from {len(enriched_posts)} posts, "
            f"confidence={synthesis.get('confidence', 'MEDIUM')}"
        )

        if progress_callback:
            await progress_callback({
                "phase": "reduce",
                "status": "completed",
                "message": "Reduce phase completed",
                "summary": summary,
                "processed": 1,
                "total": 1
            })

        return {
            "answer": synthesis.get("answer", ""),
            "main_sources": main_sources,
            "confidence": synthesis.get("confidence", "MEDIUM"),
            "has_expert_comments": synthesis.get("has_expert_comments", False),
            "language": synthesis.get("language", "ru"),
            "posts_analyzed": len(enriched_posts),
            "expert_comments_included": 0,
            "relevance_distribution": relevance_counts,
            "token_usage": synthesis.get("token_usage"),
            "summary": summary
        }