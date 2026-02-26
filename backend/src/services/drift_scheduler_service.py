import asyncio
import json
import time
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import MODEL_DRIFT_ANALYSIS, BACKEND_LOG_FILE
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError

# Configure logging specific for Cron Jobs
CRON_LOG_FILE = Path("/app/data/logs/cron_jobs.log")
# Ensure directory exists (fallback to local path for dev)
if not CRON_LOG_FILE.parent.exists():
    if os.path.exists("backend/data"):
        CRON_LOG_FILE = Path("backend/data/logs/cron_jobs.log")
    else:
        # Fallback relative to current script
        CRON_LOG_FILE = Path(__file__).parent.parent.parent / "data" / "logs" / "cron_jobs.log"

CRON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(CRON_LOG_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("drift_scheduler")

class DriftSchedulerService:
    """
    Service for processing 'pending' comment groups using Google Gemini.
    Designed for Cron Job execution with strict rate limiting.

    Uses the unified google_ai_studio_client for consistent API access
    with automatic retry logic and OpenAI-compatible response format.
    """

    def __init__(self, db: Session):
        self.db = db
        self.client = create_google_ai_studio_client()
        self.model_name = MODEL_DRIFT_ANALYSIS
        # Rate limiting is handled by the google_ai_studio_client
        # which uses Tenacity with exponential backoff + jitter
        logger.info(f"DriftSchedulerService initialized with model: {self.model_name}")

    def get_pending_groups(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch pending groups with their posts and comments."""
        query = text("""
            SELECT
                cgd.post_id,
                cgd.expert_id,
                p.message_text as post_text,
                p.telegram_message_id
            FROM comment_group_drift cgd
            JOIN posts p ON cgd.post_id = p.post_id
            WHERE cgd.analyzed_by = 'pending'
            ORDER BY cgd.post_id ASC
            LIMIT :limit
        """)

        results = self.db.execute(query, {"limit": limit}).fetchall()
        groups = []

        for row in results:
            # Fetch comments for this post
            comments_query = text("""
                SELECT author_name, comment_text
                FROM comments
                WHERE post_id = :post_id
                ORDER BY created_at ASC
            """)
            comments = self.db.execute(comments_query, {"post_id": row.post_id}).fetchall()

            groups.append({
                "post_id": row.post_id,
                "expert_id": row.expert_id,
                "post_text": row.post_text,
                "telegram_message_id": row.telegram_message_id,
                "comments": [{"author": c.author_name, "text": c.comment_text} for c in comments]
            })

        return groups

    async def analyze_drift_async(self, post_text: str, comments: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze drift using Gemini through the unified client.
        Returns parsed JSON result.

        This is an async method that uses the unified Google AI Studio client
        which handles retry logic and OpenAI-compatible response format.
        """
        comments_text = "\n".join([f"- {c['author']}: {c['text']}" for c in comments])

        prompt = f"""Analyze this Telegram post and its comments to determine if the discussion DRIFTED to other topics.

POST (anchor):
{post_text[:1000]}...

COMMENTS:
{comments_text[:3000]}

TASK:
1. Determine if comments discuss topics NOT mentioned in the post
2. If yes (drift detected), extract drift topics with:
   - topic: General theme (1-2 sentences)
   - keywords: Specific terms, technologies, names (array)
   - key_phrases: Direct quotes from comments (array, 1-3 phrases)
   - context: Brief explanation (1 sentence)

CRITERIA FOR DRIFT:
✅ DRIFT:
- Comments ask about/discuss technologies/concepts not in post
- Discussion moves to different subject area
- New specific questions with detailed answers

❌ NOT DRIFT:
- Comments just expand on post topic
- Questions clarifying post content
- Generic reactions/thanks

CONFIDENCE:
- high: Clear drift, obvious new topics
- medium: Partial drift, some new elements
- low: Unclear if drift or just expansion

Return ONLY valid JSON:
{{
  "has_drift": true/false,
  "confidence": "high|medium|low",
  "drift_topics": [
    {{
      "topic": "...",
      "keywords": ["..."],
      "key_phrases": ["..."],
      "context": "..."
    }}
  ] or null
}}"""

        try:
            response = await self.client.chat_completions_create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            # Parse OpenAI-compatible response format
            text_response = response.choices[0].message.content.strip()

            # Robust JSON extraction (same as original)
            try:
                parsed = json.loads(text_response)
            except json.JSONDecodeError:
                # Heuristic extraction
                idx_brace = text_response.find('{')
                idx_bracket = text_response.find('[')

                start_idx = -1
                end_idx = -1

                if idx_brace != -1 and idx_bracket != -1:
                    if idx_brace < idx_bracket:
                        start_idx = idx_brace
                        end_idx = text_response.rfind('}')
                    else:
                        start_idx = idx_bracket
                        end_idx = text_response.rfind(']')
                elif idx_brace != -1:
                    start_idx = idx_brace
                    end_idx = text_response.rfind('}')
                elif idx_bracket != -1:
                    start_idx = idx_bracket
                    end_idx = text_response.rfind(']')

                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = text_response[start_idx : end_idx + 1]
                    try:
                        parsed = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse extracted JSON: {json_str[:100]}... Error: {e}")
                        raise ValueError(f"Gemini returned invalid JSON structure even after extraction.")
                else:
                    raise ValueError(f"Could not find valid JSON object in response: {text_response[:100]}")

            # Validate structure
            if isinstance(parsed, list):
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    return parsed[0]
                raise ValueError(f"Gemini returned invalid list structure: {str(parsed)[:100]}")

            if not isinstance(parsed, dict):
                raise ValueError(f"Gemini returned non-dict JSON: {type(parsed)}")

            return parsed

        except GoogleAIStudioError as e:
            # The unified client handles rate limit retries automatically
            # If we still get an error here, log and re-raise
            if e.is_rate_limit:
                logger.error(f"Rate limit error after retries: {str(e)}")
            else:
                logger.error(f"Google AI Studio error: {str(e)}")
            raise



    def update_group_status(self, post_id: int, analysis_result: Dict[str, Any]):
        """Update database with analysis results."""

        has_drift = analysis_result.get("has_drift", False)
        drift_topics = analysis_result.get("drift_topics")

        # Ensure drift_topics is valid JSON string or NULL
        drift_topics_json = None
        if has_drift and drift_topics:
            drift_data = {
                "has_drift": has_drift,
                "drift_topics": drift_topics
            }
            drift_topics_json = json.dumps(drift_data, ensure_ascii=False)

        update_query = text("""
            UPDATE comment_group_drift
            SET
                has_drift = :has_drift,
                drift_topics = :drift_topics,
                analyzed_by = 'drift_checked_gemini',
                analyzed_at = datetime('now')
            WHERE post_id = :post_id
        """)

        self.db.execute(update_query, {
            "post_id": post_id,
            "has_drift": 1 if has_drift else 0,
            "drift_topics": drift_topics_json
        })
        self.db.commit()

    async def process_batch(self, batch_size: int = 10):
        """Process a batch of pending groups."""
        groups = self.get_pending_groups(limit=batch_size)

        if not groups:
            logger.info("No pending groups found.")
            return 0

        logger.info(f"Starting processing batch of {len(groups)} groups")

        success_count = 0
        for group in groups:
            try:
                # Check if empty comments
                if not group['comments']:
                    logger.info(f"Post {group['post_id']} has no comments, marking no-comments")
                    self.db.execute(text("""
                        UPDATE comment_group_drift
                        SET analyzed_by = 'no-comments', analyzed_at = datetime('now')
                        WHERE post_id = :pid
                    """), {"pid": group['post_id']})
                    self.db.commit()
                    continue

                # Analyze
                logger.info(f"Analyzing post {group['post_id']} ({len(group['comments'])} comments)...")
                result = await self.analyze_drift_async(group['post_text'], group['comments'])

                # Update DB
                self.update_group_status(group['post_id'], result)
                success_count += 1

                if result.get('has_drift'):
                    logger.info(f"✅ DRIFT DETECTED for post {group['post_id']}")

                # Rate limiting is handled by the unified client
                # Small delay to be safe
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"❌ Error analyzing post {group['post_id']}: {str(e)}")
                # Mark as error so we don't loop forever
                self.db.execute(text("""
                    UPDATE comment_group_drift
                    SET analyzed_by = 'error', analyzed_at = datetime('now')
                    WHERE post_id = :pid
                """), {"pid": group['post_id']})
                self.db.commit()

        logger.info(f"Batch complete. Processed {success_count}/{len(groups)} successfully.")
        return len(groups)

    async def run_full_cycle(self):
        """Run until no pending groups remain."""
        logger.info("🚀 Starting Drift Scheduler Cycle")
        total_processed = 0

        while True:
            count = await self.process_batch(batch_size=10)
            total_processed += count
            if count == 0:
                break

            # Extra cooldown between batches
            logger.info("Batch cooldown (10s)...")
            await asyncio.sleep(10)

        logger.info(f"🏁 Cycle complete. Total processed: {total_processed}")
