#!/usr/bin/env python3
"""Populate database with test data for comment endpoint testing."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.models.base import SessionLocal, engine, Base
from src.models.post import Post
from src.models.link import Link, LinkType
from src.models.comment import Comment

# Ensure tables exist
Base.metadata.create_all(bind=engine)

# Create session
db = SessionLocal()

try:
    # Clear existing data
    db.query(Comment).delete()
    db.query(Link).delete()
    db.query(Post).delete()
    db.commit()

    # Create test posts
    posts_data = [
        {
            "post_id": 1,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 101,
            "author_name": "Alice",
            "message_text": "Welcome to our research channel! Today we'll discuss machine learning.",
            "created_at": datetime.now() - timedelta(days=7)
        },
        {
            "post_id": 2,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 102,
            "author_name": "Bob",
            "message_text": "Great introduction! I'd like to add some thoughts on neural networks.",
            "created_at": datetime.now() - timedelta(days=6)
        },
        {
            "post_id": 3,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 103,
            "author_name": "Charlie",
            "message_text": "Here's an interesting paper on transformer architectures.",
            "created_at": datetime.now() - timedelta(days=5)
        },
        {
            "post_id": 4,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 104,
            "author_name": "David",
            "message_text": "I've been experimenting with GPT models in production.",
            "created_at": datetime.now() - timedelta(days=4)
        },
        {
            "post_id": 5,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 105,
            "author_name": "Eve",
            "message_text": "Let's discuss the ethical implications of AI research.",
            "created_at": datetime.now() - timedelta(days=3)
        },
        {
            "post_id": 6,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 106,
            "author_name": "Frank",
            "message_text": "Responding to David's post about GPT models - here's my experience.",
            "created_at": datetime.now() - timedelta(days=2)
        },
        {
            "post_id": 7,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 107,
            "author_name": "Grace",
            "message_text": "New research findings on reinforcement learning!",
            "created_at": datetime.now() - timedelta(days=1)
        },
        {
            "post_id": 8,
            "channel_id": "test_channel_123",
            "channel_name": "Test Research Channel",
            "telegram_message_id": 108,
            "author_name": "Hank",
            "message_text": "Thanks everyone for the great discussions!",
            "created_at": datetime.now()
        }
    ]

    # Add posts
    for post_data in posts_data:
        post = Post(**post_data)
        db.add(post)

    db.commit()

    # Create some links
    links_data = [
        {"source_post_id": 2, "target_post_id": 1, "link_type": LinkType.REPLY},  # Bob replies to Alice
        {"source_post_id": 6, "target_post_id": 4, "link_type": LinkType.REPLY},  # Frank replies to David
        {"source_post_id": 3, "target_post_id": 2, "link_type": LinkType.FORWARD},  # Charlie forwards Bob's post
    ]

    for link_data in links_data:
        link = Link(**link_data)
        db.add(link)

    db.commit()

    # Add a sample comment
    sample_comment = Comment(
        post_id=1,
        comment_text="This is an excellent introduction to the topic. The ML discussion is well-structured.",
        author_name="Expert Reviewer",
        author_id="expert_001",
        created_at=datetime.now()
    )
    db.add(sample_comment)
    db.commit()

    print(f"✅ Successfully populated database with {len(posts_data)} posts, {len(links_data)} links, and 1 sample comment")
    print("\nPosts created:")
    for post in posts_data:
        print(f"  - ID {post['post_id']}: {post['author_name']} - {post['message_text'][:50]}...")

except Exception as e:
    print(f"❌ Error populating database: {e}")
    db.rollback()
finally:
    db.close()