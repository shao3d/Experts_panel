"""Expert metadata model - single source of truth for expert data."""

from sqlalchemy import Column, String

from .base import Base


class Expert(Base):
    """Expert metadata for multi-expert system.

    This table serves as the single source of truth for expert information,
    replacing hardcoded dictionaries in the codebase.

    Attributes:
        expert_id: Unique identifier for the expert (e.g., 'refat')
        display_name: Human-readable name shown in UI (e.g., 'Refat (Tech & AI)')
        channel_username: Telegram channel username without @ (e.g., 'nobilix')
    """

    __tablename__ = "expert_metadata"

    # Primary key
    expert_id = Column(String(50), primary_key=True)

    # Display information
    display_name = Column(String(255), nullable=False)

    # Telegram channel information
    channel_username = Column(String(255), nullable=False, unique=True)

    def __repr__(self):
        return f"<Expert(id={self.expert_id}, name={self.display_name})>"
