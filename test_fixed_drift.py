#!/usr/bin/env python3
"""Test fixed drift format in CommentGroupMapService"""

import sqlite3
import json

def test_fixed_drift():
    conn = sqlite3.connect('data/experts.db')
    cursor = conn.cursor()

    # Get drift topics like CommentGroupMapService does now
    cursor.execute("""
        SELECT post_id, drift_topics, analyzed_by
        FROM comment_group_drift
        WHERE has_drift = 1
        AND expert_id = 'refat'
        LIMIT 3
    """)

    results = cursor.fetchall()

    print("=== Тест исправленного формата drift тем ===\n")

    for post_id, drift_topics_json, analyzed_by in results:
        print(f"Post ID: {post_id}")
        print(f"Analyzed by: {analyzed_by}")

        try:
            # Simulate the new CommentGroupMapService logic
            sanitized = re.sub(r'\\(?![ntr"\\/])', '', drift_topics_json)
            parsed_drift = json.loads(sanitized)

            # Extract only the drift_topics array, not the wrapper
            if isinstance(parsed_drift, dict) and 'drift_topics' in parsed_drift:
                drift_topics = parsed_drift['drift_topics']
            elif isinstance(parsed_drift, list):
                drift_topics = parsed_drift
            else:
                drift_topics = []

            print(f"✅ Extracted drift_topics type: {type(drift_topics)}")
            print(f"✅ Number of topics: {len(drift_topics)}")

            if drift_topics:
                first_topic = drift_topics[0]
                print(f"✅ First topic keys: {list(first_topic.keys())}")
                print(f"✅ Topic preview: {first_topic.get('topic', 'N/A')[:80]}...")

                # Это то что уйдет в промпт
                print(f"✅ Что уйдет в _format_groups_for_prompt: {type(drift_topics)}")
                print(f"✅ Правильный формат (массив): {'YES' if isinstance(drift_topics, list) else 'NO'}")

        except json.JSONDecodeError as e:
            print(f"❌ JSON Error: {e}")

        print("-" * 50)

    conn.close()

if __name__ == "__main__":
    import re
    test_fixed_drift()