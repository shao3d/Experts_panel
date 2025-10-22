"""Post model for Telegram channel posts."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from sqlalchemy.orm import relationship

from .base import Base


class Post(Base):
    """Model representing a Telegram channel post."""

    __tablename__ = "posts"

    # Primary key
    post_id = Column(Integer, primary_key=True, autoincrement=True)

    # Channel information
    channel_id = Column(String(100), nullable=False, index=True)
    channel_name = Column(String(255))
    channel_username = Column(String(255))  # Telegram username for links

    # Expert identification
    expert_id = Column(String(50), nullable=True, index=True)

    # Content
    message_text = Column(Text, nullable=True)  # Can be empty for media-only posts

    # Author information
    author_name = Column(String(255))
    author_id = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    edited_at = Column(DateTime, nullable=True)

    # Engagement metrics
    view_count = Column(Integer, default=0)
    forward_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)

    # Media and attachments (stored as JSON metadata)
    media_metadata = Column(JSON, nullable=True)

    # Telegram-specific fields
    telegram_message_id = Column(Integer)  # Original message ID from Telegram
    is_forwarded = Column(Integer, default=0)  # Boolean as integer for SQLite
    forward_from_channel = Column(String(255))

    # Relationships
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    # Additional indexes for performance
    __table_args__ = (
        Index('idx_channel_created', 'channel_id', 'created_at'),
        Index('idx_text_search', 'message_text'),  # SQLite will use this for LIKE queries
    )

    def __repr__(self):
        return f"<Post(post_id={self.post_id}, channel={self.channel_name}, created={self.created_at})>"