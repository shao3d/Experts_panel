"""
Analyze comment groups for topic drift.

This script:
1. Loads all comment groups from database
2. For each group, analyzes if comments drift from post topic
3. Extracts drift_topics (topic, keywords, key_phrases, context)
4. Saves results to comment_group_drift table

Usage:
    python analyze_drift.py [--batch-size 10] [--show-ambiguous]
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse

from dotenv import load_dotenv
from sqlalchemy.orm import Session
from openai import AsyncOpenAI

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.base import SessionLocal
from src.models.post import Post
from src.models.comment import Comment

# Load environment
load_dotenv()


class DriftAnalyzer:
    """Analyzes comment groups for topic drift using Claude Sonnet."""

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4-5"):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.analyzed_count = 0
        self.drift_found = 0
        self.ambiguous_cases = []

    async def analyze_group(
        self,
        post: Post,
        comments: List[Comment]
    ) -> Dict[str, Any]:
        """Analyze a single comment group for drift.

        Returns:
            {
                "has_drift": bool,
                "drift_topics": [...] or None,
                "confidence": "high" | "medium" | "low"
            }
        """
        # Format data for analysis
        comments_text = "\n".join([
            f"- {c.author_name}: {c.comment_text}"
            for c in comments
        ])

        prompt = f"""Analyze this Telegram post and its comments to determine if the discussion DRIFTED to other topics.

POST (anchor):
{post.message_text[:500]}...

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

        result = json.loads(response.choices[0].message.content)
        return result

    async def analyze_all_groups(
        self,
        db: Session,
        batch_size: int = 10,
        show_ambiguous: bool = False
    ):
        """Analyze all comment groups and save results."""

        # Get all posts with comments
        posts_with_comments = db.query(Post).join(
            Comment, Post.post_id == Comment.post_id
        ).filter(
            Comment.telegram_comment_id.isnot(None)
        ).distinct().all()

        total = len(posts_with_comments)
        print(f"\n📊 Found {total} posts with Telegram comments")
        print(f"⚙️  Batch size: {batch_size}")
        print(f"🤖 Model: {self.model}")
        print("=" * 60 + "\n")

        for i, post in enumerate(posts_with_comments, 1):
            # Get comments for this post
            comments = db.query(Comment).filter(
                Comment.post_id == post.post_id,
                Comment.telegram_comment_id.isnot(None)
            ).order_by(Comment.created_at).all()

            print(f"[{i}/{total}] Post #{post.telegram_message_id} ({len(comments)} comments)... ", end="")

            # Analyze
            result = await self.analyze_group(post, comments)

            has_drift = result.get("has_drift", False)
            confidence = result.get("confidence", "low")

            # Track ambiguous cases
            if confidence == "low" or (confidence == "medium" and has_drift):
                self.ambiguous_cases.append({
                    "post_id": post.telegram_message_id,
                    "post_preview": post.message_text[:80] + "...",
                    "confidence": confidence,
                    "result": result
                })

            if has_drift:
                topics_count = len(result.get("drift_topics", []))
                print(f"✅ DRIFT ({confidence} confidence, {topics_count} topics)")
                self.drift_found += 1
            else:
                print(f"— no drift ({confidence} confidence)")

            # Save to database
            self._save_result(db, post.post_id, result)

            self.analyzed_count += 1

            # Commit in batches
            if i % batch_size == 0:
                db.commit()
                print(f"\n💾 Batch commit at {i}/{total}\n")

        # Final commit
        db.commit()

        # Show summary
        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE!")
        print("=" * 60)
        print(f"📊 Total analyzed: {self.analyzed_count}")
        print(f"🎯 Drift found: {self.drift_found} ({self.drift_found/self.analyzed_count*100:.1f}%)")
        print(f"❓ Ambiguous cases: {len(self.ambiguous_cases)}")

        if show_ambiguous and self.ambiguous_cases:
            print("\n" + "=" * 60)
            print("❓ AMBIGUOUS CASES FOR REVIEW:")
            print("=" * 60)
            for case in self.ambiguous_cases:
                print(f"\nPost #{case['post_id']} ({case['confidence']} confidence):")
                print(f"  {case['post_preview']}")
                print(f"  Drift: {case['result'].get('has_drift')}")
                if case['result'].get('drift_topics'):
                    for topic in case['result']['drift_topics']:
                        print(f"    - {topic.get('topic', 'N/A')}")

    def _save_result(self, db: Session, post_id: int, result: Dict[str, Any]):
        """Save drift analysis result to database."""
        # Per docs, drift_topics column must store the FULL analysis object,
        # not just the array of topics, to match existing DB schema.
        # See .claude/agents/drift_on_synced.md for the canonical format.
        drift_topics_json = json.dumps(result, ensure_ascii=False) if result else None

        # Get expert_id from post
        post = db.query(Post).filter(Post.post_id == post_id).first()
        expert_id = post.expert_id if post else None

        # Check if exists
        existing = db.execute(
            "SELECT id FROM comment_group_drift WHERE post_id = ?",
            (post_id,)
        ).fetchone()

        if existing:
            # Update (preserve expert_id)
            db.execute(
                """UPDATE comment_group_drift
                   SET has_drift = ?, drift_topics = ?, analyzed_at = ?, analyzed_by = ?
                   WHERE post_id = ?""",
                (
                    result.get("has_drift", False),
                    drift_topics_json,
                    datetime.utcnow(),
                    "sonnet-4.5",
                    post_id
                )
            )
        else:
            # Insert with expert_id
            db.execute(
                """INSERT INTO comment_group_drift
                   (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    post_id,
                    result.get("has_drift", False),
                    drift_topics_json,
                    datetime.utcnow(),
                    "sonnet-4.5",
                    expert_id
                )
            )


async def main():
    parser = argparse.ArgumentParser(description="Analyze comment groups for topic drift")
    parser.add_argument("--batch-size", type=int, default=10, help="Commit batch size")
    parser.add_argument("--show-ambiguous", action="store_true", help="Show ambiguous cases")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment")
        sys.exit(1)

    # Create drift table if not exists
    db = SessionLocal()
    try:
        # Run migration
        migration_path = Path(__file__).parent / "migrations" / "001_create_comment_group_drift.sql"
        if migration_path.exists():
            with open(migration_path) as f:
                db.execute(f.read())
            db.commit()
            print("✅ Migration applied: comment_group_drift table ready\n")
    except Exception as e:
        print(f"⚠️  Migration warning: {e}\n")

    # Run analysis
    analyzer = DriftAnalyzer(api_key)
    await analyzer.analyze_all_groups(
        db,
        batch_size=args.batch_size,
        show_ambiguous=args.show_ambiguous
    )

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
