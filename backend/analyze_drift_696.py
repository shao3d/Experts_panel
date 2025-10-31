#!/usr/bin/env python3
"""
Drift analysis for specific post_id 696 (neuraldeep)
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any

def get_database_connection():
    """Get database connection"""
    db_path = '/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_post_content(conn, post_id: int) -> Dict[str, Any]:
    """Get post content for analysis"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text, created_at, channel_id
        FROM posts
        WHERE post_id = ?
    """, (post_id,))
    row = cursor.fetchone()
    return dict(row) if row else {}

def get_comments_for_post(conn, post_id: int) -> List[Dict[str, Any]]:
    """Get all comments for a post"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT comment_id, comment_text, author_name, created_at
        FROM comments
        WHERE post_id = ?
        ORDER BY created_at
    """, (post_id,))
    return [dict(row) for row in cursor.fetchall()]

def analyze_drift_for_group(post_content: Dict, comments: List[Dict]) -> Dict[str, Any]:
    """
    Analyze drift for a comment group
    Using the same logic as the main drift-on-synced agent
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    post_text = post_content.get('message_text', '')
    if not post_text:
        return {"has_drift": 0, "drift_topics": None}

    # Use the same simple heuristic analysis as the main script
    return simple_drift_analysis(post_text, comments)

def simple_drift_analysis(post_text: str, comments: List[Dict]) -> Dict[str, Any]:
    """
    Simple heuristic-based drift analysis (same as main script)
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    # Extract key terms from post
    post_words = set(post_text.lower().split())

    # Look for topic indicators in comments
    drift_indicators = [
        'what about', 'how does', 'what if', 'why not', 'have you considered',
        'actually', 'in my experience', 'this reminds me of', 'on the other hand',
        'but what about', 'however', 'although', 'meanwhile', 'by the way'
    ]

    # Check for question marks and discussion indicators
    has_questions = any('?' in c['comment_text'] for c in comments)
    has_discussion_indicators = any(
        any(indicator in c['comment_text'].lower() for indicator in drift_indicators)
        for c in comments
    )

    # Simple heuristic: if comments have questions or discussion indicators, mark as drift
    has_drift = 1 if (has_questions or has_discussion_indicators) else 0

    if has_drift:
        # Extract simple drift topics
        drift_topics = []
        for comment in comments[:3]:  # Take first 3 comments as topics
            comment_text = comment['comment_text']
            words = comment_text.lower().split()
            # Find words not in post
            new_words = [w for w in words if w not in post_words and len(w) > 3][:3]
            if new_words:
                drift_topics.append({
                    "topic": comment_text[:100] + "..." if len(comment_text) > 100 else comment_text,
                    "keywords": new_words,
                    "key_phrases": [comment_text[:50] + "..."],
                    "context": f"From comment by {comment['author_name']}"
                })

        return {"has_drift": 1, "drift_topics": drift_topics[:3]}  # Max 3 topics
    else:
        return {"has_drift": 0, "drift_topics": None}

def update_drift_record(conn, post_id: int, analysis_result: Dict[str, Any]):
    """Update drift analysis result in database"""
    cursor = conn.cursor()

    # Proper JSON format for drift_topics field
    if analysis_result['drift_topics']:
        drift_topics_json = json.dumps({
            "has_drift": True,
            "drift_topics": analysis_result['drift_topics']
        })
    else:
        drift_topics_json = None

    cursor.execute("""
        UPDATE comment_group_drift
        SET has_drift = ?,
            drift_topics = ?,
            analyzed_by = 'drift-on-synced',
            analyzed_at = datetime('now')
        WHERE post_id = ?
    """, (analysis_result['has_drift'], drift_topics_json, post_id))

    conn.commit()

def main():
    """Analyze drift for post_id 696"""
    post_id = 696
    print(f"🎯 Analyzing drift for post_id {post_id}")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Get post content and comments
        post_content = get_post_content(conn, post_id)
        comments = get_comments_for_post(conn, post_id)

        print(f"📄 Post content:")
        print(f"  {post_content.get('message_text', 'N/A')[:200]}...")
        print(f"\n💬 Found {len(comments)} comments:")

        for comment in comments:
            print(f"  - {comment['author_name']}: {comment['comment_text']}")

        print(f"\n🔄 Analyzing drift...")

        # Analyze drift
        analysis_result = analyze_drift_for_group(post_content, comments)

        print(f"\n📊 Analysis result:")
        print(f"  Has drift: {analysis_result['has_drift']}")

        if analysis_result['drift_topics']:
            print(f"  Drift topics ({len(analysis_result['drift_topics'])}):")
            for i, topic in enumerate(analysis_result['drift_topics'], 1):
                print(f"    {i}. {topic['topic'][:80]}...")
                print(f"       Keywords: {topic['keywords']}")
                print(f"       Context: {topic['context']}")
        else:
            print(f"  No drift topics detected")

        # Update database
        update_drift_record(conn, post_id, analysis_result)
        print(f"\n✅ Database updated successfully!")

        # Show final database state
        cursor = conn.cursor()
        cursor.execute("""
            SELECT has_drift, analyzed_by, analyzed_at, drift_topics
            FROM comment_group_drift
            WHERE post_id = ?
        """, (post_id,))
        result = cursor.fetchone()

        print(f"\n📋 Database record after update:")
        print(f"  has_drift: {result['has_drift']}")
        print(f"  analyzed_by: {result['analyzed_by']}")
        print(f"  analyzed_at: {result['analyzed_at']}")
        print(f"  drift_topics: {result['drift_topics'][:100] if result['drift_topics'] else 'NULL'}...")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    main()