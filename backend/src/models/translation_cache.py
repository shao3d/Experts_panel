"""Persistent cache for LLM translations (posts, comments, answers).

Posts and comments are static Telegram content: a translation never changes,
so it is computed once per (text, language pair) and reused across requests,
process restarts, and deployments. The table is created automatically at
startup via Base.metadata.create_all.
"""

from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime

from .base import Base


class TranslationCache(Base):
    """Cached translation result keyed by source text hash + language pair."""

    __tablename__ = "translation_cache"

    # sha256(normalized_text|source_lang->target_lang)
    cache_key = Column(String(64), primary_key=True)
    source_lang = Column(String(20), nullable=False)
    target_lang = Column(String(20), nullable=False)
    translated_text = Column(Text, nullable=False)
    model = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return (
            f"<TranslationCache(key={self.cache_key[:12]}..., "
            f"{self.source_lang}->{self.target_lang})>"
        )
