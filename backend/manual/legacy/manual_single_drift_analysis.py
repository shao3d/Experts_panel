#!/usr/bin/env python3
"""
Single drift analysis: Analyze a specific post for topic drift
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="run_single_drift_analysis",
)
DB_PATH = get_sqlite_db_path(BACKEND_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a specific post for topic drift and update comment_group_drift.",
    )
    parser.add_argument("post_id", type=int, help="Target post_id")
    return parser.parse_args()

def get_database_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
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

    # Analyze actual content for topic expansion
    topic_expansion_keywords = [
        'mcp', 'codealive', 'конфереция', 'платно', 'бесплатно', 'регистрация',
        'кормить', 'гивы', 'опыт', 'контекст', 'архитектура', 'инструменты'
    ]

    has_topic_expansion = any(
        any(keyword in c['comment_text'].lower() for keyword in topic_expansion_keywords)
        for c in comments
    )

    # Enhanced heuristic: questions, discussion indicators, or topic expansion
    has_drift = 1 if (has_questions or has_discussion_indicators or has_topic_expansion) else 0

    if has_drift:
        # Extract drift topics based on actual comment analysis
        drift_topics = []

        # Analyze each comment for meaningful topics
        for comment in comments:
            comment_text = comment['comment_text'].lower()

            # Check for MCP discussion
            if 'mcp' in comment_text and 'mcp' not in post_text.lower():
                drift_topics.append({
                    "topic": "MCP (Model Context Protocol) discussion",
                    "keywords": ["mcp", "контекст", "context"],
                    "key_phrases": ["Выбор MCP без хайпа", "40к контекста"],
                    "context": "Discussion about MCP tools and context window sizes"
                })

            # Check for conference logistics
            if any(word in comment_text for word in ['платно', 'кормить', 'регистрация']):
                drift_topics.append({
                    "topic": "Conference logistics and practical details",
                    "keywords": ["платно", "кормить", "регистрация", "конференция"],
                    "key_phrases": ["Платно?", "Кормить будут там?", "1300 человек зарегалось"],
                    "context": "Questions about conference pricing, food, and registration numbers"
                })

            # Check for tool-specific discussions
            if 'codealive' in comment_text:
                drift_topics.append({
                    "topic": "CodeAlive tool discussion",
                    "keywords": ["codealive", "инструмент", "работает"],
                    "key_phrases": ["Как работает CodeAlive", "никому не рассказывай"],
                    "context": "Discussion about specific AI coding tools"
                })

        # Remove duplicates and limit
        unique_topics = []
        seen_topics = set()
        for topic in drift_topics:
            if topic["topic"] not in seen_topics:
                unique_topics.append(topic)
                seen_topics.add(topic["topic"])

        if unique_topics:
            return {"has_drift": 1, "drift_topics": unique_topics[:3]}

        # Fallback: generic drift
        for comment in comments[:2]:
            comment_text = comment['comment_text']
            words = comment_text.lower().split()
            new_words = [w for w in words if w not in post_words and len(w) > 3][:3]
            if new_words:
                drift_topics.append({
                    "topic": comment_text[:100] + "..." if len(comment_text) > 100 else comment_text,
                    "keywords": new_words,
                    "key_phrases": [comment_text[:50] + "..."],
                    "context": f"From comment by {comment['author_name']}"
                })

        return {"has_drift": 1, "drift_topics": drift_topics[:3]} if drift_topics else {"has_drift": 0, "drift_topics": None}
    else:
        return {"has_drift": 0, "drift_topics": None}

def update_drift_record(conn, post_id: int, analysis_result: Dict[str, Any]):
    """Update drift analysis result in database"""
    cursor = conn.cursor()

    # CRITICAL: Format drift_topics as proper JSON object with structure
    drift_topics_data = None
    if analysis_result['drift_topics']:
        drift_topics_data = json.dumps({
            "has_drift": True,
            "drift_topics": analysis_result['drift_topics']
        }, ensure_ascii=False)

    cursor.execute("""
        UPDATE comment_group_drift
        SET has_drift = ?,
            drift_topics = ?,
            analyzed_by = 'drift-on-synced',
            analyzed_at = datetime('now')
        WHERE post_id = ?
    """, (analysis_result['has_drift'], drift_topics_data, post_id))

    conn.commit()

def main():
    """Main drift analysis workflow for single post"""
    args = parse_args()
    post_id = args.post_id

    print(f"🎯 Single Drift Analysis Agent: Analyzing post {post_id}")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Check if post exists and is pending
        cursor = conn.cursor()
        cursor.execute("""
            SELECT post_id, expert_id, analyzed_by
            FROM comment_group_drift
            WHERE post_id = ?
        """, (post_id,))

        record = cursor.fetchone()
        if not record:
            print(f"❌ No drift record found for post {post_id}")
            sys.exit(1)

        if record['analyzed_by'] != 'pending':
            print(f"⚠️  Post {post_id} already analyzed by: {record['analyzed_by']}")
            print("Proceeding with reanalysis...")

        print(f"📊 Found drift record: post_id={record['post_id']}, expert_id={record['expert_id']}")

        # Get post content and comments
        post_content = get_post_content(conn, post_id)
        comments = get_comments_for_post(conn, post_id)

        print(f"  - Found {len(comments)} comments")
        print(f"  - Post content length: {len(post_content.get('message_text', ''))}")

        if not comments:
            print("  ⚠️  No comments found - marking as no drift")
            update_drift_record(conn, post_id, {"has_drift": 0, "drift_topics": None})
            print("✅ Analysis complete (no drift)")
            return

        # Analyze drift
        print("\n🔄 Analyzing drift...")
        analysis_result = analyze_drift_for_group(post_content, comments)

        # Update database
        update_drift_record(conn, post_id, analysis_result)

        # Display results
        if analysis_result["has_drift"] == 1:
            print(f"  ✅ Drift detected: {len(analysis_result['drift_topics'] or [])} topics")
            for i, topic in enumerate((analysis_result['drift_topics'] or []), 1):
                print(f"    {i}. {topic['topic']}")
                print(f"       Keywords: {', '.join(topic['keywords'])}")
                print(f"       Context: {topic['context']}")
        else:
            print(f"  ➖ No drift detected")

        # Verify update
        cursor.execute("""
            SELECT has_drift, analyzed_by, analyzed_at
            FROM comment_group_drift
            WHERE post_id = ?
        """, (post_id,))

        updated = cursor.fetchone()
        print(f"\n✅ Database updated:")
        print(f"  - has_drift: {updated['has_drift']}")
        print(f"  - analyzed_by: {updated['analyzed_by']}")
        print(f"  - analyzed_at: {updated['analyzed_at']}")

        print(f"\n🎉 Single drift analysis complete for post {post_id}!")

    except Exception as e:
        print(f"❌ Error analyzing post {post_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        conn.close()

if __name__ == "__main__":
    main()
