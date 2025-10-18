#!/usr/bin/env python3
"""Script to fix double nested drift topics structure"""

import sqlite3
import json

def fix_double_nested():
    conn = sqlite3.connect('data/experts.db')
    cursor = conn.cursor()

    # Get all drift-on-synced records
    cursor.execute("""
        SELECT post_id, drift_topics
        FROM comment_group_drift
        WHERE analyzed_by = 'drift-on-synced'
    """)

    records = cursor.fetchall()

    for post_id, topics in records:
        if topics:
            try:
                parsed = json.loads(topics)

                # Check if double nested: {"has_drift": true, "drift_topics": {"has_drift": true, "drift_topics": [...]}}
                if (isinstance(parsed, dict) and
                    'drift_topics' in parsed and
                    isinstance(parsed['drift_topics'], dict) and
                    'drift_topics' in parsed['drift_topics']):

                    # Extract the inner drift_topics array
                    inner_topics = parsed['drift_topics']['drift_topics']

                    # Create correct structure
                    new_structure = {
                        "has_drift": True,
                        "drift_topics": inner_topics
                    }

                    # Update the record
                    cursor.execute("""
                        UPDATE comment_group_drift
                        SET drift_topics = ?
                        WHERE post_id = ?
                    """, (json.dumps(new_structure, ensure_ascii=False), post_id))

                    print(f"Fixed double nesting in post {post_id}")

                elif isinstance(parsed, dict) and 'drift_topics' in parsed:
                    # Already correct structure
                    print(f"Post {post_id} already correct")
                else:
                    print(f"Unexpected structure for post {post_id}")

            except json.JSONDecodeError as e:
                print(f"Error fixing post {post_id}: {e}")

    conn.commit()
    conn.close()
    print("Fixed double nested drift topics")

if __name__ == "__main__":
    fix_double_nested()