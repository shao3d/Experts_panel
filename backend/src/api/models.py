"""Pydantic models for API request/response schemas."""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RelevanceLevel(str, Enum):
    """Relevance levels for posts."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CONTEXT = "CONTEXT"


class ConfidenceLevel(str, Enum):
    """Confidence levels for answers."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    query: str = Field(
        ...,
        description="User's query in natural language",
        min_length=3,
        max_length=1000
    )
    max_posts: Optional[int] = Field(
        default=None,
        description="Maximum number of posts to process (None = all)",
        ge=10,
        le=None
    )
    include_comments: Optional[bool] = Field(
        default=True,
        description="Whether to include expert comments in the response"
    )
    include_comment_groups: Optional[bool] = Field(
        default=False,
        description="Whether to search for relevant Telegram comment groups (Pipeline B)"
    )
    stream_progress: Optional[bool] = Field(
        default=True,
        description="Whether to stream progress updates via SSE"
    )
    expert_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific expert IDs. None = all experts"
    )
    use_recent_only: Optional[bool] = Field(
        default=False,
        description="Use only recent data (last 3 months) for fresh news and current models. "
                    "When false, uses all available data for comprehensive answers including "
                    "methodology and historical context."
    )


class PostReference(BaseModel):
    """Reference to a post with relevance information."""

    telegram_message_id: int = Field(
        ...,
        description="Telegram message ID"
    )
    relevance: RelevanceLevel = Field(
        ...,
        description="Relevance level of the post"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason why this post is relevant"
    )
    is_original: bool = Field(
        default=True,
        description="Whether this was in original results or added via links"
    )


class TokenUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Optional[float] = None


class AnchorPost(BaseModel):
    """Anchor post information for comment groups."""

    telegram_message_id: int = Field(
        ...,
        description="Telegram message ID of the anchor post"
    )
    message_text: str = Field(
        ...,
        description="Text content of the anchor post"
    )
    created_at: str = Field(
        ...,
        description="When the anchor post was created"
    )
    author_name: str = Field(
        ...,
        description="Author of the anchor post"
    )
    channel_username: str = Field(
        ...,
        description="Channel username for Telegram links"
    )


class CommentGroupResponse(BaseModel):
    """Response model for a relevant comment group."""

    parent_telegram_message_id: int = Field(
        ...,
        description="Telegram message ID of the anchor post"
    )
    relevance: str = Field(
        ...,
        description="Relevance level (HIGH/MEDIUM/LOW)"
    )
    reason: str = Field(
        ...,
        description="Explanation of why this comment group is relevant"
    )
    comments_count: int = Field(
        ...,
        description="Number of comments in this group"
    )
    anchor_post: AnchorPost = Field(
        ...,
        description="The anchor post that these comments belong to"
    )
    comments: List['CommentResponse'] = Field(
        default_factory=list,
        description="List of comments in this group"
    )


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    query: str = Field(
        ...,
        description="Original query"
    )
    answer: str = Field(
        ...,
        description="Synthesized answer with inline references"
    )
    main_sources: List[int] = Field(
        default_factory=list,
        description="Main source post IDs (telegram_message_ids)"
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level of the answer"
    )
    language: str = Field(
        ...,
        description="Language of the response (ru/en)"
    )
    has_expert_comments: bool = Field(
        default=False,
        description="Whether expert comments were included"
    )
    posts_analyzed: int = Field(
        ...,
        description="Total number of posts analyzed"
    )
    expert_comments_included: int = Field(
        default=0,
        description="Number of expert comments included"
    )
    relevance_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of posts by relevance level"
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None,
        description="Token usage statistics"
    )
    processing_time_ms: int = Field(
        ...,
        description="Total processing time in milliseconds"
    )
    request_id: str = Field(
        ...,
        description="Unique request ID for tracking"
    )
    relevant_comment_groups: List[CommentGroupResponse] = Field(
        default_factory=list,
        description="Relevant comment groups found (optional, if enabled)"
    )
    comment_groups_synthesis: Optional[str] = Field(
        default=None,
        description="Synthesized insights from comment groups (optional)"
    )


class ProgressEvent(BaseModel):
    """SSE progress event model."""

    event_type: str = Field(
        ...,
        description="Type of progress event"
    )
    phase: str = Field(
        ...,
        description="Current phase (map/resolve/reduce)"
    )
    status: str = Field(
        ...,
        description="Current status within phase"
    )
    message: str = Field(
        ...,
        description="Human-readable progress message"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional event data"
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(
        ...,
        description="Error type"
    )
    message: str = Field(
        ...,
        description="Error message"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID if available"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )


class CommentResponse(BaseModel):
    """Response model for a comment."""

    comment_id: int = Field(
        ...,
        description="Comment ID"
    )
    comment_text: str = Field(
        ...,
        description="Comment text"
    )
    author_name: str = Field(
        ...,
        description="Comment author name"
    )
    created_at: datetime = Field(
        ...,
        description="When comment was created"
    )
    updated_at: datetime = Field(
        ...,
        description="When comment was last updated"
    )


class LinkResponse(BaseModel):
    """Response model for a link relationship."""

    link_id: int = Field(
        ...,
        description="Link ID"
    )
    source_post_id: int = Field(
        ...,
        description="Source post ID"
    )
    target_post_id: int = Field(
        ...,
        description="Target post ID"
    )
    link_type: str = Field(
        ...,
        description="Type of link (reply/forward/mention)"
    )
    created_at: datetime = Field(
        ...,
        description="When link was created"
    )


class SimplifiedPostDetailResponse(BaseModel):
    """Simplified response model for individual post details."""

    telegram_message_id: int = Field(
        ...,
        description="Original Telegram message ID"
    )
    author_name: Optional[str] = Field(
        default=None,
        description="Post author name"
    )
    message_text: Optional[str] = Field(
        default=None,
        description="Post content"
    )
    created_at: str = Field(
        ...,
        description="Post creation date"
    )
    channel_name: Optional[str] = Field(
        default=None,
        description="Channel name for Telegram links"
    )
    comments: List[CommentResponse] = Field(
        default_factory=list,
        description="List of comments on this post"
    )
    relevance_score: Optional[RelevanceLevel] = Field(
        default=None,
        description="Relevance score if available"
    )


class PostDetailResponse(BaseModel):
    """Response model for individual post details."""

    post_id: int = Field(
        ...,
        description="Post ID"
    )
    telegram_message_id: int = Field(
        ...,
        description="Original Telegram message ID"
    )
    channel_id: str = Field(
        ...,
        description="Channel ID"
    )
    channel_name: Optional[str] = Field(
        default=None,
        description="Channel name"
    )
    message_text: Optional[str] = Field(
        default=None,
        description="Post message text"
    )
    author_name: Optional[str] = Field(
        default=None,
        description="Post author name"
    )
    author_id: Optional[str] = Field(
        default=None,
        description="Post author ID"
    )
    created_at: datetime = Field(
        ...,
        description="When post was created"
    )
    edited_at: Optional[datetime] = Field(
        default=None,
        description="When post was edited"
    )
    view_count: int = Field(
        default=0,
        description="View count"
    )
    forward_count: int = Field(
        default=0,
        description="Forward count"
    )
    reply_count: int = Field(
        default=0,
        description="Reply count"
    )
    is_forwarded: bool = Field(
        default=False,
        description="Whether post is forwarded"
    )
    forward_from_channel: Optional[str] = Field(
        default=None,
        description="Channel post was forwarded from"
    )
    media_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Media metadata if any"
    )
    comments: List[CommentResponse] = Field(
        default_factory=list,
        description="Expert comments on this post"
    )
    incoming_links: List[LinkResponse] = Field(
        default_factory=list,
        description="Links pointing to this post"
    )
    outgoing_links: List[LinkResponse] = Field(
        default_factory=list,
        description="Links from this post to others"
    )


class ExpertResponse(BaseModel):
    """Response from a single expert."""

    expert_id: str = Field(
        ...,
        description="Expert identifier"
    )
    expert_name: str = Field(
        ...,
        description="Human-readable expert name"
    )
    channel_username: str = Field(
        ...,
        description="Telegram channel username"
    )
    answer: str = Field(
        ...,
        description="Synthesized answer with inline references"
    )
    main_sources: List[int] = Field(
        default_factory=list,
        description="Main source post IDs (telegram_message_ids)"
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level of the answer"
    )
    posts_analyzed: int = Field(
        ...,
        description="Total number of posts analyzed"
    )
    processing_time_ms: int = Field(
        ...,
        description="Processing time for this expert in milliseconds"
    )
    relevant_comment_groups: List[CommentGroupResponse] = Field(
        default_factory=list,
        description="Relevant comment groups found (optional)"
    )
    comment_groups_synthesis: Optional[str] = Field(
        default=None,
        description="Synthesized insights from comment groups (optional)"
    )


class MultiExpertQueryResponse(BaseModel):
    """Response containing results from multiple experts."""

    query: str = Field(
        ...,
        description="Original query"
    )
    expert_responses: List[ExpertResponse] = Field(
        default_factory=list,
        description="Responses from each expert"
    )
    total_processing_time_ms: int = Field(
        ...,
        description="Total processing time across all experts"
    )
    request_id: str = Field(
        ...,
        description="Unique request ID for tracking"
    )


# Helper functions
def get_expert_name(expert_id: str) -> str:
    """Get display name for expert from database.

    UPDATED (Migration 009): Now queries expert_metadata table instead of hardcoded dict.

    Args:
        expert_id: Expert identifier (e.g., 'refat')

    Returns:
        Display name (e.g., 'Refat (Tech & AI)') or expert_id if not found
    """
    from ..models.base import SessionLocal
    from ..models.expert import Expert

    db = SessionLocal()
    try:
        expert = db.query(Expert).filter(Expert.expert_id == expert_id).first()
        return expert.display_name if expert else expert_id
    finally:
        db.close()


def get_channel_username(expert_id: str) -> str:
    """Get Telegram channel username for expert from database.

    UPDATED (Migration 009): Now queries expert_metadata table instead of hardcoded dict.

    Args:
        expert_id: Expert identifier (e.g., 'refat')

    Returns:
        Channel username (e.g., 'nobilix') or expert_id if not found
    """
    from ..models.base import SessionLocal
    from ..models.expert import Expert

    db = SessionLocal()
    try:
        expert = db.query(Expert).filter(Expert.expert_id == expert_id).first()
        return expert.channel_username if expert else expert_id
    finally:
        db.close()