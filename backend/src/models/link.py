"""Link model for post-to-post relationships in Telegram channels."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .base import Base


class LinkType(str, Enum):
    """Types of relationships between posts."""
    REPLY = "reply"
    FORWARD = "forward"
    MENTION = "mention"


class Link(Base):
    """Model representing relationships between posts."""

    __tablename__ = "links"

    # Primary key
    link_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys to posts
    source_post_id = Column(Integer, ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=False, index=True)
    target_post_id = Column(Integer, ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=False, index=True)

    # Link type
    link_type = Column(String(20), nullable=False)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships for navigation
    source_post = relationship("Post", foreign_keys=[source_post_id], backref="outgoing_links")
    target_post = relationship("Post", foreign_keys=[target_post_id], backref="incoming_links")

    # Constraints and indexes
    __table_args__ = (
        # Unique constraint to prevent duplicate relationships
        UniqueConstraint('source_post_id', 'target_post_id', 'link_type', name='uix_source_target_type'),
        # Additional composite indexes for efficient queries
        Index('idx_source_type', 'source_post_id', 'link_type'),
        Index('idx_target_type', 'target_post_id', 'link_type'),
    )

    def __repr__(self):
        return f"<Link(source={self.source_post_id}, target={self.target_post_id}, type={self.link_type})>"