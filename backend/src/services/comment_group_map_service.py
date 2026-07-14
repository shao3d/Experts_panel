"""Comment Group Map service for finding relevant comment groups."""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import re
import logging
from pathlib import Path
from string import Template

import numpy as np
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from ..models.post import Post
from ..models.comment import Comment
from ..models.database import comment_group_drift
from .vertex_llm_client import get_vertex_llm_client, VertexLLMError
from .embedding_service import get_embedding_service
from .. import config
from ..api.models import get_channel_username
from ..utils.language_utils import prepare_prompt_with_language_instruction

logger = logging.getLogger(__name__)


def build_drift_text(drift_topics_json: str) -> str:
    """Build a dense text representation of drift_topics for embedding.

    Used in three places:
    1. ``drift_scheduler_service`` — embed new drift_topics at sync time.
    2. ``backfill_drift_embeddings.py`` — one-shot embed for legacy rows.
    3. (Future) display or re-ranking.

    Concatenates topic, keywords, key_phrases and context. Excludes the
    anchor-post text on purpose: the embedding should represent *what the
    comments drifted to*, not the original post topic.
    """
    if not drift_topics_json:
        return ""
    try:
        if isinstance(drift_topics_json, bytes):
            drift_topics_json = drift_topics_json.decode("utf-8")
        data = json.loads(drift_topics_json)
    except Exception:
        return ""

    if isinstance(data, dict) and "drift_topics" in data:
        topics = data["drift_topics"]
    elif isinstance(data, list):
        topics = data
    else:
        return ""

    # Guard against corrupted rows where ``drift_topics`` is a bare scalar
    # (string / int). Iterating it would either yield characters or raise
    # ``TypeError: 'int' object is not iterable``. The dispatch contract
    # treats an empty embedding text as "skip this row, fall back to LLM"
    # (one bad row poisons the batch — that's the correct conservative
    # behavior during rollout).
    if not isinstance(topics, list):
        return ""

    parts: List[str] = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        topic = t.get("topic", "")
        keywords = " ".join(t.get("keywords") or [])
        key_phrases = " ".join(t.get("key_phrases") or [])
        context = t.get("context", "")
        if topic:
            parts.append(str(topic))
        if keywords:
            parts.append(keywords)
        if key_phrases:
            parts.append(key_phrases)
        if context:
            parts.append(str(context))

    return " ".join(parts).strip()


def _all_drift_groups_have_embeddings(groups: List[Dict[str, Any]]) -> bool:
    """True if every group carries a non-null ``drift_embedding`` BLOB.

    Used as the dispatch predicate in ``score_drift_groups``: when True, the
    fast cosine-similarity path is used; otherwise we fall back to the legacy
    LLM chunked scoring. Empty list is treated as vacuously True so an empty
    result short-circuits without an unnecessary fallback.
    """
    if not groups:
        return True
    return all(g.get("drift_embedding") is not None for g in groups)


def _normalize_embedding_to_blob(vec: Any) -> bytes:
    """Normalize a numpy embedding to unit-length and serialize as float32 bytes.

    Storage-layer contract for the ``drift_embedding`` BLOB column: stored
    vectors MUST be unit-length. ``_score_by_embedding`` relies on this to
    skip matrix normalization when computing cosine similarity, which saves
    ~120µs per expert across our 22 active experts (≈2.6ms total wall time).

    Used in three places:
    1. ``drift_scheduler_service.py`` - embed new drift_topics at sync time.
    2. ``backfill_drift_embeddings.py`` - one-shot embed for legacy rows.
    3. (Future) any other code path that writes to ``drift_embedding``.

    Raises:
        ValueError: if ``vec`` is zero-norm (degenerate embedding API output
            that should never happen in production; surfaces the bug rather
            than silently storing a zero-vector that would later match every
            normalized query in the storage contract).
    """
    arr = np.asarray(vec, dtype=np.float32)
    # Reject NaN/Inf BEFORE any arithmetic — storing them would produce
    # NaN blobs whose dot product with a query is also NaN; NaN comparisons
    # (`sim < threshold`) return False, so the row SILENTLY passes the
    # threshold filter and ends up in the HIGH set. Surface the bad input.
    if not np.all(np.isfinite(arr)):
        raise ValueError("Cannot normalize non-finite embedding (NaN or Inf found)")
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        raise ValueError("Cannot normalize zero-norm embedding to unit length")
    return (arr / norm).tobytes()


class CommentGroupMapService:
    """Service for finding relevant GROUPS of comments using Gemini on Vertex AI.

    Analyzes groups of Telegram comments to find discussions relevant to the query.
    Strategy: use the shared Vertex-backed Gemini client.
    """

    DEFAULT_CHUNK_SIZE = 20  # Groups per chunk
    DEFAULT_MAX_PARALLEL = 5  # Rate limiting for API calls

    def __init__(
        self,
        model: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_parallel: int = DEFAULT_MAX_PARALLEL
    ):
        """Initialize CommentGroupMapService.

        Args:
            model: Model to use (Gemini)
            chunk_size: Number of comment groups per chunk
            max_parallel: Maximum parallel API calls
        """
        # Initialize Vertex LLM client
        self.llm_client = None
        try:
            self.llm_client = get_vertex_llm_client()
            if self.llm_client:
                logger.info("CommentGroupMapService: Vertex LLM client initialized.")
        except Exception as e:
            logger.warning(f"CommentGroupMapService: Could not initialize Vertex LLM client: {e}")

        self.chunk_size = chunk_size
        self.primary_model = model
        self.max_parallel = max_parallel
        self._prompt_template = self._load_prompt_template()

        logger.info(f"CommentGroupMapService Config: Model={self.primary_model}")

    def _load_prompt_template(self) -> Template:
        """Load the comment group drift prompt template."""
        try:
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "comment_group_drift_prompt.txt"

            if not prompt_path.resolve().is_relative_to(prompt_dir.resolve()):
                raise ValueError(f"Invalid prompt path: {prompt_path}")

            if prompt_path.stat().st_mode & 0o002:
                raise PermissionError("Unsafe prompt file permissions")

            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "$query" not in content or "$groups" not in content:
                raise ValueError("Prompt template missing required placeholders")

            return Template(content)
        except FileNotFoundError:
            logger.error(f"Comment group map prompt template not found at {prompt_path}")
            raise

    def _load_main_source_author_comments(
        self,
        db: Session,
        main_source_ids: List[int],
        expert_id: str
    ) -> List[Dict[str, Any]]:
        """Load author's comments from main_source posts.
        
        These are clarifications the expert made in comments to their own posts
        that were used as main_sources for the answer.
        
        Uses author_id matching: posts have 'channelXXX', comments have 'XXX'.
        """
        if not main_source_ids:
            return []
        
        # Get posts by telegram_message_id
        # Note: main_source_ids come from reduce_results which already processed
        # filtered posts (respecting cutoff_date), so no date filter needed here
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(main_source_ids),
            Post.expert_id == expert_id
        ).all()
        
        logger.info(f"[{expert_id}] Loading main_source author comments from {len(posts)} posts")
        
        groups = []
        for post in posts:
            # Extract numeric author_id from post (remove 'channel' prefix)
            post_author_id = post.author_id.replace("channel", "") if post.author_id else None
            
            if not post_author_id:
                logger.debug(f"Post {post.telegram_message_id} has no author_id, skipping")
                continue
            
            # Get only author's comments using author_id matching (reliable!)
            author_comments = db.query(Comment).filter(
                Comment.post_id == post.post_id,
                Comment.author_id == post_author_id  # "2273349814" == "2273349814"
            ).order_by(Comment.created_at.desc()).all()
            
            if author_comments:
                groups.append({
                    "anchor_post": {
                        "telegram_message_id": post.telegram_message_id,
                        "message_text": post.message_text or "[Media only]",
                        "created_at": post.created_at.isoformat() if post.created_at else "",
                        "author_name": post.author_name or "Unknown",
                        "channel_username": get_channel_username(expert_id)
                    },
                    "drift_topics": ["Author clarification to main source"],
                    "comments_count": len(author_comments),
                    "comments": [
                        {
                            "comment_id": c.comment_id,
                            "comment_text": c.comment_text,
                            "author_name": c.author_name,
                            "created_at": c.created_at.isoformat() if c.created_at else "",
                            "updated_at": c.updated_at.isoformat() if c.updated_at else ""
                        }
                        for c in author_comments
                    ],
                    "is_main_source_clarification": True,  # Flag for synthesis priority
                    "relevance": "HIGH",  # Main source clarifications are always HIGH
                    "reason": "Author's clarification to a main source post",
                    "parent_telegram_message_id": post.telegram_message_id
                })
                logger.debug(f"Found {len(author_comments)} author comments for post {post.telegram_message_id}")
        
        logger.info(f"[{expert_id}] Found {len(groups)} main_source posts with author clarifications")
        return groups

    def _load_main_source_community_comments(
        self,
        db: Session,
        main_source_ids: List[int],
        expert_id: str
    ) -> List[Dict[str, Any]]:
        """Load community comments from main_source posts.
        
        These are comments from community members (not the expert) on the posts
        that were used as main_sources for the answer.
        """
        if not main_source_ids:
            return []
        
        # Get posts by telegram_message_id
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(main_source_ids),
            Post.expert_id == expert_id
        ).all()
        
        logger.info(f"[{expert_id}] Loading main_source community comments from {len(posts)} posts")
        
        groups = []
        for post in posts:
            # Extract numeric author_id from post (remove 'channel' prefix)
            post_author_id = post.author_id.replace("channel", "") if post.author_id else None
            
            # Get community comments (NOT from author)
            if post_author_id:
                community_comments = db.query(Comment).filter(
                    Comment.post_id == post.post_id,
                    Comment.author_id != post_author_id  # NOT the author
                ).order_by(Comment.created_at.desc()).all()
            else:
                # If no author_id, take all comments
                community_comments = db.query(Comment).filter(
                    Comment.post_id == post.post_id
                ).order_by(Comment.created_at.desc()).all()
            
            if community_comments:
                groups.append({
                    "anchor_post": {
                        "telegram_message_id": post.telegram_message_id,
                        "message_text": post.message_text or "[Media only]",
                        "created_at": post.created_at.isoformat() if post.created_at else "",
                        "author_name": post.author_name or "Unknown",
                        "channel_username": get_channel_username(expert_id)
                    },
                    "drift_topics": ["Community discussion on main source"],
                    "comments_count": len(community_comments),
                    "comments": [
                        {
                            "comment_id": c.comment_id,
                            "comment_text": c.comment_text,
                            "author_name": c.author_name,
                            "created_at": c.created_at.isoformat() if c.created_at else "",
                            "updated_at": c.updated_at.isoformat() if c.updated_at else ""
                        }
                        for c in community_comments
                    ],
                    "is_main_source_community": True,  # Flag for synthesis
                    "relevance": "HIGH",  # Main source community comments are HIGH priority
                    "reason": "Community discussion on a main source post",
                    "parent_telegram_message_id": post.telegram_message_id
                })
                logger.debug(f"Found {len(community_comments)} community comments for post {post.telegram_message_id}")
        
        logger.info(f"[{expert_id}] Found {len(groups)} main_source posts with community comments")
        return groups

    def _load_drift_groups(
        self,
        db: Session,
        expert_id: str,
        exclude_post_ids: Optional[List[int]] = None,
        cutoff_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Load comment groups with drift from database."""
        # Query drift groups with anchor posts
        query = db.query(
            comment_group_drift.c.post_id,
            comment_group_drift.c.drift_topics,
            comment_group_drift.c.drift_embedding,
            Post.telegram_message_id,
            Post.message_text,
            Post.created_at,
            Post.author_name
        ).join(
            Post, comment_group_drift.c.post_id == Post.post_id
        ).filter(
            comment_group_drift.c.has_drift == True,
            comment_group_drift.c.expert_id == expert_id
        )

        # Apply date filter if specified
        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        if exclude_post_ids:
            validated_ids = [pid for pid in exclude_post_ids if isinstance(pid, int) and pid > 0]
            if validated_ids:
                query = query.filter(Post.telegram_message_id.notin_(validated_ids))

        results = query.all()
        groups = []
        for post_id, drift_topics_json, drift_embedding, telegram_msg_id, message_text, created_at, author_name in results:
            if drift_topics_json:
                try:
                    if isinstance(drift_topics_json, bytes):
                        drift_topics_json = drift_topics_json.decode("utf-8")
                    sanitized = re.sub(r'\\(?![ntr"\\/])', '', drift_topics_json)
                    parsed_drift = json.loads(sanitized)

                    if isinstance(parsed_drift, dict) and 'drift_topics' in parsed_drift:
                        drift_topics = parsed_drift['drift_topics']
                    elif isinstance(parsed_drift, list):
                        drift_topics = parsed_drift
                    else:
                        drift_topics = []
                except Exception as e:
                    # Use json_repair as fallback if available, otherwise empty
                    try:
                        from json_repair import repair_json
                        repaired = json.loads(repair_json(drift_topics_json))
                        if isinstance(repaired, dict) and 'drift_topics' in repaired:
                            drift_topics = repaired['drift_topics']
                        elif isinstance(repaired, list):
                            drift_topics = repaired
                        else:
                            drift_topics = []
                    except Exception:
                        drift_topics = []
            else:
                drift_topics = []

            from ..models.comment import Comment
            comments_query = db.query(Comment).filter(Comment.post_id == post_id).all()
            comments = [
                {
                    "comment_id": c.comment_id,
                    "comment_text": c.comment_text,
                    "author_name": c.author_name,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat()
                }
                for c in comments_query
            ]

            groups.append({
                "anchor_post": {
                    "telegram_message_id": telegram_msg_id,
                    "message_text": message_text or "[Media only]",
                    "created_at": created_at.isoformat(),
                    "author_name": author_name or "Unknown",
                    "channel_username": get_channel_username(expert_id)
                },
                "drift_topics": drift_topics,
                "comments_count": len(comments),
                "comments": comments,
                "drift_embedding": drift_embedding,
            })

        return groups

    def _chunk_groups(self, groups: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split comment groups into chunks."""
        chunks = []
        for i in range(0, len(groups), self.chunk_size):
            chunks.append(groups[i:i + self.chunk_size])
        return chunks

    def _format_groups_for_prompt(self, groups: List[Dict[str, Any]]) -> str:
        """Format drift groups for inclusion in the prompt."""
        formatted_groups = []
        for group in groups:
            formatted_groups.append({
                "parent_telegram_message_id": group["anchor_post"]["telegram_message_id"],
                "drift_topics": group["drift_topics"],
                "comments_count": group["comments_count"]
            })

        return json.dumps(formatted_groups, ensure_ascii=False, indent=2)

    async def _call_llm(self, model_name: str, messages: List[Dict[str, str]]):
        """Call the shared Vertex LLM client."""
        if self.llm_client:
            return await self.llm_client.chat_completions_create(
                model=model_name,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
        raise ValueError("Vertex LLM client not initialized")

    def _validate_llm_client_availability(self) -> bool:
        """Check if the shared Vertex LLM client is properly initialized."""
        return self.llm_client is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    async def _process_chunk(
        self,
        chunk: List[Dict[str, Any]],
        query: str,
        chunk_index: int,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a single chunk of comment groups with Gemini."""
        try:
            if progress_callback:
                await progress_callback({
                    "event_type": "progress",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "processing",
                    "message": f"Analyzing comment groups chunk {chunk_index + 1}"
                })

            # Format the prompt
            groups_formatted = self._format_groups_for_prompt(chunk)

            # Create base prompt
            base_prompt = self._prompt_template.substitute(
                query=query,
                groups=groups_formatted
            )

            # Apply language instruction based on query language
            prompt = prepare_prompt_with_language_instruction(base_prompt, query)

            messages = [
                {"role": "system", "content": "You are analyzing comment groups from Telegram."},
                {"role": "user", "content": prompt}
            ]

            response = None

            # Direct call to the shared Vertex model
            response = await self._call_llm(self.primary_model, messages)
            logger.info(f"CommentGroups: Successfully used model {self.primary_model}")

            # Parse response
            result = json.loads(response.choices[0].message.content)

            # Add anchor_post and comments back to each group from original chunk data
            chunk_map = {
                group["anchor_post"]["telegram_message_id"]: {
                    "anchor_post": group["anchor_post"],
                    "comments": group["comments"],
                    "comments_count": group["comments_count"]
                }
                for group in chunk
            }

            for group in result.get("relevant_groups", []):
                telegram_msg_id = group.get("parent_telegram_message_id")
                if telegram_msg_id and telegram_msg_id in chunk_map:
                    group["anchor_post"] = chunk_map[telegram_msg_id]["anchor_post"]
                    group["comments"] = chunk_map[telegram_msg_id]["comments"]
                    group["comments_count"] = chunk_map[telegram_msg_id]["comments_count"]

            # Add chunk metadata
            result["chunk_index"] = chunk_index
            result["groups_processed"] = len(chunk)

            if progress_callback:
                await progress_callback({
                    "event_type": "progress",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "completed",
                    "message": f"Comment groups chunk {chunk_index + 1} completed",
                    "relevant_found": len(result.get("relevant_groups", []))
                })

            return result

        except Exception as e:
            logger.error(f"Error processing comment groups chunk {chunk_index}: {str(e)}")
            if progress_callback:
                await progress_callback({
                    "event_type": "error",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "error",
                    "message": f"Error in chunk {chunk_index + 1}: {str(e)}"
                })
            raise

    async def score_drift_groups(
        self,
        query: str,
        db: Session,
        expert_id: str,
        exclude_post_ids: Optional[List[int]] = None,
        cutoff_date: Optional[datetime] = None,
        progress_callback: Optional[Callable] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Load drift groups and score them. Does NOT need main_sources.

        Fast path: when all groups have pre-computed ``drift_embedding`` BLOBs,
        uses cosine similarity with the query embedding (~1ms per expert).

        Fallback: if any group lacks an embedding, falls back to the legacy
        LLM-chunked path (~80-130s per expert). This state is expected only
        during the rollout window (between migration 024 and the backfill
        script run).

        Returns:
            List of HIGH-relevance scored drift groups, sorted by date.
        """
        import time
        t_start = time.time()

        all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids, cutoff_date=cutoff_date)

        if not all_groups:
            logger.info(f"[{expert_id}] Drift scoring: no drift groups found")
            return []

        # Fast path: cosine similarity on pre-computed embeddings
        all_have_embeddings = _all_drift_groups_have_embeddings(all_groups)
        if all_have_embeddings:
            if query_embedding is None:
                embedding_service = get_embedding_service()
                query_embedding = await embedding_service.embed_query(query)
            return self._score_by_embedding(
                all_groups, query_embedding, expert_id, t_start
            )

        # Fallback to LLM chunked path (any group without embedding triggers full LLM)
        missing_count = sum(1 for g in all_groups if g.get("drift_embedding") is None)
        logger.info(
            f"[{expert_id}] Drift scoring: {missing_count}/{len(all_groups)} groups without "
            f"drift_embedding, falling back to LLM chunked path (run backfill to enable fast path)"
        )

        chunks = self._chunk_groups(all_groups)
        total_chunks = len(chunks)

        logger.info(
            f"[{expert_id}] Drift Scoring START: {len(all_groups)} groups in "
            f"{total_chunks} chunks using {self.primary_model}"
        )

        if progress_callback:
            await progress_callback({
                "event_type": "phase_start",
                "phase": "comment_groups",
                "status": "starting",
                "message": f"Drift scoring: {len(all_groups)} groups in {total_chunks} chunks",
                "total_chunks": total_chunks,
            })

        # Process chunks in parallel
        parallel_limit = self.max_parallel if self.max_parallel is not None else total_chunks
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_with_semaphore(chunk, index):
            async with semaphore:
                return await self._process_chunk(chunk, query, index, progress_callback)

        tasks = [
            process_with_semaphore(chunk, i)
            for i, chunk in enumerate(chunks)
        ]

        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_relevant_groups = []
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(f"Drift scoring chunk {i} failed: {result}")
            else:
                for group in result.get("relevant_groups", []):
                    if group.get("anchor_post"):
                        all_relevant_groups.append(group)

        # Filter HIGH relevance only
        relevant_groups = [
            g for g in all_relevant_groups if g.get("relevance") == "HIGH"
        ]

        # Sort: date descending, then relevance (stable sort)
        relevant_groups.sort(
            key=lambda x: x["anchor_post"].get("created_at", ""), reverse=True
        )

        duration_ms = int((time.time() - t_start) * 1000)
        logger.info(
            f"[{expert_id}] Drift Scoring END: {duration_ms}ms, "
            f"{len(all_groups)} groups -> {len(relevant_groups)} HIGH"
        )

        return relevant_groups

    def _score_by_embedding(
        self,
        groups: List[Dict[str, Any]],
        query_embedding: List[float],
        expert_id: str,
        t_start: float,
    ) -> List[Dict[str, Any]]:
        """Score drift groups via cosine similarity. No LLM call.

        ~1ms for hundreds of groups. Replaces ~80-130s LLM chunked scoring.
        Returns HIGH-relevance groups only, sorted by date desc.
        """
        import time
        threshold = config.DRIFT_EMBEDDING_THRESHOLD
        top_k = config.DRIFT_EMBEDDING_TOP_K

        # Normalize query vector
        q_vec = np.asarray(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))
        if q_norm == 0.0:
            logger.warning(f"[{expert_id}] Drift embedding: zero query vector, skipping")
            return []
        q_normalized = q_vec / q_norm

        # Decode all drift embeddings; skip dimension mismatches
        d_vecs: List[np.ndarray] = []
        valid_groups: List[Dict[str, Any]] = []
        for g in groups:
            blob = g.get("drift_embedding")
            if blob is None:
                continue
            d_vec = np.frombuffer(blob, dtype=np.float32)
            if d_vec.shape[0] != q_vec.shape[0]:
                logger.warning(
                    f"[{expert_id}] Drift embedding dim mismatch: "
                    f"expected {q_vec.shape[0]}, got {d_vec.shape[0]}. Skipping group."
                )
                continue
            d_vecs.append(d_vec)
            valid_groups.append(g)

        if not valid_groups:
            return []

        d_matrix = np.stack(d_vecs)

        # Cosine similarity: (N, D) @ (D,) -> (N,)
        # CRITICAL contract: stored vectors are pre-normalized to unit-length
        # by ``_normalize_embedding_to_blob`` (see drift_scheduler_service
        # and backfill_drift_embeddings writers). Trusting this contract
        # strictly lets us skip ``np.linalg.norm`` and matrix division
        # (~120µs/expert saved, ~2.6ms across 22 experts).
        # During the rollout window before a re-backfill, OLD un-normalized
        # blobs become ``q_normalized @ d`` instead of true cosine — slight
        # score drift, biased toward smaller-magnitude stored rows, but
        # never catastrophically wrong. Re-run backfill to normalize them.
        similarities = d_matrix @ q_normalized

        # Pair, sort by similarity desc, take top-K
        scored = sorted(
            zip(similarities.tolist(), valid_groups),
            key=lambda x: x[0],
            reverse=True,
        )[:top_k]

        relevant_groups: List[Dict[str, Any]] = []
        for sim, group in scored:
            if sim < threshold:
                continue
            # Shallow copy so we don't mutate the cached group from _load_drift_groups
            out = dict(group)
            out["relevance"] = "HIGH"
            out["reason"] = f"Embedding similarity: {sim:.3f}"
            out["matched_keywords"] = []
            relevant_groups.append(out)

        # Sort by date desc (consistent with LLM path)
        relevant_groups.sort(
            key=lambda x: x["anchor_post"].get("created_at", ""),
            reverse=True,
        )

        duration_ms = int((time.time() - t_start) * 1000)
        logger.info(
            f"[{expert_id}] Drift Scoring END (embedding path): {duration_ms}ms, "
            f"{len(valid_groups)} scored -> {len(relevant_groups)} HIGH "
            f"(threshold={threshold}, top_k={top_k})"
        )
        return relevant_groups

    def merge_with_main_sources(
        self,
        scored_drift_groups: List[Dict[str, Any]],
        db: Session,
        expert_id: str,
        main_source_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Load main_source comments and merge with pre-scored drift groups.

        Cheap operation (~5ms): DB queries for author/community comments,
        then dedup drift groups that overlap with main_sources.

        Returns:
            Final ordered list: author clarifications + community + drift (deduped).
        """
        main_source_groups = []
        main_source_community_groups = []

        if main_source_ids:
            main_source_groups = self._load_main_source_author_comments(
                db, main_source_ids, expert_id
            )
            main_source_community_groups = self._load_main_source_community_comments(
                db, main_source_ids, expert_id
            )

        # Dedup: remove drift groups whose anchor post is already a main_source
        deduped_drift = scored_drift_groups
        if main_source_ids:
            main_source_set = set(main_source_ids)
            deduped_drift = [
                g for g in scored_drift_groups
                if g.get("anchor_post", {}).get("telegram_message_id") not in main_source_set
            ]

        logger.info(
            f"[{expert_id}] Merge: {len(main_source_groups)} author + "
            f"{len(main_source_community_groups)} community + "
            f"{len(deduped_drift)} drift (deduped from {len(scored_drift_groups)})"
        )

        return main_source_groups + main_source_community_groups + deduped_drift

    async def process(
        self,
        query: str,
        db: Session,
        expert_id: str,
        exclude_post_ids: Optional[List[int]] = None,
        main_source_ids: Optional[List[int]] = None,
        cutoff_date: Optional[datetime] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Process drift groups to find relevant ones (backward-compatible sequential path).

        Delegates to score_drift_groups() + merge_with_main_sources().
        """
        import time
        phase_start_time = time.time()

        scored = await self.score_drift_groups(
            query=query,
            db=db,
            expert_id=expert_id,
            exclude_post_ids=exclude_post_ids,
            cutoff_date=cutoff_date,
            progress_callback=progress_callback,
        )

        final_groups = self.merge_with_main_sources(
            scored_drift_groups=scored,
            db=db,
            expert_id=expert_id,
            main_source_ids=main_source_ids,
        )

        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Comment Groups Phase END: {duration_ms}ms, "
            f"{len(final_groups)} total groups"
        )

        if progress_callback:
            await progress_callback({
                "event_type": "phase_complete",
                "phase": "comment_groups",
                "status": "completed",
                "message": f"Found {len(final_groups)} relevant comment groups",
            })

        return final_groups
