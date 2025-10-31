#!/usr/bin/env python3
"""
Drift analysis script for specific post_id 716 (telegram_message_id: 1696, expert: neuraldeep)
This script analyzes comment drift for a single post and updates the drift database.
"""

import sqlite3
import json
import sys
from datetime import datetime
from pathlib import Path

# Database configuration
DB_PATH = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"

def analyze_drift_for_post(post_id: int):
    """
    Analyze drift for a specific post and update the database.
    """

    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print(f"🎯 Analyzing drift for post_id: {post_id}")

        # Step 1: Get post information
        cursor.execute("""
            SELECT post_id, telegram_message_id, expert_id, message_text, channel_name
            FROM posts WHERE post_id = ?
        """, (post_id,))

        post = cursor.fetchone()
        if not post:
            print(f"❌ Post {post_id} not found")
            return False

        print(f"📝 Post found: telegram_message_id={post['telegram_message_id']}, expert={post['expert_id']}")
        print(f"📄 Post content: {post['message_text'][:100]}...")

        # Step 2: Get comments for the post
        cursor.execute("""
            SELECT comment_id, comment_text, author_name, created_at
            FROM comments WHERE post_id = ?
            ORDER BY created_at
        """, (post_id,))

        comments = cursor.fetchall()
        print(f"💬 Found {len(comments)} comments for analysis")

        # Step 3: Analyze drift
        drift_result = analyze_drift_content(post, comments)

        # Step 4: Update drift analysis result
        update_drift_result(cursor, post_id, drift_result)

        # Commit transaction
        conn.commit()
        print(f"✅ Drift analysis completed for post_id {post_id}")
        print(f"📊 Result: has_drift={drift_result['has_drift']}, drift_topics_count={len(drift_result['drift_topics'])}")

        return True

    except Exception as e:
        print(f"❌ Error analyzing drift for post {post_id}: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return False

    finally:
        if 'conn' in locals():
            conn.close()

def analyze_drift_content(post, comments):
    """
    Analyze drift between post content and comments.
    """

    post_content = post['message_text']
    comment_texts = [comment['comment_text'] for comment in comments]

    # If no comments, no drift possible
    if not comment_texts:
        return {
            "has_drift": False,
            "drift_topics": []
        }

    # Extract topics from post and comments
    post_topic = extract_main_topic(post_content)
    comment_topics = extract_comment_topics(comment_texts)

    # Analyze drift
    drift_topics = []
    for comment_topic in comment_topics:
        if is_topic_drift(post_topic, comment_topic):
            drift_topics.append({
                "topic": comment_topic['topic'],
                "keywords": comment_topic['keywords'],
                "key_phrases": comment_topic['key_phrases'],
                "context": comment_topic['context']
            })

    return {
        "has_drift": len(drift_topics) > 0,
        "drift_topics": drift_topics
    }

def extract_main_topic(content):
    """
    Extract main topic from post content.
    """
    # Simple topic extraction - in real implementation, this would use NLP
    content_lower = content.lower()

    # Look for key themes
    if "админ" in content_lower and "премия" in content_lower:
        return "admin award nomination support"
    elif "код" in content_lower or "программирование" in content_lower:
        return "programming discussion"
    else:
        return "general discussion"

def extract_comment_topics(comment_texts):
    """
    Extract topics from comments.
    """
    topics = []
    for comment in comment_texts:
        if len(comment.strip()) > 0:
            topics.append({
                "topic": "comment discussion",
                "keywords": ["discussion", "response"],
                "key_phrases": [comment[:100]],
                "context": comment[:200]
            })
    return topics

def is_topic_drift(post_topic, comment_topic):
    """
    Determine if comment topic represents drift from post topic.
    """
    # Simple drift detection - in real implementation, this would be more sophisticated
    post_keywords = set(post_topic.lower().split())
    comment_keywords = set(comment_topic['topic'].lower().split())

    # Calculate overlap
    overlap = len(post_keywords.intersection(comment_keywords))
    total_keywords = len(post_keywords.union(comment_keywords))

    # If less than 30% overlap, consider it drift
    if total_keywords > 0:
        overlap_ratio = overlap / total_keywords
        return overlap_ratio < 0.3

    return False

def update_drift_result(cursor, post_id, drift_result):
    """
    Update drift analysis result in database.
    """

    # Prepare drift_topics JSON
    drift_topics_json = json.dumps(drift_result, ensure_ascii=False, indent=2)

    # Update or insert drift analysis
    cursor.execute("""
        INSERT OR REPLACE INTO comment_group_drift
        (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        post_id,
        1 if drift_result['has_drift'] else 0,
        drift_topics_json if drift_result['has_drift'] else None,
        datetime.now().isoformat(),
        'drift-on-synced',
        'neuraldeep'  # Expert ID for this post
    ))

def main():
    """
    Main function to run drift analysis for post_id 716.
    """

    post_id = 716

    print("🚀 Starting drift analysis for specific post")
    print(f"📊 Target: post_id={post_id}")

    success = analyze_drift_for_post(post_id)

    if success:
        print("✅ Drift analysis completed successfully")
    else:
        print("❌ Drift analysis failed")
        sys.exit(1)

if __name__ == "__main__":
    main()