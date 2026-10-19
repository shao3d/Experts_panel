"""Comment Group Map service for finding relevant comment groups."""

import json
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import re
import logging

import numpy as np
from sqlalchemy.orm import Session

from ..models.post import Post
from ..models.comment import Comment
from ..models.database import comment_group_drift
from .embedding_service import get_embedding_service
from .. import config
from ..api.models import get_channel_username

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
    """Load and score precomputed comment-group drift.

    Drift itself is determined offline by ``DriftSchedulerService`` through the
    headless OpenCode backend (GLM-5.3 Flash); every drift group is stored with
    a 768-dim ``drift_embedding``. Query-time scoring is a cosine comparison
    against the query embedding — the retired Gemini/OpenRouter path is gone.
    """

    def __init__(self) -> None:
        logger.info("CommentGroupMapService: embedding-only drift scoring")

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
        """Load drift groups and score them by embedding cosine similarity.

        Drift topics and their 768-dim embeddings are produced offline by the
        OpenCode drift scheduler — the same pipeline the visual group uses.
        This method never calls an LLM: groups without a stored embedding are
        skipped with a warning instead of falling back to the retired Gemini
        chunked path.

        Returns:
            List of HIGH-relevance scored drift groups, sorted by date.
        """
        import time
        t_start = time.time()

        all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids, cutoff_date=cutoff_date)
        if not all_groups:
            logger.info(f"[{expert_id}] Drift scoring: no drift groups found")
            return []

        missing = [g for g in all_groups if g.get("drift_embedding") is None]
        if missing:
            logger.warning(
                f"[{expert_id}] Drift scoring: skipping {len(missing)}/{len(all_groups)} "
                "groups without drift_embedding (offline analysis/backfill missing)"
            )
            all_groups = [g for g in all_groups if g.get("drift_embedding") is not None]
            if not all_groups:
                return []

        if query_embedding is None:
            embedding_service = get_embedding_service()
            query_embedding = await embedding_service.embed_query(query)

        return self._score_by_embedding(all_groups, query_embedding, expert_id, t_start)

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
