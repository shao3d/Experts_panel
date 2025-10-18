"""Comment-related API endpoints for expert comment collection."""

import uuid
from datetime import datetime
from typing import List, Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from .models import CommentResponse
from ..models.base import SessionLocal
from ..models.comment import Comment
from ..models.post import Post

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["comments"])


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CommentCreateRequest(BaseModel):
    """Request model for creating a comment."""

    post_id: int = Field(
        ...,
        description="ID of the post to comment on"
    )
    comment_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Comment text (markdown supported)"
    )
    author_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the comment author/expert"
    )
    author_id: Optional[str] = Field(
        None,
        description="Optional author ID for tracking"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID for workflow tracking"
    )


class CommentUpdateRequest(BaseModel):
    """Request model for updating a comment."""

    comment_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Updated comment text"
    )


class CommentsListResponse(BaseModel):
    """Response with list of comments."""

    comments: List[CommentResponse] = Field(
        default_factory=list,
        description="List of comments"
    )
    total: int = Field(
        0,
        description="Total number of comments"
    )
    post_id: int = Field(
        ...,
        description="Post ID these comments belong to"
    )


class NextPostResponse(BaseModel):
    """Response for next post to review."""

    post_id: Optional[int] = Field(
        None,
        description="Next post ID to review, None if no more posts"
    )
    message_text: Optional[str] = Field(
        None,
        description="Post content preview"
    )
    author_name: Optional[str] = Field(
        None,
        description="Post author"
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Post creation time"
    )
    total_posts: int = Field(
        ...,
        description="Total number of posts"
    )
    reviewed_posts: int = Field(
        ...,
        description="Number of posts with comments"
    )
    remaining_posts: int = Field(
        ...,
        description="Number of posts without comments"
    )


@router.get("/posts/{post_id}/comments", response_model=CommentsListResponse)
async def get_post_comments(
    post_id: int,
    db: Session = Depends(get_db)
) -> CommentsListResponse:
    """
    Get all comments for a specific post.

    Args:
        post_id: ID of the post
        db: Database session

    Returns:
        List of comments for the post
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Getting comments for post {post_id} - Request {request_id}")

    # Check if post exists
    post = db.query(Post).filter(Post.post_id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail=f"Post with ID {post_id} not found"
        )

    # Get all comments for this post
    comments = db.query(Comment).filter(
        Comment.post_id == post_id
    ).order_by(Comment.created_at.desc()).all()

    # Convert to response models
    comment_responses = []
    for comment in comments:
        comment_responses.append(CommentResponse(
            comment_id=comment.comment_id,
            comment_text=comment.comment_text,
            author_name=comment.author_name,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        ))

    logger.info(f"Found {len(comments)} comments for post {post_id}")

    return CommentsListResponse(
        comments=comment_responses,
        total=len(comment_responses),
        post_id=post_id
    )


@router.post("/comments/collect", response_model=CommentResponse)
async def create_comment(
    request: CommentCreateRequest,
    db: Session = Depends(get_db)
) -> CommentResponse:
    """
    Create a new comment for a post.

    Args:
        request: Comment creation request
        db: Database session

    Returns:
        Created comment
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Creating comment for post {request.post_id} by {request.author_name} - Request {request_id}")

    # Check if post exists
    post = db.query(Post).filter(Post.post_id == request.post_id).first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail=f"Post with ID {request.post_id} not found"
        )

    # Check if comment already exists from this author for this post
    existing_comment = db.query(Comment).filter(
        Comment.post_id == request.post_id,
        Comment.author_name == request.author_name
    ).first()

    if existing_comment:
        # Update existing comment
        existing_comment.comment_text = request.comment_text
        existing_comment.updated_at = datetime.utcnow()
        if request.author_id:
            existing_comment.author_id = request.author_id

        db.commit()
        db.refresh(existing_comment)

        logger.info(f"Updated existing comment {existing_comment.comment_id}")

        return CommentResponse(
            comment_id=existing_comment.comment_id,
            comment_text=existing_comment.comment_text,
            author_name=existing_comment.author_name,
            created_at=existing_comment.created_at,
            updated_at=existing_comment.updated_at
        )

    # Create new comment
    new_comment = Comment(
        post_id=request.post_id,
        comment_text=request.comment_text,
        author_name=request.author_name,
        author_id=request.author_id or request.session_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    logger.info(f"Created new comment {new_comment.comment_id}")

    return CommentResponse(
        comment_id=new_comment.comment_id,
        comment_text=new_comment.comment_text,
        author_name=new_comment.author_name,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at
    )


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    request: CommentUpdateRequest,
    db: Session = Depends(get_db)
) -> CommentResponse:
    """
    Update an existing comment.

    Args:
        comment_id: ID of comment to update
        request: Update request
        db: Database session

    Returns:
        Updated comment
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Updating comment {comment_id} - Request {request_id}")

    # Get comment
    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(
            status_code=404,
            detail=f"Comment with ID {comment_id} not found"
        )

    # Update comment
    comment.comment_text = request.comment_text
    comment.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(comment)

    logger.info(f"Updated comment {comment_id}")

    return CommentResponse(
        comment_id=comment.comment_id,
        comment_text=comment.comment_text,
        author_name=comment.author_name,
        created_at=comment.created_at,
        updated_at=comment.updated_at
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """
    Delete a comment.

    Args:
        comment_id: ID of comment to delete
        db: Database session

    Returns:
        Success message
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Deleting comment {comment_id} - Request {request_id}")

    # Get comment
    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(
            status_code=404,
            detail=f"Comment with ID {comment_id} not found"
        )

    # Delete comment
    db.delete(comment)
    db.commit()

    logger.info(f"Deleted comment {comment_id}")

    return {"message": f"Comment {comment_id} deleted successfully"}


@router.get("/comments/next-post", response_model=NextPostResponse)
async def get_next_post_for_review(
    session_id: Optional[str] = Query(None, description="Session ID for tracking progress"),
    skip_commented: bool = Query(True, description="Skip posts that already have comments"),
    db: Session = Depends(get_db)
) -> NextPostResponse:
    """
    Get the next post that needs expert comments.

    Args:
        session_id: Optional session ID for workflow tracking
        skip_commented: Whether to skip posts with existing comments
        db: Database session

    Returns:
        Next post to review or None if all posts reviewed
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Getting next post for review - Session: {session_id} - Request {request_id}")

    # Get total post count
    total_posts = db.query(Post).count()

    # Get posts with comments
    posts_with_comments = db.query(Comment.post_id).distinct().count()

    # Find next post
    if skip_commented:
        # Find posts without any comments
        subquery = db.query(Comment.post_id).distinct()
        next_post = db.query(Post).filter(
            ~Post.post_id.in_(subquery)
        ).order_by(Post.created_at).first()
    else:
        # Just get the next post by creation date
        next_post = db.query(Post).order_by(Post.created_at).first()

    if next_post:
        return NextPostResponse(
            post_id=next_post.post_id,
            message_text=next_post.message_text[:200] if next_post.message_text else None,
            author_name=next_post.author_name,
            created_at=next_post.created_at,
            total_posts=total_posts,
            reviewed_posts=posts_with_comments,
            remaining_posts=total_posts - posts_with_comments
        )
    else:
        # No more posts to review
        return NextPostResponse(
            post_id=None,
            message_text=None,
            author_name=None,
            created_at=None,
            total_posts=total_posts,
            reviewed_posts=posts_with_comments,
            remaining_posts=0
        )


@router.post("/comments/batch", response_model=List[CommentResponse])
async def create_batch_comments(
    comments: List[CommentCreateRequest],
    db: Session = Depends(get_db)
) -> List[CommentResponse]:
    """
    Create multiple comments in a single request.

    Args:
        comments: List of comments to create
        db: Database session

    Returns:
        List of created comments
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Creating batch of {len(comments)} comments - Request {request_id}")

    created_comments = []

    for comment_request in comments:
        # Check if post exists
        post = db.query(Post).filter(Post.post_id == comment_request.post_id).first()
        if not post:
            logger.warning(f"Post {comment_request.post_id} not found, skipping")
            continue

        # Check for existing comment
        existing_comment = db.query(Comment).filter(
            Comment.post_id == comment_request.post_id,
            Comment.author_name == comment_request.author_name
        ).first()

        if existing_comment:
            # Update existing
            existing_comment.comment_text = comment_request.comment_text
            existing_comment.updated_at = datetime.utcnow()
            if comment_request.author_id:
                existing_comment.author_id = comment_request.author_id

            created_comments.append(CommentResponse(
                comment_id=existing_comment.comment_id,
                comment_text=existing_comment.comment_text,
                author_name=existing_comment.author_name,
                created_at=existing_comment.created_at,
                updated_at=existing_comment.updated_at
            ))
        else:
            # Create new
            new_comment = Comment(
                post_id=comment_request.post_id,
                comment_text=comment_request.comment_text,
                author_name=comment_request.author_name,
                author_id=comment_request.author_id or comment_request.session_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_comment)

            # Need to flush to get the ID
            db.flush()

            created_comments.append(CommentResponse(
                comment_id=new_comment.comment_id,
                comment_text=new_comment.comment_text,
                author_name=new_comment.author_name,
                created_at=new_comment.created_at,
                updated_at=new_comment.updated_at
            ))

    # Commit all changes
    db.commit()

    logger.info(f"Created/updated {len(created_comments)} comments in batch")

    return created_comments