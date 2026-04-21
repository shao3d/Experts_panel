#!/usr/bin/env python3
"""
Check for pending comment groups in the database
"""

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.check_pending_groups",
)
DB_PATH = get_sqlite_db_path(BACKEND_DIR)


def main():
    conn = None

    try:
        # Connect to database
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query for pending groups
        print("🔍 Checking for pending comment groups...")
        cursor.execute("""
            SELECT
                post_id,
                expert_id,
                analyzed_at,
                analyzed_by,
                has_drift
            FROM comment_group_drift
            WHERE analyzed_by = 'pending'
            ORDER BY post_id DESC
        """)

        pending_groups = cursor.fetchall()

        if not pending_groups:
            print("✅ No pending groups found")

            # Check what groups we do have
            cursor.execute("""
                SELECT
                    analyzed_by,
                    COUNT(*) as count
                FROM comment_group_drift
                GROUP BY analyzed_by
                ORDER BY count DESC
            """)

            all_groups = cursor.fetchall()
            print("\n📊 Current groups by status:")
            for row in all_groups:
                print(f"  - {row['analyzed_by']}: {row['count']} groups")

            # Show the most recent groups (latest processed)
            cursor.execute("""
                SELECT
                    post_id,
                    expert_id,
                    analyzed_at,
                    analyzed_by,
                    has_drift
                FROM comment_group_drift
                ORDER BY post_id DESC
                LIMIT 5
            """)

            recent_groups = cursor.fetchall()
            print(f"\n📋 5 most recent groups:")
            for row in recent_groups:
                print(f"  - Post {row['post_id']} ({row['expert_id']}) - {row['analyzed_by']} - Drift: {bool(row['has_drift'])}")

        else:
            print(f"📋 Found {len(pending_groups)} pending groups:")

            # Group by expert
            expert_counts = {}
            latest_post_id = None
            latest_expert = None

            for row in pending_groups:
                expert_id = row['expert_id']
                expert_counts[expert_id] = expert_counts.get(expert_id, 0) + 1

                # Track the latest (highest) post_id
                if latest_post_id is None or row['post_id'] > latest_post_id:
                    latest_post_id = row['post_id']
                    latest_expert = expert_id

                print(f"  - Post {row['post_id']} from {expert_id}")

            print(f"\n📊 By expert:")
            for expert_id, count in expert_counts.items():
                print(f"  - {expert_id}: {count} pending groups")

            print(f"\n🎯 Latest (highest post_id): {latest_post_id} from {latest_expert}")

            return latest_post_id, latest_expert

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    main()
