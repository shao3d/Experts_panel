#!/usr/bin/env python3
"""
Minimal script to add a new expert to the system.

This tool performs all necessary steps to add a new expert:
1. Add expert metadata to expert_metadata table
2. Import posts from Telegram JSON export
3. Backfill channel_username in posts table
4. Validate the import

Usage:
    python tools/add_expert.py <expert_id> <display_name> <channel_username> <json_file>

Example:
    python tools/add_expert.py neuraldeep "Neuraldeep" neuraldeep exports/neuraldeep.json

Next steps after running this script:
    - Sync comments: python sync_comments.py --expert-id <expert_id>
    - Verify in UI: open http://localhost:3000
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from models.base import SessionLocal
from models.expert import Expert
from data.json_parser import import_telegram_data
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def add_expert(expert_id: str, display_name: str, channel_username: str, json_file: str):
    """Add a new expert to the system.

    Args:
        expert_id: Unique expert identifier (e.g., 'neuraldeep')
        display_name: Human-readable name (e.g., 'Neuraldeep')
        channel_username: Telegram channel username (e.g., 'neuraldeep')
        json_file: Path to Telegram JSON export file

    Raises:
        SystemExit: If any step fails
    """
    db = SessionLocal()

    try:
        print(f"🚀 Adding expert: {expert_id}")
        print()

        # Step 1: Add to expert_metadata
        print(f"📝 Step 1/4: Adding expert metadata...")
        try:
            expert = Expert(
                expert_id=expert_id,
                display_name=display_name,
                channel_username=channel_username
            )
            db.add(expert)
            db.commit()
            print(f"✅ Expert metadata added")
        except IntegrityError as e:
            print(f"❌ Expert already exists: {expert_id}")
            print(f"   Error: {e}")
            print()
            print("To retry, first delete the existing expert:")
            print(f"   sqlite3 data/experts.db \"DELETE FROM expert_metadata WHERE expert_id = '{expert_id}';\"")
            db.rollback()
            sys.exit(1)

        print()

        # Step 2: Import posts
        print(f"📥 Step 2/4: Importing posts from {json_file}...")
        try:
            # Check if file exists
            if not Path(json_file).exists():
                print(f"❌ File not found: {json_file}")
                sys.exit(1)

            # Import using existing parser
            stats = import_telegram_data(json_file, expert_id)
            print(f"✅ Posts imported: {stats.get('posts_created', 0)} posts created")
        except Exception as e:
            print(f"❌ Import failed: {e}")
            sys.exit(1)

        print()

        # Step 3: Backfill channel_username
        print(f"🔄 Step 3/4: Backfilling channel_username...")
        result = db.execute(text("""
            UPDATE posts
            SET channel_username = :username
            WHERE expert_id = :expert_id AND channel_username IS NULL
        """), {"username": channel_username, "expert_id": expert_id})
        db.commit()
        print(f"✅ Updated {result.rowcount} posts with channel_username")

        print()

        # Step 4: Validate
        print(f"🔍 Step 4/4: Validating...")

        # Check 1: Posts without channel_username
        missing = db.execute(text("""
            SELECT COUNT(*) FROM posts
            WHERE expert_id = :expert_id AND channel_username IS NULL
        """), {"expert_id": expert_id}).scalar()

        if missing > 0:
            print(f"⚠️  Warning: {missing} posts missing channel_username")
        else:
            print(f"✅ All posts have channel_username")

        # Check 2: Total posts
        total_posts = db.execute(text("""
            SELECT COUNT(*) FROM posts WHERE expert_id = :expert_id
        """), {"expert_id": expert_id}).scalar()

        print(f"✅ Total posts for expert: {total_posts}")

        print()
        print("=" * 60)
        print(f"🎉 Expert '{expert_id}' added successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print(f"  1. Sync comments (optional):")
        print(f"     python sync_comments.py --expert-id {expert_id}")
        print()
        print(f"  2. Verify in API:")
        print(f"     curl http://localhost:8000/api/v1/experts | jq '.'")
        print()
        print(f"  3. Check in UI:")
        print(f"     open http://localhost:3000")
        print()

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def main():
    """Main entry point."""
    if len(sys.argv) != 5:
        print("Usage: python tools/add_expert.py <expert_id> <display_name> <channel_username> <json_file>")
        print()
        print("Example:")
        print('  python tools/add_expert.py neuraldeep "Neuraldeep" neuraldeep exports/neuraldeep.json')
        print()
        print("Arguments:")
        print("  expert_id         - Unique identifier (e.g., 'neuraldeep')")
        print("  display_name      - Human-readable name (e.g., 'Neuraldeep')")
        print("  channel_username  - Telegram channel username (e.g., 'neuraldeep')")
        print("  json_file         - Path to Telegram JSON export")
        sys.exit(1)

    expert_id = sys.argv[1]
    display_name = sys.argv[2]
    channel_username = sys.argv[3]
    json_file = sys.argv[4]

    add_expert(expert_id, display_name, channel_username, json_file)


if __name__ == '__main__':
    main()
