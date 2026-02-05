"""Main API endpoint for processing queries through the multi-expert pipeline.

This module orchestrates the entire query processing flow, including:
- Receiving the user query via a POST request.
- Spawning parallel processing tasks for each configured expert.
- Orchestrating the multi-phase pipeline (Map, Score, Resolve, Reduce, etc.) for each expert.
- Streaming real-time progress updates to the client via Server-Sent Events (SSE).
- Assembling and returning the final multi-expert response.
It also includes endpoints for retrieving individual post details.
"""

import asyncio
import json
import uuid
import time
from typing import AsyncGenerator, Optional, Callable
import logging
import os

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from .models import (
    QueryRequest,
    QueryResponse,
    ProgressEvent,
    TokenUsage,
    SimplifiedPostDetailResponse,
    CommentResponse,
    CommentGroupResponse,
    AnchorPost,
    ExpertResponse,
    MultiExpertQueryResponse,
    RedditResponse,
    RedditSource,
    ConfidenceLevel,
    get_expert_name,
    get_channel_username
)
from .. import config
from ..models.base import SessionLocal
from ..models.post import Post
from ..models.comment import Comment
from ..services.map_service import MapService
from ..services.simple_resolve_service import SimpleResolveService
from ..services.reduce_service import ReduceService
from ..services.comment_group_map_service import CommentGroupMapService
from ..services.comment_synthesis_service import CommentSynthesisService
from ..services.medium_scoring_service import MediumScoringService
from ..services.translation_service import TranslationService
from ..services.language_validation_service import LanguageValidationService
from ..services.reddit_client import search_reddit
from ..services.reddit_synthesis_service import RedditSynthesisService
from ..services.reddit_service import RedditSearchResult, RedditSource as RS
from ..utils.error_handler import error_handler
from ..utils.date_utils import get_cutoff_date

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["query"])


def sanitize_for_json(obj):
    """Recursively sanitize all strings in nested data structures for safe JSON transmission.

    Removes invalid escape sequences that would break JSON.parse() on frontend.
    """
    import re

    if isinstance(obj, str):
        # Remove invalid escape sequences, keep only valid JSON escapes: \n \t \r \" \/ \\
        return re.sub(r'\\(?![ntr"\\/])', '', obj)
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    else:
        return obj


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




async def process_expert_pipeline(
    expert_id: str,
    request: QueryRequest,
    db: Session,
    progress_callback: Optional[Callable] = None
) -> ExpertResponse:
    """Process full pipeline for one expert.

    Args:
        expert_id: Expert identifier
        request: Query request
        db: Database session
        progress_callback: Optional callback for progress updates

    Returns:
        ExpertResponse with answer from this expert
    """
    start_time = time.time()

    # 1. Calculate cutoff date if filtering enabled
    cutoff_date = None
    if request.use_recent_only:
        cutoff_date = get_cutoff_date(months=3)
        logger.info(f"[{expert_id}] use_recent_only enabled, cutoff_date: {cutoff_date.isoformat()}")

    # 2. Get posts for this expert (with optional date filter)
    query = db.query(Post).filter(Post.expert_id == expert_id)

    if cutoff_date:
        query = query.filter(Post.created_at >= cutoff_date)

    # Order by date first (newest first), then apply limit
    query = query.order_by(Post.created_at.desc())

    if request.max_posts is not None:
        query = query.limit(request.max_posts)

    posts = query.all()

    if not posts:
        return ExpertResponse(
            expert_id=expert_id,
            expert_name=get_expert_name(expert_id),
            channel_username=get_channel_username(expert_id),
            answer="Нет данных от этого эксперта для ответа на вопрос.",
            main_sources=[],
            confidence=ConfidenceLevel.LOW,
            posts_analyzed=0,
            processing_time_ms=int((time.time() - start_time) * 1000),
            relevant_comment_groups=[],
            comment_groups_synthesis=None
        )

    # 2. Map phase
    map_service = MapService(
        model=config.MODEL_MAP,
        max_parallel=config.MAP_MAX_PARALLEL
    )

    async def map_progress(data: dict):
        if progress_callback:
            data['expert_id'] = expert_id
            await progress_callback(data)

    map_results = await map_service.process(
        posts=posts,
        query=request.query,
        expert_id=expert_id,
        progress_callback=map_progress
    )

    relevant_posts = map_results.get("relevant_posts", [])

    # 3. NEW: Split HIGH and MEDIUM posts after Map phase
    high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
    medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

    # Create a lookup map for quick access to full post objects by ID
    posts_by_id = {p.telegram_message_id: p for p in posts}

    # 4. NEW: Score MEDIUM posts and filter (two-stage: score >= 0.7 → top-5)
    selected_medium_posts = []
    if medium_posts:
        from ..services.medium_scoring_service import MediumScoringService

        # Use Google Gemini with automatic key rotation
        scoring_service = MediumScoringService(
            model=config.MODEL_MEDIUM_SCORING
        )

        # Enrich medium_posts with full content before passing to the scoring service
        medium_posts_with_content = []
        for post_meta in medium_posts:
            post_id = post_meta["telegram_message_id"]
            if post_id in posts_by_id:
                full_post = posts_by_id[post_id]
                # Combine metadata from map_service with content from original post object
                enriched_post = {
                    **post_meta,
                    "content": full_post.message_text or "",
                    "author": full_post.author_name or "Unknown",
                    "created_at": full_post.created_at.isoformat() if full_post.created_at else ""
                }
                medium_posts_with_content.append(enriched_post)

        # Debug logging to verify enriched data
        logger.debug(f"[{expert_id}] DEBUG: Enriched {len(medium_posts_with_content)} medium posts with content")
        if medium_posts_with_content:
            first_post = medium_posts_with_content[0]
            logger.debug(f"[{expert_id}] DEBUG: First enriched medium post: ID={first_post.get('telegram_message_id')}, "
                        f"content_len={len(first_post.get('content', ''))}, "
                        f"content_preview='{first_post.get('content', '')[:100]}...'")

        async def scoring_progress(data: dict):
            if progress_callback:
                data['expert_id'] = expert_id
                await progress_callback(data)

        # Create context from HIGH posts
        high_context = json.dumps([
            {
                "telegram_message_id": p["telegram_message_id"],
                "content": p.get("content", ""),
                "reason": p.get("reason", "")
            }
            for p in high_posts
        ], ensure_ascii=False, indent=2)

        # Score MEDIUM posts
        try:
            scored_medium_posts = await scoring_service.score_medium_posts(
                medium_posts=medium_posts_with_content,
                high_posts_context=high_context,
                query=request.query,
                expert_id=expert_id,
                progress_callback=scoring_progress
            )

            # Filter by score >= 0.7, then top-5 by highest score
            above_threshold = [p for p in scored_medium_posts if p.get("score", 0) >= 0.7]
            selected_medium_posts = sorted(
                above_threshold,
                key=lambda x: x.get("score", 0),
                reverse=True
            )[:5]  # Max 5 posts

            # Debug logging for scoring results
            logger.info(f"[{expert_id}] Medium reranking: {len(medium_posts_with_content)} → {len(scored_medium_posts)} scored → {len(above_threshold)} posts (score >= 0.7) → {len(selected_medium_posts)} selected (max 5)")

            if scored_medium_posts:
                logger.debug(f"[{expert_id}] DEBUG: Medium post scores: {[(p.get('telegram_message_id'), p.get('score', 0)) for p in scored_medium_posts[:3]]}")
        except Exception as e:
            logger.error(f"[{expert_id}] Medium scoring failed: {e}")
            # Fallback: use empty list (graceful degradation)
            selected_medium_posts = []

    # 5. NEW: Differential Resolve processing
    enriched_posts = []

    # Process HIGH posts through Resolve (with linked posts)
    if high_posts:
        resolve_service = SimpleResolveService()

        async def resolve_progress(data: dict):
            if progress_callback:
                data['expert_id'] = expert_id
                await progress_callback(data)

        high_resolve_results = await resolve_service.process(
            relevant_posts=high_posts,
            query=request.query,
            expert_id=expert_id,  # CRITICAL: Pass expert_id
            cutoff_date=cutoff_date,  # Pass cutoff_date for filtering linked posts
            progress_callback=resolve_progress
        )

        # HIGH posts get linked context posts
        high_enriched = high_resolve_results.get("enriched_posts", [])
        enriched_posts.extend(high_enriched)

    # Selected MEDIUM posts bypass Resolve (direct inclusion)
    medium_direct = [
        {
            "telegram_message_id": p["telegram_message_id"],
            "relevance": "MEDIUM",
            "reason": p.get("reason", ""),
            "content": p.get("content", ""),
            "author": p.get("author", ""),
            "created_at": p.get("created_at", ""),
            "is_original": True,  # Critical: not CONTEXT posts
            "score": p.get("score", 0.0),
            "score_reason": p.get("score_reason", "")
        }
        for p in selected_medium_posts
    ]
    enriched_posts.extend(medium_direct)

    # --- CHRONOLOGY FIX: Sort posts by Relevance then by Date (Newest First) ---
    # Strategy: Python sort is stable.
    # 1. Global Sort: Date Descending (Newest first)
    enriched_posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # 2. Stable Sort: Relevance Ascending (HIGH=0, MEDIUM=1).
    # This keeps High posts at the top, but preserves the Date ordering within the High group.
    relevance_priority = {"HIGH": 0, "MEDIUM": 1}
    enriched_posts.sort(key=lambda x: relevance_priority.get(x.get("relevance", "LOW"), 2))

    # 5. Reduce phase
    reduce_service = ReduceService()

    async def reduce_progress(data: dict):
        if progress_callback:
            data['expert_id'] = expert_id
            await progress_callback(data)

    reduce_results = await reduce_service.process(
        enriched_posts=enriched_posts,
        query=request.query,
        expert_id=expert_id,
        progress_callback=reduce_progress
    )

    # 5. NEW: Language Validation Phase
    language_validation_service = LanguageValidationService(
        model=config.MODEL_ANALYSIS
    )

    async def validation_progress(data: dict):
        if progress_callback:
            data['expert_id'] = expert_id
            await progress_callback(data)

    validation_results = await language_validation_service.process(
        answer=reduce_results.get("answer", ""),
        query=request.query,
        expert_id=expert_id,
        progress_callback=validation_progress
    )

    # Use validated answer for subsequent phases
    validated_answer = validation_results.get("answer", reduce_results.get("answer", ""))

    # 6. Comment Groups (optional)
    comment_groups = []
    comment_group_results = []  # Raw results from service (preserves is_main_source_clarification)
    comment_synthesis = None

    print(f"[DEBUG] include_comment_groups={request.include_comment_groups}")  # DEBUG

    if request.include_comment_groups:
        main_sources = reduce_results.get("main_sources", [])

        # Use Google Gemini with automatic key rotation
        cg_service = CommentGroupMapService(
            model=config.MODEL_COMMENT_GROUPS
        )

        async def cg_progress(data: dict):
            if progress_callback:
                data['expert_id'] = expert_id
                await progress_callback(data)

        print(f"[DEBUG] Calling cg_service.process for expert {expert_id}")  # DEBUG

        comment_group_results = await cg_service.process(
            query=request.query,
            db=db,
            expert_id=expert_id,  # CRITICAL: Pass expert_id
            exclude_post_ids=main_sources,  # Exclude main_sources from drift search
            main_source_ids=main_sources,   # NEW: Extract author clarifications from main_sources
            cutoff_date=cutoff_date,  # Pass cutoff_date for filtering drift groups
            progress_callback=cg_progress
        )

        print(f"[DEBUG] comment_group_results count: {len(comment_group_results)}")  # DEBUG

        # Convert to response format
        seen_parent_ids = set()
        for group in comment_group_results:
            # Deduplicate groups by parent message ID
            if group["parent_telegram_message_id"] in seen_parent_ids:
                continue
            seen_parent_ids.add(group["parent_telegram_message_id"])

            anchor_post_data = group["anchor_post"]

            # Convert comments
            comments = [
                CommentResponse(
                    comment_id=c["comment_id"],
                    comment_text=c["comment_text"],
                    author_name=c["author_name"],
                    created_at=c["created_at"],
                    updated_at=c["updated_at"]
                )
                for c in group.get("comments", [])
            ]

            comment_groups.append(CommentGroupResponse(
                parent_telegram_message_id=group["parent_telegram_message_id"],
                relevance=group["relevance"],
                reason=group["reason"],
                comments_count=group["comments_count"],
                anchor_post=AnchorPost(
                    telegram_message_id=anchor_post_data["telegram_message_id"],
                    message_text=anchor_post_data["message_text"],
                    created_at=anchor_post_data["created_at"],
                    author_name=anchor_post_data["author_name"],
                    channel_username=get_channel_username(expert_id)  # Use helper function
                ),
                comments=comments
            ))

        # Comment Synthesis (if we have relevant comment groups)
        # IMPORTANT: Use original comment_group_results, not converted Pydantic models
        # This preserves is_main_source_clarification flag for proper synthesis prioritization
        if comment_group_results:
            try:
                synthesis_service = CommentSynthesisService()
                comment_synthesis = await synthesis_service.process(
                    query=request.query,
                    main_answer=validated_answer,  # Use validated answer
                    comment_groups=comment_group_results,  # Use original results with all fields!
                    expert_id=expert_id
                )
            except Exception as e:
                logger.error(f"Comment synthesis failed for expert {expert_id}: {e}")

    # 7. Build response
    processing_time = int((time.time() - start_time) * 1000)

    return ExpertResponse(
        expert_id=expert_id,
        expert_name=get_expert_name(expert_id),
        channel_username=get_channel_username(expert_id),
        answer=sanitize_for_json(validated_answer),  # Use validated answer
        main_sources=reduce_results.get("main_sources", []),
        confidence=reduce_results.get("confidence", ConfidenceLevel.MEDIUM),
        posts_analyzed=reduce_results.get("posts_analyzed", 0),
        processing_time_ms=processing_time,
        relevant_comment_groups=sanitize_for_json(comment_groups),
        comment_groups_synthesis=sanitize_for_json(comment_synthesis) if comment_synthesis else None
    )


async def process_reddit_pipeline(
    query: str,
    progress_callback: Optional[Callable] = None
) -> Optional[RedditResponse]:
    """Process Reddit community pipeline using direct Reddit API (asyncpraw).
    
    Direct Reddit API integration with OAuth authentication.
    
    Args:
        query: User query (will be translated to English if Russian)
        progress_callback: Optional callback for progress updates
        
    Returns:
        RedditResponse with community insights or None if failed/no results
    """
    import time
    start_time = time.time()
    
    # Detect query language and translate if needed
    from ..utils.language_utils import detect_query_language
    query_language = detect_query_language(query)
    
    search_query = query
    if query_language == "Russian":
        try:
            from ..services.google_ai_studio_client import create_google_ai_studio_client
            client = create_google_ai_studio_client()
            
            prompt = f"""Convert this Russian question into an optimal English search query for Reddit.

Rules:
1. Use only key concepts (no fluff words like "which", "should", "how")
2. 4-6 words maximum  
3. Think: what keywords would Reddit users use?
4. Output ONLY the search query, nothing else

Question: {query}

Search query:"""
            
            response = await client.chat_completions_create(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            search_query = response.choices[0].message.content.strip()
            search_query = search_query.strip('"\'')
            
            logger.info(f"Gemini formulated Reddit query: '{query[:50]}...' -> '{search_query}'")
        except Exception as e:
            logger.warning(f"Failed to formulate Reddit query: {e}")
            search_query = query
    
    try:
        # Report start
        if progress_callback:
            await progress_callback({
                "phase": "reddit_pipeline",
                "status": "starting",
                "message": "Starting Reddit search...",
                "source": "reddit"
            })
        
        # Search Reddit using asyncpraw
        if progress_callback:
            await progress_callback({
                "phase": "reddit_search",
                "status": "processing",
                "message": f"Searching Reddit for: {search_query[:50]}...",
                "source": "reddit"
            })
        
        reddit_result = await search_reddit(
            query=search_query,
            limit=25,
            time_filter="all",
            sort="relevance"
        )
        
        # Check if we found anything relevant
        if not reddit_result.posts:
            logger.info(f"No Reddit posts found for query: {search_query}")
            if progress_callback:
                await progress_callback({
                    "phase": "reddit_search",
                    "status": "complete",
                    "message": "No relevant discussions found",
                    "source": "reddit",
                    "found_count": 0
                })
            return None
        
        logger.info(f"Found {len(reddit_result.posts)} Reddit posts via asyncpraw")
        
        if progress_callback:
            await progress_callback({
                "phase": "reddit_search",
                "status": "complete",
                "message": f"Found {len(reddit_result.posts)} relevant posts",
                "source": "reddit",
                "found_count": len(reddit_result.posts)
            })
        
        # Build sources for synthesis
        sources = []
        for post in reddit_result.posts:
            sources.append(RS(
                title=post.title or "Untitled",
                url=post.permalink,
                score=post.score or 0,
                comments_count=post.num_comments or 0,
                subreddit=post.subreddit or "unknown",
                content=post.selftext or ""
            ))
        
        # Build markdown for display
        markdown = _build_reddit_markdown(reddit_result)
        
        # Synthesize with Gemini
        if progress_callback:
            await progress_callback({
                "phase": "reddit_synthesis",
                "status": "processing",
                "message": "Analyzing community discussions...",
                "source": "reddit"
            })
        
        synthesis_service = RedditSynthesisService()
        
        search_result = RedditSearchResult(
            markdown=markdown,
            found_count=len(reddit_result.posts),
            sources=sources,
            query=search_query,
            processing_time_ms=reddit_result.processing_time_ms
        )
        
        synthesis = await synthesis_service.synthesize(query, search_result)
        
        if progress_callback:
            await progress_callback({
                "phase": "reddit_synthesis",
                "status": "complete",
                "message": "Analysis complete",
                "source": "reddit"
            })
        
        # Build response
        reddit_response = RedditResponse(
            markdown=markdown,
            synthesis=synthesis,
            found_count=len(reddit_result.posts),
            sources=[
                RedditSource(
                    title=src.title,
                    url=src.url,
                    score=src.score,
                    comments_count=src.comments_count,
                    subreddit=src.subreddit
                )
                for src in search_result.sources
            ],
            query=search_query,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )
        
        if progress_callback:
            await progress_callback({
                "phase": "reddit_pipeline",
                "status": "completed",
                "message": f"Reddit analysis complete: {reddit_response.found_count} posts",
                "source": "reddit",
                "found_count": reddit_response.found_count
            })
        
        return reddit_response
        
    except Exception as e:
        logger.error(f"Reddit pipeline error: {e}")
        if progress_callback:
            await progress_callback({
                "phase": "reddit_pipeline",
                "status": "error",
                "message": "Reddit analysis failed",
                "source": "reddit",
                "error": str(e)
            })
        return None


def _build_reddit_markdown(result) -> str:
    """Build markdown from Reddit search result."""
    if not result.posts:
        return "No relevant Reddit discussions found."
    
    markdown_parts = []
    for i, post in enumerate(result.posts, 1):
        # Build content preview
        if post.selftext:
            content_preview = post.selftext[:500]
            if len(post.selftext) > 500:
                content_preview += "..."
        else:
            content_preview = ""
        
        markdown_parts.append(f"""### {i}. {post.title}

**r/{post.subreddit}** | ⬆️ {post.score} | 💬 {post.num_comments} comments

{content_preview}

[Read on Reddit]({post.permalink})""")
    
    return "\n\n---\n\n".join(markdown_parts)


async def event_generator_parallel(
    request: QueryRequest,
    db: Session,
    request_id: str
) -> AsyncGenerator[str, None]:
    """Generate SSE events for parallel multi-expert processing.

    Processes all experts in parallel, returns separate results for each.

    Args:
        request: Query request
        db: Database session
        request_id: Unique request ID

    Yields:
        SSE formatted events with multi-expert response
    """
    start_time = time.time()

    try:
        # Initial event
        event = ProgressEvent(
            event_type="start",
            phase="initialization",
            status="starting",
            message="Starting multi-expert query processing",
            data={"request_id": request_id, "query": request.query}
        )
        sanitized = sanitize_for_json(event.model_dump(mode='json'))
        yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"

        # 1. Determine which experts to process
        if request.expert_filter is not None:
            # Empty list [] means NO experts (Reddit-only mode)
            # Non-empty list means specific experts only
            expert_ids = request.expert_filter
        else:
            # Default: ALL experts from database
            expert_rows = db.query(Post.expert_id).distinct().filter(
                Post.expert_id.isnot(None)
            ).all()
            expert_ids = [row[0] for row in expert_rows if row[0]]

        if not expert_ids:
            error_event = ProgressEvent(
                event_type="error",
                phase="initialization",
                status="error",
                message="No experts found in database",
                data={"request_id": request_id}
            )
            yield f"data: {json.dumps(error_event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            return

        event = ProgressEvent(
            event_type="phase_start",
            phase="multi_expert",
            status="starting",
            message=f"Processing {len(expert_ids)} experts in parallel: {', '.join(expert_ids)}",
            data={"experts": expert_ids}
        )
        sanitized = sanitize_for_json(event.model_dump(mode='json'))
        yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"

        # 1.5. Start Reddit pipeline in parallel (if enabled)
        reddit_progress_queue = asyncio.Queue(maxsize=50)
        reddit_complete = False
        reddit_result: Optional[RedditResponse] = None

        # Check if Reddit search is enabled (default: true)
        include_reddit = request.include_reddit if request.include_reddit is not None else True

        async def reddit_progress_callback(data: dict):
            """Callback for Reddit pipeline progress."""
            event = ProgressEvent(
                event_type="progress",
                phase=f"reddit_{data.get('phase', 'pipeline')}",
                status=data.get('status', 'processing'),
                message=f"[Reddit] {data.get('message', 'Processing...')}",
                data={"source": "reddit", **data}
            )
            try:
                reddit_progress_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Reddit progress queue full, dropping event")

        async def run_reddit_pipeline():
            """Run Reddit pipeline and track completion."""
            nonlocal reddit_complete, reddit_result
            try:
                reddit_result = await process_reddit_pipeline(
                    query=request.query,
                    progress_callback=reddit_progress_callback
                )
            except Exception as e:
                logger.error(f"Reddit pipeline failed: {e}")
                reddit_result = None
            finally:
                reddit_complete = True
                # Send completion event
                try:
                    event = ProgressEvent(
                        event_type="reddit_complete" if reddit_result else "reddit_error",
                        phase="reddit_pipeline",
                        status="completed" if reddit_result else "error",
                        message=f"Reddit analysis: {reddit_result.found_count if reddit_result else 0} posts found" if reddit_result else "Reddit analysis failed",
                        data={
                            "source": "reddit",
                            "found_count": reddit_result.found_count if reddit_result else 0,
                            "success": reddit_result is not None
                        }
                    )
                    reddit_progress_queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

        # Launch Reddit pipeline as background task (only if enabled)
        if include_reddit:
            reddit_task = asyncio.create_task(run_reddit_pipeline())
        else:
            # Reddit disabled - mark as complete immediately with null result
            reddit_complete = True
            reddit_result = None
            # Create a dummy task for compatibility with rest of the code
            reddit_task = asyncio.create_task(asyncio.sleep(0))

        # 2. Create queue for real-time progress events
        # SECURITY: Limit queue size to prevent memory leaks
        progress_queue = asyncio.Queue(maxsize=100)  # Max 100 buffered events

        async def expert_progress_callback(data: dict):
            expert_id = data.get('expert_id', 'unknown')
            status = data.get("status", "processing")

            # Check if this is an error with error_info
            if status == "error" and "error_info" in data:
                # Use user-friendly error message from error_info
                error_info = data["error_info"]
                message = f"[{expert_id}] {error_info.get('title', 'Processing error')}"

                # Enhance data with error information
                enhanced_data = data.copy()
                enhanced_data.update({
                    "error_type": error_info.get("error_type"),
                    "user_message": error_info.get("message"),
                    "suggested_action": error_info.get("suggested_action"),
                    "user_friendly": error_info.get("user_friendly", True)
                })
            else:
                message = f"[{expert_id}] {data.get('message', 'Processing...')}"
                enhanced_data = data

            # Use original phase from service (map/resolve/reduce)
            event = ProgressEvent(
                event_type="progress",
                phase=data.get('phase', 'expert_pipeline'),  # Preserve original phase!
                status=status,
                message=message,
                data=enhanced_data
            )
            # SECURITY: Try to add event to queue, drop if full to prevent memory leaks
            try:
                progress_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Progress queue full for {expert_id}, dropping event")

        # 3. Launch background task to stream progress events
        async def stream_progress_events():
            """Stream progress events from queue in real-time with keep-alive."""
            last_activity_time = time.time()
            keep_alive_interval = 2.5  # Send keep-alive every 2.5 seconds (faster for Reddit)

            while True:
                event_yielded = False
                
                # Check expert progress queue
                try:
                    event = progress_queue.get_nowait()
                    sanitized = sanitize_for_json(event.model_dump(mode='json'))
                    yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                    last_activity_time = time.time()
                    event_yielded = True
                except asyncio.QueueEmpty:
                    pass
                
                # Check Reddit progress queue
                try:
                    event = reddit_progress_queue.get_nowait()
                    sanitized = sanitize_for_json(event.model_dump(mode='json'))
                    yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                    last_activity_time = time.time()
                    event_yielded = True
                except asyncio.QueueEmpty:
                    pass
                
                # If no events, wait a bit
                if not event_yielded:
                    try:
                        await asyncio.wait_for(asyncio.sleep(0.05), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass
                    
                    # Check if all tasks are done
                    expert_tasks_done = all(task.done() for _, task in tasks)
                    if expert_tasks_done and reddit_complete:
                        break
                    
                    # Send keep-alive while waiting for Reddit (can be slow)
                    if time.time() - last_activity_time > keep_alive_interval:
                        # Add 2KB of padding to force proxy buffer flush
                        padding = " " * 2048
                        yield f": keep-alive {padding}\n\n"
                        last_activity_time = time.time()

        # 4. Launch PARALLEL tasks for each expert
        tasks = []
        for expert_id in expert_ids:
            task = asyncio.create_task(
                process_expert_pipeline(
                    expert_id=expert_id,
                    request=request,
                    db=db,
                    progress_callback=expert_progress_callback
                )
            )
            tasks.append((expert_id, task))

        # 5. Stream progress events while waiting for completion
        expert_responses = []
        # FIX: Removed orphaned stream_task that was never used

        for expert_id, task in tasks:
            try:
                # Wait for both expert completion and stream events
                while not task.done():
                    # Try to get progress events from both queues
                    try:
                        event = progress_queue.get_nowait()
                        sanitized = sanitize_for_json(event.model_dump(mode='json'))
                        yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                    except asyncio.QueueEmpty:
                        pass
                    
                    # Check Reddit events
                    try:
                        event = reddit_progress_queue.get_nowait()
                        sanitized = sanitize_for_json(event.model_dump(mode='json'))
                        yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                    except asyncio.QueueEmpty:
                        pass

                    # Small delay to avoid busy loop
                    await asyncio.sleep(0.05)

                result = await task
                expert_responses.append(result)

                # Send any remaining events for this expert
                while not progress_queue.empty():
                    try:
                        event = progress_queue.get_nowait()
                        sanitized = sanitize_for_json(event.model_dump(mode='json'))
                        yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                event = ProgressEvent(
                    event_type="expert_complete",
                    phase="expert_pipeline",
                    status="completed",
                    message=f"Expert {expert_id} completed",
                    data={
                        "expert_id": expert_id,
                        "posts_analyzed": result.posts_analyzed,
                        "sources_found": len(result.main_sources)
                    }
                )
                sanitized = sanitize_for_json(event.model_dump(mode='json'))
                yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"Error processing expert {expert_id}: {e}")

                # Process error through error handler for user-friendly messaging
                error_info = error_handler.process_api_error(
                    e,
                    context={
                        "phase": "expert_pipeline",
                        "expert_id": expert_id,
                        "request_id": request_id
                    }
                )

                # Create user-friendly error event
                error_event = error_handler.create_error_event(
                    error_info,
                    event_type="expert_error"
                )

                event = ProgressEvent(
                    event_type="expert_error",
                    phase=error_event["phase"],
                    status="error",
                    message=error_event["message"],
                    data=error_event["data"]
                )
                sanitized = sanitize_for_json(event.model_dump(mode='json'))
                yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"

        # Wait for Reddit pipeline to complete (with timeout)
        # Reddit usually takes 10-30s (cold start + search), 30s is sufficient
        reddit_wait_start = time.time()
        reddit_timeout = 30.0  # 30 seconds max wait after experts complete
        last_activity_time_outer = time.time()  # FIX: Define in outer scope
        
        # FIX: Also check if task is done to avoid waiting full timeout if task crashed
        while (not reddit_complete and 
               (time.time() - reddit_wait_start) < reddit_timeout and
               not reddit_task.done()):
            # Send any Reddit progress events while waiting
            try:
                event = reddit_progress_queue.get_nowait()
                sanitized = sanitize_for_json(event.model_dump(mode='json'))
                yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
                last_activity_time_outer = time.time()
            except asyncio.QueueEmpty:
                pass
            
            # Send keep-alive while waiting
            if time.time() - last_activity_time_outer > 2.5:
                padding = " " * 2048
                yield f": keep-alive {padding}\n\n"
                last_activity_time_outer = time.time()
            
            await asyncio.sleep(0.1)
        
        # If Reddit still not complete, cancel it (but don't fail the whole request)
        if not reddit_complete and not reddit_task.done():
            reddit_task.cancel()
            logger.warning("Reddit pipeline timed out, proceeding without Reddit results")
            try:
                await reddit_task
            except asyncio.CancelledError:
                pass
            reddit_result = None
        elif not reddit_complete and reddit_task.done():
            # Task done but flag not set (error case)
            try:
                reddit_result = reddit_task.result()
            except asyncio.CancelledError:
                logger.warning("Reddit pipeline was cancelled")
                reddit_result = None
            except Exception as e:
                logger.error(f"Reddit pipeline failed: {e}")
                reddit_result = None

        # Send final Reddit events
        while not reddit_progress_queue.empty():
            try:
                event = reddit_progress_queue.get_nowait()
                sanitized = sanitize_for_json(event.model_dump(mode='json'))
                yield f"data: {json.dumps(sanitized, ensure_ascii=False)}\n\n"
            except asyncio.QueueEmpty:
                break

        # 5. Calculate total processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # 6. Build multi-expert response (including Reddit if available)
        response = MultiExpertQueryResponse(
            query=request.query,
            expert_responses=expert_responses,
            reddit_response=reddit_result,  # NEW: Include Reddit results
            total_processing_time_ms=processing_time_ms,
            request_id=request_id
        )

        # 7. Send final result
        reddit_message = ""
        if reddit_result:
            reddit_message = f" | Reddit: {reddit_result.found_count} posts"
        elif include_reddit and reddit_result is None and reddit_complete:
            # Only show "unavailable" if Reddit was enabled but failed/unavailable
            reddit_message = " | Reddit: unavailable"
        
        event = ProgressEvent(
            event_type="complete",
            phase="final",
            status="success",
            message=f"Query completed: {len(expert_responses)} experts{reddit_message}",
            data={"response": response.model_dump(mode='json')}
        )

        sanitized_event = sanitize_for_json(event.model_dump(mode='json'))
        yield f"data: {json.dumps(sanitized_event, ensure_ascii=False)}\n\n"

    except Exception as e:
        import traceback
        logger.error(f"Error processing multi-expert query {request_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Process error through error handler for user-friendly messaging
        error_info = error_handler.process_api_error(
            e,
            context={
                "phase": "global",
                "request_id": request_id
            }
        )

        # Create user-friendly error event
        error_event_data = error_handler.create_error_event(
            error_info,
            event_type="error"
        )

        error_event = ProgressEvent(
            event_type=error_event_data["event_type"],
            phase=error_event_data["phase"],
            status=error_event_data["status"],
            message=error_event_data["message"],
            data=error_event_data["data"]
        )
        yield f"data: {json.dumps(error_event.model_dump(mode='json'), ensure_ascii=False)}\n\n"



@router.post("/query")
async def process_simplified_query(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """Process a query through parallel multi-expert pipeline with SSE streaming.

    Always processes all experts in parallel and returns SSE stream.
    No synchronous mode - streaming is always enabled.

    Args:
        request: Query request with user's question
        db: Database session

    Returns:
        SSE stream with multi-expert responses
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Processing multi-expert query {request_id}: {request.query[:50]}...")

    # Always return SSE stream with parallel multi-expert processing
    return EventSourceResponse(
        event_generator_parallel(request, db, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id
        }
    )


def validate_post_id(post_id: int) -> int:
    """Validate post_id parameter to prevent database issues."""
    if post_id <= 0 or post_id > 10_000_000:  # Reasonable range for Telegram message IDs
        raise HTTPException(
            status_code=400,
            detail="Invalid post_id. Must be between 1 and 10,000,000"
        )
    return post_id


def validate_expert_id(expert_id: str) -> str:
    """Basic validation for expert_id parameter."""
    import re
    if not expert_id or not re.match(r'^[a-zA-Z0-9_-]+$', expert_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid expert_id format. Only letters, numbers, underscores and hyphens allowed"
        )
    return expert_id


@router.get("/posts/{post_id}", response_model=SimplifiedPostDetailResponse)
async def get_post_detail(
    post_id: int,
    expert_id: Optional[str] = None,
    query: Optional[str] = None,
    translate: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    # Validate parameters
    post_id = validate_post_id(post_id)
    if expert_id:
        expert_id = validate_expert_id(expert_id)
    """Get detailed information about a specific post.

    Args:
        post_id: Telegram message ID of the post
        expert_id: Optional expert ID to filter posts (required for multi-expert)
        query: Optional user query to determine if translation is needed
        translate: Boolean flag to force translation
        db: Database session

    Returns:
        SimplifiedPostDetailResponse with post content and comments
    """
    # Find post in database - filter by expert_id to avoid cross-expert conflicts
    post_query = db.query(Post).filter(Post.telegram_message_id == post_id)
    if expert_id:
        post_query = post_query.filter(Post.expert_id == expert_id)
    post = post_query.first()

    if not post:
        raise HTTPException(
            status_code=404,
            detail=f"Post with ID {post_id} not found"
        )

    # Convert comments to response format
    comments = []
    if post.comments:
        for comment in post.comments:
            comments.append(CommentResponse(
                comment_id=comment.comment_id,
                author_name=comment.author_name,
                comment_text=comment.comment_text,
                created_at=comment.created_at,
                updated_at=comment.updated_at
            ))

    # Determine if translation is needed
    should_translate = False
    logger.info(f"DEBUG: get_post_detail called with post_id={post_id}, expert_id={expert_id}, query='{query}', translate={translate}")

    if translate:
        should_translate = True
        logger.info(f"DEBUG: Translation forced by translate=true flag for post {post_id}")
    elif query:
        # Use translation service to detect if query is in English
        translation_service = TranslationService(
            model=config.MODEL_ANALYSIS
        )
        should_translate = translation_service.should_translate(query)
        logger.info(f"DEBUG: Translation check for post {post_id}: query='{query[:50]}...', should_translate={should_translate}")
    else:
        logger.info(f"DEBUG: No translation for post {post_id}: no query provided")

    # Translate post content if needed
    message_text = post.message_text or ""
    logger.info(f"DEBUG: Before translation - should_translate={should_translate}, message_text_length={len(message_text)}")

    if should_translate and message_text:
        logger.info(f"DEBUG: Starting translation for post {post_id} with content length {len(message_text)}")
        try:
            # Use Google Gemini for translation
            translation_service = TranslationService(
                model=config.MODEL_ANALYSIS
            )
            translated_text = await translation_service.translate_single_post(
                message_text,
                post.author_name or "Unknown"
            )
            message_text = translated_text
            logger.info(f"DEBUG: Successfully translated post {post_id} to English for query: {query[:50]}...")
        except Exception as e:
            logger.error(f"DEBUG: Translation failed for post {post_id}: {e}")
            # Keep original text if translation fails
    else:
        logger.info(f"DEBUG: Skipping translation for post {post_id} - should_translate={should_translate}, has_content={bool(message_text)}")

    # Get channel username from expert_id using helper function
    channel_username = get_channel_username(post.expert_id) if post.expert_id else post.channel_name

    # Create response
    return SimplifiedPostDetailResponse(
        telegram_message_id=post.telegram_message_id,
        author_name=post.author_name or "Unknown",
        message_text=message_text,
        created_at=post.created_at.isoformat() if post.created_at else "",
        channel_name=channel_username,  # Use username for Telegram links
        comments=comments,
        relevance_score=None  # Not available for individual post fetch
    )
