#!/usr/bin/env python3
"""
Script to update drift analysis for post_id=684, expert_id=refat
"""

import json
import sqlite3
from datetime import datetime

def update_drift_analysis():
    # Database connection
    db_path = "/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db"

    # Drift analysis data
    drift_data = {
        "has_drift": True,
        "drift_topics": [
            {
                "topic": "Veo 3.1 Video Generation Model Discussion",
                "keywords": ["veo 3.1", "higgsfield", "video generation", "waitlist", "comparison", "промпт"],
                "key_phrases": ["Про veo 3.1 ничего не слышно пока?", "сравнение 3.1 с 3", "higgsfield предлагают waitlist", "по одному и тому же промпту"],
                "context": "Users discuss the new Veo 3.1 video generation model from Higgsfield, comparing it with version 3.0 and sharing information about the waitlist availability. This represents a drift to focus on specific video generation capabilities not detailed in the original digest."
            },
            {
                "topic": "OpenAI Pricing Details and Technical Specifications",
                "keywords": ["openai", "pricing", "gpt-5 pro", "tokens", "cost", "api pricing"],
                "key_phrases": ["$120.00 / 1M tokens", "https://openai.com/api/pricing/", "Output: $120.00 / 1M tokens"],
                "context": "Technical discussion focused specifically on OpenAI's GPT-5 Pro pricing structure, with users sharing exact cost information and API pricing links. This drift focuses on detailed cost analysis that goes beyond the general announcement in the digest."
            },
            {
                "topic": "Backup and Data Security Personal Relevance",
                "keywords": ["backup", "напоминание", "бэкап", "безопасность данных", "спасибо"],
                "key_phrases": ["Про бэкап хорошее напоминание", "Спасибо"],
                "context": "Personal acknowledgment of the backup reminder importance, showing users found this particular news item highly relevant and actionable for their own data security practices."
            },
            {
                "topic": "Telegram Technical Support and Access Issues",
                "keywords": ["бан", "канал не найден", "доступ", "техническая поддержка", "аккаунт"],
                "key_phrases": ["Оффтоп. Пишет канал не найден", "это может означать что был бан", "лучше сюда написать", "с другого акка открывает", "может по ошибке под горячую руку попал"],
                "context": "User experiencing technical difficulties with channel access, leading to discussion about potential bans and troubleshooting solutions. This represents a drift from tech news to personal technical support issues within the Telegram ecosystem."
            }
        ]
    }

    # Convert to JSON string
    drift_json = json.dumps(drift_data, ensure_ascii=False)

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Update the drift analysis
        update_query = """
        UPDATE comment_group_drift
        SET has_drift = ?,
            drift_topics = ?,
            analyzed_by = 'drift-on-synced',
            analyzed_at = datetime('now')
        WHERE post_id = ? AND expert_id = ?
        """

        cursor.execute(update_query, (1, drift_json, 684, 'refat'))
        conn.commit()

        # Verify the update
        cursor.execute("SELECT changes()")
        rows_affected = cursor.fetchone()[0]

        print(f"✅ Successfully updated drift analysis for post_id=684, expert_id=refat")
        print(f"📊 Rows affected: {rows_affected}")

        # Show the updated record
        cursor.execute("""
        SELECT post_id, expert_id, has_drift, analyzed_by, analyzed_at
        FROM comment_group_drift
        WHERE post_id = 684 AND expert_id = 'refat'
        """)

        result = cursor.fetchone()
        if result:
            print(f"📋 Verification: post_id={result[0]}, expert_id={result[1]}, has_drift={result[2]}, analyzed_by={result[3]}")

        return True

    except Exception as e:
        print(f"❌ Error updating database: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    update_drift_analysis()