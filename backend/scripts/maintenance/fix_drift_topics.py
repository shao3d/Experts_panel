#!/usr/bin/env python3
"""Script to fix drift topics structure in database"""

import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.fix_drift_topics",
)
DB_PATH = get_sqlite_db_path(BACKEND_DIR)

def fix_drift_topics():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all drift-on-synced records
    cursor.execute("""
        SELECT post_id, drift_topics
        FROM comment_group_drift
        WHERE analyzed_by = 'drift-on-synced'
    """)

    records = cursor.fetchall()

    for post_id, old_topics in records:
        if old_topics:
            try:
                # Parse the old structure - check if it's already correct or needs fixing
                try:
                    parsed = json.loads(old_topics)
                    if isinstance(parsed, dict) and 'drift_topics' in parsed:
                        # Already correct structure, skip
                        print(f"Post {post_id} already has correct structure")
                        continue
                    elif isinstance(parsed, list):
                        # Array structure that needs wrapping
                        topics_array = parsed
                    else:
                        print(f"Unexpected structure for post {post_id}")
                        continue
                except json.JSONDecodeError:
                    print(f"Invalid JSON for post {post_id}")
                    continue

                # Create new structure with proper wrapper
                new_structure = {
                    "has_drift": True,
                    "drift_topics": topics_array
                }

                # Update the record
                cursor.execute("""
                    UPDATE comment_group_drift
                    SET drift_topics = ?
                    WHERE post_id = ? AND analyzed_by = 'drift-on-synced'
                """, (json.dumps(new_structure, ensure_ascii=False), post_id))

                print(f"Fixed post {post_id}")

            except json.JSONDecodeError as e:
                print(f"Error fixing post {post_id}: {e}")
                continue

    conn.commit()
    conn.close()
    print(f"Fixed {len(records)} records")

if __name__ == "__main__":
    fix_drift_topics()
