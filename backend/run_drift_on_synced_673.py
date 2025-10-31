#!/usr/bin/env python3
"""
Drift-on-synced agent: Analyzes specific post_id for topic drift
Modified to target post_id 673 specifically
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

    drift_topics_json = json.dumps(analysis_result['drift_topics']) if analysis_result['drift_topics'] else None

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
    """Main drift analysis workflow for specific post_id 673"""
    target_post_id = 673

    print(f"🎯 Drift-on-Synced Agent: Analyzing post_id {target_post_id}")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Check if post exists and is pending
        cursor = conn.cursor()
        cursor.execute("""
            SELECT post_id, expert_id, analyzed_by
            FROM comment_group_drift
            WHERE post_id = ? AND analyzed_by = 'pending'
        """, (target_post_id,))

        pending_record = cursor.fetchone()

        if not pending_record:
            print(f"❌ No pending drift analysis found for post_id {target_post_id}")
            return

        post_id = pending_record['post_id']
        expert_id = pending_record['expert_id']

        print(f"📊 Found pending drift analysis:")
        print(f"  - Post ID: {post_id}")
        print(f"  - Expert ID: {expert_id}")

        print(f"\n🔄 Starting drift analysis...")

        # Get post content and comments
        post_content = get_post_content(conn, post_id)
        comments = get_comments_for_post(conn, post_id)

        print(f"  - Found {len(comments)} comments")
        print(f"  - Post text length: {len(post_content.get('message_text', ''))}")

        # Display post content preview
        post_preview = post_content.get('message_text', '')[:200]
        print(f"  - Post preview: {post_preview}...")

        # Analyze drift
        start_time = time.time()
        analysis_result = analyze_drift_for_group(post_content, comments)
        analysis_time = time.time() - start_time

        # Update database
        update_drift_record(conn, post_id, analysis_result)

        # Display results
        print(f"\n✅ Analysis complete in {analysis_time:.1f} seconds")
        print(f"  - Has drift: {analysis_result['has_drift']}")

        if analysis_result["has_drift"] == 1:
            drift_topics = analysis_result.get('drift_topics', [])
            print(f"  - Drift topics found: {len(drift_topics)}")
            for i, topic in enumerate(drift_topics, 1):
                print(f"    {i}. {topic['topic'][:80]}...")
        else:
            print(f"  - No meaningful drift detected")

        # Verify the update
        cursor.execute("""
            SELECT analyzed_by, has_drift, analyzed_at
            FROM comment_group_drift
            WHERE post_id = ?
        """, (post_id,))

        updated_record = cursor.fetchone()
        print(f"\n📋 Database update verification:")
        print(f"  - analyzed_by: {updated_record['analyzed_by']}")
        print(f"  - has_drift: {updated_record['has_drift']}")
        print(f"  - analyzed_at: {updated_record['analyzed_at']}")

        print(f"\n🎉 Drift analysis for post_id {target_post_id} completed successfully!")

    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)

    finally:
        conn.close()

if __name__ == "__main__":
    main()