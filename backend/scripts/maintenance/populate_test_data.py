#!/usr/bin/env python3
"""Populate database with test data for comment endpoint testing."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, set_default_sqlite_database_url

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.populate_test_data",
)
set_default_sqlite_database_url(BACKEND_DIR, force=True)

from src.models.base import Base, SessionLocal, engine
from src.models.post import Post
from src.models.link import Link, LinkType
from src.models.comment import Comment

def main() -> int:
    # Ensure tables exist only when the script is intentionally executed.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        db.query(Comment).delete()
        db.query(Link).delete()
        db.query(Post).delete()
        db.commit()

        posts_data = [
            {
                "post_id": 1,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 101,
                "author_name": "Alice",
                "message_text": "Welcome to our research channel! Today we'll discuss machine learning.",
                "created_at": datetime.now() - timedelta(days=7),
            },
            {
                "post_id": 2,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 102,
                "author_name": "Bob",
                "message_text": "Great introduction! I'd like to add some thoughts on neural networks.",
                "created_at": datetime.now() - timedelta(days=6),
            },
            {
                "post_id": 3,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 103,
                "author_name": "Charlie",
                "message_text": "Here's an interesting paper on transformer architectures.",
                "created_at": datetime.now() - timedelta(days=5),
            },
            {
                "post_id": 4,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 104,
                "author_name": "David",
                "message_text": "I've been experimenting with GPT models in production.",
                "created_at": datetime.now() - timedelta(days=4),
            },
            {
                "post_id": 5,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 105,
                "author_name": "Eve",
                "message_text": "Let's discuss the ethical implications of AI research.",
                "created_at": datetime.now() - timedelta(days=3),
            },
            {
                "post_id": 6,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 106,
                "author_name": "Frank",
                "message_text": "Responding to David's post about GPT models - here's my experience.",
                "created_at": datetime.now() - timedelta(days=2),
            },
            {
                "post_id": 7,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 107,
                "author_name": "Grace",
                "message_text": "New research findings on reinforcement learning!",
                "created_at": datetime.now() - timedelta(days=1),
            },
            {
                "post_id": 8,
                "channel_id": "test_channel_123",
                "channel_name": "Test Research Channel",
                "telegram_message_id": 108,
                "author_name": "Hank",
                "message_text": "Thanks everyone for the great discussions!",
                "created_at": datetime.now(),
            },
        ]

        for post_data in posts_data:
            db.add(Post(**post_data))
        db.commit()

        links_data = [
            {"source_post_id": 2, "target_post_id": 1, "link_type": LinkType.REPLY},
            {"source_post_id": 6, "target_post_id": 4, "link_type": LinkType.REPLY},
            {"source_post_id": 3, "target_post_id": 2, "link_type": LinkType.FORWARD},
        ]

        for link_data in links_data:
            db.add(Link(**link_data))
        db.commit()

        db.add(
            Comment(
                post_id=1,
                comment_text="This is an excellent introduction to the topic. The ML discussion is well-structured.",
                author_name="Expert Reviewer",
                author_id="expert_001",
                created_at=datetime.now(),
            )
        )
        db.commit()

        print(
            f"Successfully populated database with {len(posts_data)} posts, "
            f"{len(links_data)} links, and 1 sample comment"
        )
        print("\nPosts created:")
        for post in posts_data:
            print(
                f"  - ID {post['post_id']}: {post['author_name']} - "
                f"{post['message_text'][:50]}..."
            )
        return 0
    except Exception as e:
        print(f"Error populating database: {e}")
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
