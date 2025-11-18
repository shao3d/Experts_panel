#!/usr/bin/env python3
"""
Drift-on-synced agent for specific post analysis.

Analyzes drift for a specific post_id and updates the analyzed_by field
from 'pending' to 'drift-on-synced'.
"""

import asyncio
import json
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

# Configuration
DATABASE_PATH = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"


class DriftOnSyncedAgent:
    """Analyzes drift for specific pending comment groups."""

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.db_path = DATABASE_PATH

    async def analyze_specific_post(self, post_id: int) -> Dict[str, Any]:
        """Analyze drift for a specific post_id."""

        print(f"🎯 Starting drift analysis for post_id: {post_id}")

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get post details
            cursor.execute("""
                SELECT post_id, message_text, expert_id, telegram_message_id
                FROM posts WHERE post_id = ?
            """, (post_id,))

            post = cursor.fetchone()
            if not post:
                return {"error": f"Post {post_id} not found"}

            post_id, message_text, expert_id, telegram_message_id = post
            print(f"📄 Post #{telegram_message_id} from {expert_id}")
            print(f"📝 Preview: {message_text[:100]}...")

            # Get comments for this post
            cursor.execute("""
                SELECT comment_id, comment_text, author_name, created_at
                FROM comments
                WHERE post_id = ?
                ORDER BY created_at
            """, (post_id,))

            comments = cursor.fetchall()
            print(f"💬 Found {len(comments)} comments")

            if len(comments) == 0:
                # Update status to 'no-comments' instead of returning error
                print("📝 No comments found - updating status to 'no-comments'")
                cursor.execute("""
                    UPDATE comment_group_drift
                    SET analyzed_by = 'no-comments',
                        has_drift = 0,
                        analyzed_at = ?
                    WHERE post_id = ?
                """, (datetime.utcnow().isoformat(), post_id))

                # Check if record exists, create if not
                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO comment_group_drift
                        (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                        VALUES (?, 0, NULL, ?, 'no-comments', ?)
                    """, (post_id, datetime.utcnow().isoformat(), expert_id))
                    print(f"📝 Created new 'no-comments' record for post_id {post_id}")
                else:
                    print(f"📝 Updated existing record to 'no-comments' for post_id {post_id}")

                conn.commit()

                return {
                    "success": True,
                    "post_id": post_id,
                    "telegram_message_id": telegram_message_id,
                    "expert_id": expert_id,
                    "comments_count": 0,
                    "analysis_result": {
                        "has_drift": False,
                        "status": "no-comments"
                    }
                }

            # Format comments for analysis
            comments_text = "\n".join([
                f"- {author}: {text}"
                for _, text, author, _ in comments
            ])

            print(f"\n📊 Comments to analyze:")
            for comment_id, text, author, created_at in comments:
                print(f"  • {author}: {text[:60]}...")

            # Perform drift analysis
            print(f"\n🤖 Analyzing drift with {self.model}...")
            result = await self.analyze_drift(message_text, comments_text)

            # Update database with results
            await self.update_drift_analysis(cursor, post_id, result, expert_id)
            conn.commit()

            print(f"\n✅ Analysis complete for post_id {post_id}")
            print(f"📈 Has drift: {result.get('has_drift', False)}")
            print(f"🎯 Confidence: {result.get('confidence', 'unknown')}")

            if result.get('drift_topics'):
                print(f"🏷️  Drift topics found: {len(result['drift_topics'])}")
                for i, topic in enumerate(result['drift_topics'], 1):
                    print(f"  {i}. {topic.get('topic', 'N/A')}")

            return {
                "success": True,
                "post_id": post_id,
                "telegram_message_id": telegram_message_id,
                "expert_id": expert_id,
                "comments_count": len(comments),
                "analysis_result": result
            }

        except Exception as e:
            print(f"❌ Error analyzing post {post_id}: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    async def analyze_drift(self, post_text: str, comments_text: str) -> Dict[str, Any]:
        """Analyze drift using Claude Sonnet 4.5."""

        prompt = f"""Analyze this Telegram post and its comments to determine if the discussion DRIFTED to other topics.

POST (anchor):
{post_text[:500]}...

COMMENTS:
{comments_text}

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

Return JSON:
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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        # Extract JSON from response (handle cases where model adds reasoning after JSON)
        json_start = content.find('{')
        json_end = content.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_content = content[json_start:json_end]
            print(f"🔍 Extracted JSON:")
            print(json_content)

            result = json.loads(json_content)
            return result
        else:
            print(f"❌ Could not find valid JSON in response")
            print(f"🔍 Full response:")
            print(content)
            raise ValueError("No valid JSON found in response")

    async def update_drift_analysis(self, cursor, post_id: int, result: Dict[str, Any], expert_id: str):
        """Update drift analysis result in database."""

        # Create proper JSON structure for drift_topics
        drift_topics_json = None
        if result.get("drift_topics"):
            # CRITICAL: Save as JSON object with has_drift and drift_topics fields
            drift_data = {
                "has_drift": result.get("has_drift", False),
                "drift_topics": result["drift_topics"]
            }
            drift_topics_json = json.dumps(drift_data, ensure_ascii=False)

        # Check if record exists
        cursor.execute(
            "SELECT id FROM comment_group_drift WHERE post_id = ?",
            (post_id,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE comment_group_drift
                SET has_drift = ?,
                    drift_topics = ?,
                    analyzed_at = ?,
                    analyzed_by = ?
                WHERE post_id = ?
            """, (
                result.get("has_drift", False),
                drift_topics_json,
                datetime.utcnow().isoformat(),
                "drift-on-synced",  # This is the key marker for drift-on-synced agent
                post_id
            ))
            print(f"📝 Updated existing drift record for post_id {post_id}")
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO comment_group_drift
                (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                post_id,
                result.get("has_drift", False),
                drift_topics_json,
                datetime.utcnow().isoformat(),
                "drift-on-synced",
                expert_id
            ))
            print(f"📝 Created new drift record for post_id {post_id}")


async def main():
    """Main execution function."""
    if len(sys.argv) != 2:
        print("Usage: python drift_on_synced_single.py <post_id>")
        sys.exit(1)

    post_id = int(sys.argv[1])

    # Check environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment")
        sys.exit(1)

    print("🚀 Drift-on-Synced Agent Starting...")
    print(f"📁 Database: {DATABASE_PATH}")
    print(f"🔑 API Key: {'✓' if api_key else '✗'}")

    # Run analysis
    agent = DriftOnSyncedAgent(api_key)
    result = await agent.analyze_specific_post(post_id)

    if result.get("success"):
        print(f"\n🎉 SUCCESS: Drift analysis completed for post_id {post_id}")
        print(f"📊 Summary: {result['comments_count']} comments analyzed")
        print(f"🏷️  Drift detected: {result['analysis_result'].get('has_drift', False)}")
    else:
        print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())