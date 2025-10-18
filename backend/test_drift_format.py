#!/usr/bin/env python3
"""Test script to check drift format in CommentGroupMapService"""

import sqlite3
import json
from pathlib import Path

def test_drift_format():
    """Test how CommentGroupMapService loads drift topics"""

    # Add src to path
    src_path = Path(__file__).parent / "src"
    import sys
    sys.path.insert(0, str(src_path))

    from src.models.database import comment_group_drift
    from src.models.post import Post
    from src.models.comment import Comment
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Setup database
    engine = create_engine("sqlite:///data/experts.db")
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Query exactly like CommentGroupMapService._load_drift_groups does
        results = db.query(
            comment_group_drift.c.post_id,
            comment_group_drift.c.drift_topics,
            Post.telegram_message_id,
            Post.message_text,
            Post.created_at,
            Post.author_name
        ).join(
            Post, comment_group_drift.c.post_id == Post.post_id
        ).filter(
            comment_group_drift.c.has_drift == True,
            comment_group_drift.c.expert_id == 'refat'
        ).limit(3).all()

        print("=== Как CommentGroupMapService загружает drift_topics ===\n")

        for post_id, drift_topics_json, telegram_msg_id, message_text, created_at, author_name in results:
            print(f"Post ID: {post_id}")
            print(f"Telegram Message ID: {telegram_msg_id}")
            print(f"Author: {author_name}")

            # Parse JSON like CommentGroupMapService does
            if drift_topics_json:
                try:
                    drift_topics = json.loads(drift_topics_json)
                    print(f"Type of drift_topics: {type(drift_topics)}")
                    print(f"Keys in drift_topics: {list(drift_topics.keys()) if isinstance(drift_topics, dict) else 'N/A (not dict)'}")

                    if isinstance(drift_topics, dict) and 'drift_topics' in drift_topics:
                        print(f"✅ Has 'drift_topics' key")
                        print(f"Type of drift_topics['drift_topics']: {type(drift_topics['drift_topics'])}")
                        print(f"Number of topics: {len(drift_topics['drift_topics'])}")

                        if drift_topics['drift_topics']:
                            first_topic = drift_topics['drift_topics'][0]
                            print(f"Keys in first topic: {list(first_topic.keys())}")
                            print(f"First topic preview: {first_topic.get('topic', 'N/A')[:100]}...")

                    elif isinstance(drift_topics, list):
                        print(f"❌ drift_topics is directly a list (old format)")
                        print(f"Number of topics: {len(drift_topics)}")

                    print()

                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
            else:
                print("❌ No drift_topics")

            print("-" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    test_drift_format()