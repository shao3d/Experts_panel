"""Comment model for expert annotations on posts."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from .base import Base


class Comment(Base):
    """Model representing expert comments and annotations on posts."""

    __tablename__ = "comments"

    # Primary key
    comment_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to post
    post_id = Column(Integer, ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=False, index=True)

    # Comment content
    comment_text = Column(Text, nullable=False)

    # Author information
    author_name = Column(String(255), nullable=False)
    author_id = Column(String(255), nullable=True)  # Optional author/session ID for tracking

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Telegram-specific fields (for imported comments)
    telegram_comment_id = Column(Integer, nullable=True, index=True)  # Original Telegram comment ID
    parent_telegram_message_id = Column(Integer, nullable=True)  # Telegram post ID this comment belongs to

    # Relationship to post
    post = relationship("Post", back_populates="comments")

    # Additional indexes for performance
    __table_args__ = (
        Index('idx_post_created', 'post_id', 'created_at'),
        Index('idx_telegram_comment_unique', 'telegram_comment_id', unique=True),
        Index('idx_telegram_comments', 'telegram_comment_id', 'post_id'),
    )

    def __repr__(self):
        return f"<Comment(comment_id={self.comment_id}, post_id={self.post_id}, author={self.author_name})>"