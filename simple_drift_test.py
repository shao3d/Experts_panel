#!/usr/bin/env python3
"""Simple test to check drift format in database"""

import sqlite3
import json

def simple_test():
    conn = sqlite3.connect('data/experts.db')
    cursor = conn.cursor()

    # Get drift topics like CommentGroupMapService does
    cursor.execute("""
        SELECT post_id, drift_topics, analyzed_by
        FROM comment_group_drift
        WHERE has_drift = 1
        AND expert_id = 'refat'
        LIMIT 5
    """)

    results = cursor.fetchall()

    print("=== Анализ drift форматов в базе данных ===\n")

    for post_id, drift_topics_json, analyzed_by in results:
        print(f"Post ID: {post_id}")
        print(f"Analyzed by: {analyzed_by}")

        try:
            drift_topics = json.loads(drift_topics_json)
            print(f"Type: {type(drift_topics)}")

            if isinstance(drift_topics, dict):
                print(f"Keys: {list(drift_topics.keys())}")
                if 'drift_topics' in drift_topics:
                    inner_topics = drift_topics['drift_topics']
                    print(f"Inner drift_topics type: {type(inner_topics)}")
                    print(f"Inner topics count: {len(inner_topics) if isinstance(inner_topics, list) else 'N/A'}")

                    if isinstance(inner_topics, list) and inner_topics:
                        first_topic = inner_topics[0]
                        print(f"First topic keys: {list(first_topic.keys())}")
                        print(f"Topic preview: {first_topic.get('topic', 'N/A')[:80]}...")

                        # Проверяем что пойдет в _format_groups_for_prompt
                        print(f"Что пойдет в _format_groups_for_prompt: {type(drift_topics)}")
                        print(f"Будет ли обертка включена: {'YES' if isinstance(drift_topics, dict) else 'NO'}")

            elif isinstance(drift_topics, list):
                print(f"Direct list (old format): {len(drift_topics)} items")

        except json.JSONDecodeError as e:
            print(f"❌ JSON Error: {e}")

        print("-" * 50)

    conn.close()

if __name__ == "__main__":
    simple_test()