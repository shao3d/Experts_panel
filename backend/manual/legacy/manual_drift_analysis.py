#!/usr/bin/env python3
"""
Drift Analysis Script for Processing Pending Comment Groups

This script processes pending comment groups from the comment_group_drift table,
performs drift analysis comparing original post topics with comment discussions,
and updates the database with structured drift topics.
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="drift_analysis",
)
DB_PATH = get_sqlite_db_path(BACKEND_DIR)

def get_database_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn

def get_pending_groups(limit: int = 5) -> List[Dict[str, Any]]:
    """Get pending comment groups for drift analysis."""
    conn = get_database_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT post_id, expert_id
        FROM comment_group_drift
        WHERE analyzed_by = 'pending'
        ORDER BY post_id
        LIMIT ?
    """, (limit,))

    groups = [{"post_id": row["post_id"], "expert_id": row["expert_id"]} for row in cursor.fetchall()]
    conn.close()
    return groups

def get_post_with_comments(post_id: int) -> Optional[Dict[str, Any]]:
    """Get post details and all comments for a given post."""
    conn = get_database_connection()
    cursor = conn.cursor()

    # Get post details
    cursor.execute("""
        SELECT message_text, created_at, telegram_message_id, view_count,
               forward_count, reply_count, expert_id
        FROM posts
        WHERE post_id = ?
    """, (post_id,))

    post = cursor.fetchone()
    if not post:
        conn.close()
        return None

    # Get comments
    cursor.execute("""
        SELECT comment_id, comment_text, author_name, created_at
        FROM comments
        WHERE post_id = ?
        ORDER BY created_at
    """, (post_id,))

    comments = [
        {
            "comment_id": row["comment_id"],
            "comment_text": row["comment_text"],
            "author_name": row["author_name"],
            "created_at": row["created_at"]
        }
        for row in cursor.fetchall()
    ]

    post_data = {
        "post_id": post_id,
        "message_text": post["message_text"],
        "created_at": post["created_at"],
        "telegram_message_id": post["telegram_message_id"],
        "view_count": post["view_count"],
        "forward_count": post["forward_count"],
        "reply_count": post["reply_count"],
        "expert_id": post["expert_id"],
        "comments": comments
    }

    conn.close()
    return post_data

def analyze_drift(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze drift between post topic and comment discussions.

    This function compares the original post topic with comment discussions
    to identify topic shifts, expansions, tangents, and extract structured drift topics.
    """

    post_text = post_data["message_text"]
    comments = post_data["comments"]
    post_id = post_data["post_id"]

    if not comments:
        return {
            "has_drift": False,
            "drift_topics": []
        }

    # Analyze post topic
    post_topic_lower = post_text.lower()

    # Common drift patterns to look for
    drift_indicators = [
        "implementation", "timeline", "cost", "how long", "сколько", "проблема", "issue",
        "bug", "ошибка", "difficult", "сложно", "question", "вопрос", "alternatives",
        "experience", "опыт", "comparison", "сравнение", "tools", "инструменты",
        "architecture", "архитектура", "database", "база данных", "api", "framework"
    ]

    # Extract drift topics from comments
    drift_topics = []

    # Group comments by themes
    theme_comments = {}

    for comment in comments:
        comment_text = comment["comment_text"].lower()
        author = comment["author_name"]

        # Check for drift indicators
        for indicator in drift_indicators:
            if indicator in comment_text:
                if indicator not in theme_comments:
                    theme_comments[indicator] = []
                theme_comments[indicator].append({
                    "text": comment["comment_text"],
                    "author": author,
                    "indicator": indicator
                })
                break

    # Create structured drift topics
    for theme, comment_list in theme_comments.items():
        if len(comment_list) >= 1:  # At least one comment on the theme
            # Extract keywords and key phrases
            all_text = " ".join([c["text"] for c in comment_list])

            # Simple keyword extraction (common words related to the theme)
            keywords = [theme]
            if "implementation" in theme or "как" in all_text:
                keywords.extend(["implementation", "how to", "как сделать"])
            if "timeline" in theme or "сколько" in all_text or "долго" in all_text:
                keywords.extend(["timeline", "duration", "сколько времени"])
            if "cost" in theme or "стоимость" in all_text:
                keywords.extend(["cost", "price", "стоимость"])
            if "problem" in theme or "проблема" in all_text or "issue" in all_text:
                keywords.extend(["problem", "issue", "проблема", "сложность"])
            if "experience" in theme or "опыт" in all_text:
                keywords.extend(["experience", "опыт", "practice"])
            if "comparison" in theme or "сравнение" in all_text:
                keywords.extend(["comparison", "alternatives", "сравнение", "альтернативы"])

            # Extract key phrases (first few sentences from representative comments)
            key_phrases = []
            for comment in comment_list[:3]:  # Take first 3 comments as examples
                text = comment["text"]
                # Take first sentence or first 100 chars
                if "." in text:
                    first_sentence = text.split(".")[0] + "."
                else:
                    first_sentence = text[:100] + ("..." if len(text) > 100 else "")
                key_phrases.append(first_sentence)

            # Create context from comment discussions
            context = f"Discussion involving {len(comment_list)} comments about {theme}. "
            if len(comment_list) > 0:
                sample_authors = list(set([c["author"] for c in comment_list[:3]]))
                context += f"Participants include: {', '.join(sample_authors)}"

            drift_topic = {
                "topic": f"Discussion drift towards {theme}",
                "keywords": keywords,
                "key_phrases": key_phrases,
                "context": context
            }

            drift_topics.append(drift_topic)

    # Determine if meaningful drift exists
    has_drift = len(drift_topics) > 0

    # Special handling for posts with many comments discussing implementation details
    if len(comments) >= 10 and not has_drift:
        # Look for technical discussions
        technical_keywords = ["database", "api", "architecture", "code", "implementation"]
        for comment in comments:
            comment_text = comment["comment_text"].lower()
            if any(keyword in comment_text for keyword in technical_keywords):
                has_drift = True
                drift_topics.append({
                    "topic": "Technical implementation discussion",
                    "keywords": technical_keywords,
                    "key_phrases": [comment["comment_text"][:150] + "..."],
                    "context": f"Extended technical discussion with {len(comments)} comments"
                })
                break

    return {
        "has_drift": has_drift,
        "drift_topics": drift_topics
    }

def update_drift_analysis(post_id: int, drift_result: Dict[str, Any]) -> bool:
    """Update the database with drift analysis results."""
    conn = get_database_connection()
    cursor = conn.cursor()

    try:
        # Create the JSON structure for drift_topics
        drift_topics_json = json.dumps(drift_result, ensure_ascii=False)

        cursor.execute("""
            UPDATE comment_group_drift
            SET has_drift = ?,
                drift_topics = ?,
                analyzed_by = 'drift-on-synced',
                analyzed_at = datetime('now')
            WHERE post_id = ?
        """, (1 if drift_result["has_drift"] else 0, drift_topics_json, post_id))

        conn.commit()
        print(f"   ✅ Successfully updated post {post_id} in database")
        return True
    except Exception as e:
        print(f"   ❌ Error updating post {post_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def process_pending_groups(limit: int = 5) -> Dict[str, Any]:
    """Process pending comment groups for drift analysis."""

    print(f"🎯 Starting drift analysis for up to {limit} pending groups...")

    # Get pending groups
    pending_groups = get_pending_groups(limit)

    if not pending_groups:
        return {
            "total_processed": 0,
            "success": True,
            "message": "No pending groups found"
        }

    results = {
        "total_processed": 0,
        "with_drift": 0,
        "without_drift": 0,
        "by_expert": {},
        "groups": []
    }

    for group in pending_groups:
        post_id = group["post_id"]
        expert_id = group["expert_id"]

        print(f"\n📊 Processing Post {post_id} (Expert: {expert_id})")

        # Initialize expert stats if not exists
        if expert_id not in results["by_expert"]:
            results["by_expert"][expert_id] = {
                "processed": 0,
                "with_drift": 0,
                "without_drift": 0
            }

        # Get post data
        post_data = get_post_with_comments(post_id)
        if not post_data:
            print(f"❌ Post {post_id} not found, skipping...")
            continue

        # Perform drift analysis
        print(f"   Analyzing {len(post_data['comments'])} comments...")
        drift_result = analyze_drift(post_data)

        # Update database
        success = update_drift_analysis(post_id, drift_result)

        if success:
            results["total_processed"] += 1
            results["by_expert"][expert_id]["processed"] += 1

            if drift_result["has_drift"]:
                results["with_drift"] += 1
                results["by_expert"][expert_id]["with_drift"] += 1
                print(f"   ✅ Drift detected: {len(drift_result['drift_topics'])} topics")
            else:
                results["without_drift"] += 1
                results["by_expert"][expert_id]["without_drift"] += 1
                print(f"   ✅ No meaningful drift detected")

            # Add group result
            results["groups"].append({
                "post_id": post_id,
                "expert_id": expert_id,
                "has_drift": drift_result["has_drift"],
                "drift_topics_count": len(drift_result["drift_topics"]),
                "comments_count": len(post_data["comments"])
            })
        else:
            print(f"   ❌ Failed to update database")

    results["success"] = True
    return results

def main():
    """Main function to process pending comment groups."""
    try:
        # Process a batch of pending groups
        results = process_pending_groups(limit=5)

        print(f"\n📈 Drift Analysis Summary:")
        print(f"   Total processed: {results['total_processed']}")
        print(f"   With drift: {results['with_drift']}")
        print(f"   Without drift: {results['without_drift']}")

        if results["by_expert"]:
            print(f"\n👥 By Expert:")
            for expert_id, stats in results["by_expert"].items():
                print(f"   {expert_id}: {stats['processed']} processed ({stats['with_drift']} with drift)")

        return results

    except Exception as e:
        print(f"❌ Error in main: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    main()
