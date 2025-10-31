#!/usr/bin/env python3
"""
Drift-on-Synced Agent for specific post analysis
Executes drift analysis for post_id 717 (telegram_message_id: 170, expert: refat)
"""

import sqlite3
import json
import requests
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Database configuration
DB_PATH = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv('OPENAI_API_KEY')
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_database_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def get_post_details(post_id: int, expert_id: str) -> Optional[Dict[str, Any]]:
    """Get post details from database"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT post_id, telegram_message_id, message_text, author_name, created_at
            FROM posts
            WHERE post_id = ? AND expert_id = ?
        """, (post_id, expert_id))
        row = cursor.fetchone()
        if row:
            return {
                'post_id': row[0],
                'telegram_message_id': row[1],
                'message_text': row[2],
                'author_name': row[3],
                'created_at': row[4]
            }
        return None
    finally:
        conn.close()

def get_post_comments(post_id: int) -> List[Dict[str, Any]]:
    """Get all comments for a post"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT comment_id, comment_text, author_name, created_at
            FROM comments
            WHERE post_id = ?
            ORDER BY created_at
        """, (post_id,))
        rows = cursor.fetchall()
        return [{
            'comment_id': row[0],
            'comment_text': row[1],
            'author_name': row[2],
            'created_at': row[3]
        } for row in rows]
    finally:
        conn.close()

def analyze_drift_with_claude(post_content: str, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze comment drift using Claude API"""

    # Prepare comments text for analysis
    comments_text = "\n\n".join([
        f"Comment by {c['author_name']} ({c['created_at']}):\n{c['comment_text']}"
        for c in comments
    ])

    prompt = f"""Analyze the comment drift for this Telegram post and its comments.

Original Post:
{post_content}

Comments:
{comments_text}

Task: Compare the original post topic with the comment discussions to identify topic drift. Extract any meaningful drift topics where comments discuss different themes, expand on the original topic, or introduce tangential discussions.

Return JSON in this exact format:
{{
    "has_drift": true/false,
    "drift_topics": [
        {{
            "topic": "Clear description of the drift topic",
            "keywords": ["keyword1", "keyword2", "keyword3"],
            "key_phrases": ["exact phrase from comments", "another exact phrase"],
            "context": "Brief context of this drift topic from the discussion"
        }}
    ]
}}

Rules:
- Only set has_drift=true if comments add meaningful new topics beyond the original post
- Extract topics where comments significantly expand or shift from the original theme
- Include exact key phrases from comments that represent each drift topic
- Be specific about what makes each topic a drift from the original post
- If no meaningful drift exists, return {{"has_drift": false, "drift_topics": []}}"""

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()
        analysis = json.loads(result['choices'][0]['message']['content'])

        # Validate response format
        if 'has_drift' not in analysis or 'drift_topics' not in analysis:
            raise ValueError("Invalid response format from Claude")

        return analysis

    except Exception as e:
        print(f"Error calling Claude API: {e}")
        # Return safe default
        return {"has_drift": False, "drift_topics": []}

def update_drift_analysis(post_id: int, expert_id: str, drift_analysis: Dict[str, Any]) -> bool:
    """Update drift analysis in database"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()

        # Prepare drift_topics as JSON string with proper format
        drift_topics_json = json.dumps(drift_analysis, ensure_ascii=False)

        cursor.execute("""
            UPDATE comment_group_drift
            SET has_drift = ?,
                drift_topics = ?,
                analyzed_by = 'drift-on-synced',
                analyzed_at = datetime('now')
            WHERE post_id = ? AND expert_id = ?
        """, (
            1 if drift_analysis.get('has_drift', False) else 0,
            drift_topics_json,
            post_id,
            expert_id
        ))

        conn.commit()
        return cursor.rowcount > 0

    except Exception as e:
        print(f"Error updating drift analysis: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main execution function"""
    target_post_id = 717
    target_expert_id = "refat"

    print(f"🎯 Starting drift-on-synced analysis for post_id {target_post_id}, expert {target_expert_id}")

    # Get post details
    post = get_post_details(target_post_id, target_expert_id)
    if not post:
        print(f"❌ Post {target_post_id} not found for expert {target_expert_id}")
        return

    print(f"📝 Found post: telegram_message_id {post['telegram_message_id']}")

    # Get comments
    comments = get_post_comments(target_post_id)
    print(f"💬 Found {len(comments)} comments")

    if not comments:
        print("⚠️ No comments found for this post")
        return

    # Analyze drift
    print("🧠 Analyzing comment drift with Claude...")
    drift_analysis = analyze_drift_with_claude(post['message_text'], comments)

    # Update database
    success = update_drift_analysis(target_post_id, target_expert_id, drift_analysis)

    if success:
        print("✅ Drift analysis completed and saved to database")
        print(f"📊 Has drift: {drift_analysis.get('has_drift', False)}")
        print(f"🔢 Drift topics found: {len(drift_analysis.get('drift_topics', []))}")

        if drift_analysis.get('drift_topics'):
            print("\n📋 Drift Topics Summary:")
            for i, topic in enumerate(drift_analysis['drift_topics'], 1):
                print(f"  {i}. {topic.get('topic', 'Unknown topic')}")
                print(f"     Keywords: {', '.join(topic.get('keywords', []))}")
    else:
        print("❌ Failed to update drift analysis in database")

if __name__ == "__main__":
    main()