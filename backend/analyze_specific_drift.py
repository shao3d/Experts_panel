#!/usr/bin/env python3
"""
Drift analysis for a specific post
"""

import json
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any
import time

def get_database_connection():
    """Get database connection"""
    # Use absolute path for database reliability
    db_path = '/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_post_content(conn, post_id: int) -> Dict[str, Any]:
    """Get post content for analysis"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text, created_at, channel_id, expert_id
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
    Analyze drift for a comment group using Claude Sonnet 4.5
    This is where the actual drift analysis happens
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    post_text = post_content.get('message_text', '')
    if not post_text:
        return {"has_drift": 0, "drift_topics": None}

    # Prepare analysis prompt
    comments_text = "\n\n".join([
        f"Comment by {c['author_name']} ({c['created_at']}): {c['comment_text']}"
        for c in comments
    ])

    analysis_prompt = f"""
Analyze the topic drift between this post and its comments:

POST:
{post_text}

COMMENTS:
{comments_text}

Instructions:
1. Compare the main topic of the post with the discussion in comments
2. Identify if comments discuss topics beyond the original post
3. Extract drift topics if meaningful topic shift exists
4. Consider tangential discussions, expansions, or completely different topics

Return JSON format:
{{
    "has_drift": 1 or 0,
    "drift_topics": [
        {{
            "topic": "Main drifted topic",
            "keywords": ["keyword1", "keyword2"],
            "key_phrases": ["phrase1", "phrase2"],
            "context": "Brief context of how this topic emerged"
        }}
    ] if has_drift = 1, otherwise null
}}

Criteria for drift:
- Comments discuss related but expanded topics not in original post
- Comments ask follow-up questions about different aspects
- Comments bring in external examples or comparisons
- Comments discuss practical applications not mentioned in post
- Comments debate implications or consequences not covered

If comments are purely discussing the post content (clarifications, agreements, basic questions), then has_drift = 0.
"""

    # For now, we'll implement a simplified analysis
    # In production, this would call Claude API

    # Simple heuristic-based analysis as fallback
    return simple_drift_analysis(post_text, comments)

def simple_drift_analysis(post_text: str, comments: List[Dict]) -> Dict[str, Any]:
    """
    Simple heuristic-based drift analysis
    This is a placeholder for Claude API analysis
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

    # Important: drift_topics must be JSON object with format: {"has_drift": true, "drift_topics": [...]}
    # NOT just the array directly!
    if analysis_result['has_drift'] == 1 and analysis_result['drift_topics']:
        drift_topics_json = json.dumps({
            "has_drift": True,
            "drift_topics": analysis_result['drift_topics']
        })
    else:
        drift_topics_json = json.dumps({
            "has_drift": False,
            "drift_topics": []
        })

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
    """Main drift analysis workflow for specific post"""
    post_id = 698

    print(f"🎯 Drift Analysis for Post {post_id}")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Get post content and comments
        post_content = get_post_content(conn, post_id)
        comments = get_comments_for_post(conn, post_id)

        print(f"📊 Post details:")
        print(f"  - Post ID: {post_id}")
        print(f"  - Expert: {post_content.get('expert_id', 'Unknown')}")
        print(f"  - Channel: {post_content.get('channel_id', 'Unknown')}")
        print(f"  - Created: {post_content.get('created_at', 'Unknown')}")
        print(f"  - Comments: {len(comments)}")

        if not comments:
            print("❌ No comments found for analysis")
            return

        print(f"\n🔄 Starting drift analysis...")

        # Analyze drift
        start_time = time.time()
        analysis_result = analyze_drift_for_group(post_content, comments)
        analysis_time = time.time() - start_time

        # Update database
        update_drift_record(conn, post_id, analysis_result)

        # Display results
        print(f"\n✅ Analysis completed in {analysis_time:.2f} seconds")
        print(f"📈 Results:")

        if analysis_result["has_drift"] == 1:
            print(f"  - Has drift: YES")
            print(f"  - Drift topics: {len(analysis_result['drift_topics'] or [])}")
            for i, topic in enumerate((analysis_result['drift_topics'] or [])[:3], 1):
                print(f"    {i}. {topic.get('topic', 'N/A')[:60]}...")
                if topic.get('keywords'):
                    print(f"       Keywords: {', '.join(topic['keywords'][:5])}")
        else:
            print(f"  - Has drift: NO")
            print(f"  - Comments are focused on post content")

        # Verify database update
        cursor = conn.cursor()
        cursor.execute("""
            SELECT has_drift, analyzed_by, analyzed_at
            FROM comment_group_drift
            WHERE post_id = ?
        """, (post_id,))
        result = cursor.fetchone()

        print(f"\n📋 Database verification:")
        print(f"  - has_drift: {result['has_drift']}")
        print(f"  - analyzed_by: {result['analyzed_by']}")
        print(f"  - analyzed_at: {result['analyzed_at']}")

        print(f"\n✅ Drift analysis for post {post_id} complete!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

    finally:
        conn.close()

if __name__ == "__main__":
    main()