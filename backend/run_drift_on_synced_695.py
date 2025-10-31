#!/usr/bin/env python3
"""
Drift-on-Synced Agent for post_id 695 specifically

Analyzes drift for neuraldeep post with telegram_message_id 1667 (post_id 695)
This script re-analyzes the specific post and updates the database accordingly.
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI

# Database configuration
DATABASE_PATH = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"

# OpenAI configuration
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def get_post_details(post_id: int) -> Optional[Dict[str, Any]]:
    """Get post details including telegram_message_id and expert_id"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT telegram_message_id, expert_id, message_text
        FROM posts
        WHERE post_id = ?
    """, (post_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'telegram_message_id': result[0],
            'expert_id': result[1],
            'content': result[2]  # message_text becomes content
        }
    return None

def get_comments_for_post(post_id: int) -> List[Dict[str, Any]]:
    """Get all comments for a specific post"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT comment_id, comment_text, author_name, created_at
        FROM comments
        WHERE post_id = ?
        ORDER BY created_at
    """, (post_id,))

    comments = []
    for row in cursor.fetchall():
        comments.append({
            'comment_id': row[0],
            'comment_text': row[1],
            'author_name': row[2],
            'created_at': row[3]
        })

    conn.close()
    return comments

def analyze_drift_for_post(post_content: str, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze drift between post content and comments using Claude API"""

    # Prepare comments text for analysis
    comments_text = "\n\n".join([
        f"Comment by {c['author_name']}: {c['comment_text']}"
        for c in comments
    ])

    # Drift analysis prompt
    prompt = f"""Analyze the topic drift between this original post and the following comments.

Original Post Content:
{post_content}

Comments:
{comments_text}

Your task:
1. Compare the main topic/theme of the original post with what people are actually discussing in the comments
2. Identify if the comments have drifted away from the original topic, expanded on it, or introduced new themes
3. Extract specific drift topics with keywords and key phrases
4. Determine if meaningful drift exists

Return a JSON object with this exact format:
{{
    "has_drift": true/false,
    "drift_analysis": "Brief explanation of drift or lack thereof",
    "drift_topics": [
        {{
            "topic": "Clear description of the drift topic",
            "keywords": ["keyword1", "keyword2", "keyword3"],
            "key_phrases": ["exact phrase from comments", "another exact phrase"],
            "context": "Brief context from the discussion"
        }}
    ]
}}

If no meaningful drift exists, set has_drift to false and return an empty drift_topics array."""

    try:
        response = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing conversation drift and topic changes in discussions. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()

        # Try to parse JSON
        try:
            # Remove any markdown code blocks
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            return json.loads(result_text)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from response: {result_text}")
            return {"has_drift": False, "drift_topics": []}

    except Exception as e:
        print(f"Error analyzing drift: {e}")
        return {"has_drift": False, "drift_topics": []}

def update_drift_analysis(post_id: int, drift_result: Dict[str, Any]) -> bool:
    """Update the drift analysis in the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Prepare drift_topics JSON according to the required format
        if drift_result.get('has_drift', False) and drift_result.get('drift_topics'):
            # The required format is: {"has_drift": true, "drift_topics": [...]}
            drift_topics_json = json.dumps({
                "has_drift": True,
                "drift_topics": drift_result['drift_topics']
            })
            has_drift = 1
        else:
            drift_topics_json = None
            has_drift = 0

        cursor.execute("""
            UPDATE comment_group_drift
            SET has_drift = ?,
                drift_topics = ?,
                analyzed_by = 'drift-on-synced',
                analyzed_at = datetime('now')
            WHERE post_id = ?
        """, (has_drift, drift_topics_json, post_id))

        conn.commit()
        return True

    except Exception as e:
        print(f"Error updating drift analysis: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main function to analyze drift for post_id 695"""
    post_id = 695

    print(f"🎯 Starting drift analysis for post_id {post_id}")

    # Get post details
    post_details = get_post_details(post_id)
    if not post_details:
        print(f"❌ Post {post_id} not found")
        return

    print(f"📝 Post found: telegram_message_id {post_details['telegram_message_id']}, expert_id {post_details['expert_id']}")
    # Display first 100 characters of post content as preview
    content_preview = post_details['content'][:100] + "..." if len(post_details['content']) > 100 else post_details['content']
    print(f"📄 Post content preview: {content_preview}")

    # Get comments for the post
    comments = get_comments_for_post(post_id)
    print(f"💬 Found {len(comments)} comments")

    if not comments:
        print("⚠️ No comments found for this post")
        return

    # Analyze drift
    print("🔍 Analyzing drift...")
    drift_result = analyze_drift_for_post(post_details['content'], comments)

    print(f"📊 Drift analysis result:")
    print(f"   Has drift: {drift_result.get('has_drift', False)}")
    if drift_result.get('drift_topics'):
        print(f"   Drift topics found: {len(drift_result['drift_topics'])}")
        for i, topic in enumerate(drift_result['drift_topics']):
            print(f"     {i+1}. {topic['topic']}")

    # Update database
    print("💾 Updating database...")
    success = update_drift_analysis(post_id, drift_result)

    if success:
        print("✅ Drift analysis completed successfully")
        print(f"📈 Post {post_id} drift analysis updated in database")
    else:
        print("❌ Failed to update drift analysis in database")

if __name__ == "__main__":
    main()