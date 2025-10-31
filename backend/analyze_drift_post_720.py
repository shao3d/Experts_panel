#!/usr/bin/env python3
"""
Drift analysis for post_id 720 (telegram_message_id: 174, expert: refat)
"""

import json
import sqlite3
from datetime import datetime
import os

def main():
    # Database connection
    db_path = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Get post data
            cursor.execute("""
                SELECT telegram_message_id, message_text, expert_id, channel_name
                FROM posts
                WHERE post_id = 720 AND expert_id = 'refat'
            """)
            post_row = cursor.fetchone()

            if not post_row:
                print("❌ Post 720 not found for expert 'refat'")
                return

            telegram_message_id, post_content, expert_id, channel_name = post_row

            # Get comments for this post
            cursor.execute("""
                SELECT comment_id, comment_text, author_name, created_at
                FROM comments
                WHERE post_id = 720
                ORDER BY created_at
            """)
            comment_rows = cursor.fetchall()

            if not comment_rows:
                print("❌ No comments found for post_id 720")
                return

            # Format comments
            comments_text = ""
            for comment_id, comment_text, author_name, created_at in comment_rows:
                comments_text += f"Comment by {author_name} ({created_at}):\n{comment_text}\n\n"

            print(f"📊 Analyzing drift for post_id 720 (telegram_message_id: {telegram_message_id}, expert: {expert_id})")
            print(f"📝 Found {len(comment_rows)} comments")
            print(f"🔍 Starting drift analysis...")

            # Manual drift analysis based on content
            # Post: Comprehensive weekly digest covering various AI and technology news
            # Comment: Specifically mentions Google's AI Studio app constructor update with critical opinion
            # Analysis: The comment focuses on ONE specific item from the digest and adds personal criticism about usability
            # This IS drift because it:
            # 1. Focuses on a single item rather than the broader digest scope
            # 2. Adds personal experience/opinion about usability issues
            # 3. Expresses negative sentiment about the update being "not controlled at all"

            drift_result = {
                "has_drift": True,
                "drift_topics": [
                    {
                        "topic": "Критика Google AI Studio конструктора приложений",
                        "keywords": ["Google AI Studio", "ИИ-конструктор", "приложения", "управляемость", "проблемы"],
                        "key_phrases": ["Лучше бы они этого не делали", "ассистент стал не управляемым от слова совсем"],
                        "context": "Комментарий фокусируется на конкретном обновлении Google AI Studio (одно из множества новостей в дайджесте) и выражает критическое мнение о проблемах с управляемостью ИИ-ассистента после обновления. Это демонстрирует дрифт от общего обзора новостей к детальной критике одного конкретного продукта."
                    }
                ]
            }

            # Ensure proper JSON structure for database
            drift_topics_json = json.dumps(drift_result, ensure_ascii=False, indent=2)

            # Update database
            cursor.execute("""
                UPDATE comment_group_drift
                SET has_drift = ?,
                    drift_topics = ?,
                    analyzed_by = 'drift-on-synced',
                    analyzed_at = datetime('now')
                WHERE post_id = ? AND expert_id = ?
            """, (
                1 if drift_result.get('has_drift', False) else 0,
                drift_topics_json,
                720,
                'refat'
            ))

            conn.commit()

            print(f"✅ Drift analysis completed for post_id 720")
            print(f"📊 Has drift: {drift_result.get('has_drift', False)}")
            if drift_result.get('has_drift', False):
                drift_topics = drift_result.get('drift_topics', [])
                print(f"🎯 Found {len(drift_topics)} drift topics:")
                for i, topic in enumerate(drift_topics, 1):
                    print(f"  {i}. {topic.get('topic', 'Unknown')}")
                    print(f"     Keywords: {', '.join(topic.get('keywords', []))}")
            else:
                print("📭 No drift detected - comments stay within original topic scope")

            # Save detailed analysis
            result_data = {
                "post_id": 720,
                "telegram_message_id": telegram_message_id,
                "expert_id": expert_id,
                "channel_name": channel_name,
                "post_content": post_content,
                "comments_count": len(comment_rows),
                "comments": [
                    {
                        "comment_id": comment_id,
                        "text": comment_text,
                        "author": author_name,
                        "created_at": created_at
                    }
                    for comment_id, comment_text, author_name, created_at in comment_rows
                ],
                "drift_analysis": drift_result,
                "analyzed_at": datetime.now().isoformat()
            }

            output_file = '/Users/andreysazonov/Documents/Projects/Experts_panel/backend/drift_analysis_post_720.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

            print(f"💾 Detailed analysis saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error during drift analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()