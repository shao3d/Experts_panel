import asyncio
import json
import time
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import GOOGLE_AI_STUDIO_API_KEYS, BACKEND_LOG_FILE

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
    """

    def __init__(self, db: Session):
        self.db = db
        self.keys = GOOGLE_AI_STUDIO_API_KEYS
        self.current_key_index = 0
        self._configure_model()
        # Strict Rate Limit for Gemini Pro (Free Tier)
        # Limit is usually 5 RPM per key. We sleep 15s to be safe (4 RPM).
        # With 5 keys, we can theoretically burst, but we play it safe per-key.
        self.rate_limit_delay = 15.0

    def _configure_model(self):
        """Configure Gemini model with current key."""
        if not self.keys:
            raise ValueError("No GOOGLE_AI_STUDIO_API_KEYS configured")
        
        key = self.keys[self.current_key_index]
        genai.configure(api_key=key)
        
        # Use Gemini 2.5 Pro as requested (Strong model)
        # Limits: ~5 RPM / 50-100 RPD per key (Free Tier)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        logger.info(f"Configured Gemini 2.5 Pro with key index {self.current_key_index}")

    def _rotate_key(self):
        """Rotate to next available API key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        logger.warning(f"🔄 Rotating to Google API Key index: {self.current_key_index}")
        self._configure_model()

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

    def analyze_drift(self, post_text: str, comments: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze drift using Gemini.
        Returns parsed JSON result.
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
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            # Parse JSON
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # Fallback cleanup
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_text)
                
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                self._rotate_key()
                time.sleep(2)
                # Retry once with new key
                return self.analyze_drift(post_text, comments)
            else:
                raise e

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

    def process_batch(self, batch_size: int = 10):
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
                result = self.analyze_drift(group['post_text'], group['comments'])
                
                # Update DB
                self.update_group_status(group['post_id'], result)
                success_count += 1
                
                if result.get('has_drift'):
                    logger.info(f"✅ DRIFT DETECTED for post {group['post_id']}")
                
                # Strict Rate Limiting
                time.sleep(self.rate_limit_delay)
                
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

    def run_full_cycle(self):
        """Run until no pending groups remain."""
        logger.info("🚀 Starting Drift Scheduler Cycle")
        total_processed = 0
        
        while True:
            count = self.process_batch(batch_size=10)
            total_processed += count
            if count == 0:
                break
            
            # Extra cooldown between batches
            logger.info("Batch cooldown (10s)...")
            time.sleep(10)
            
        logger.info(f"🏁 Cycle complete. Total processed: {total_processed}")
