"""Source-bundle service for the explicit-only Agent Context API."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..api.models import (
    AgentContextRequest,
    AgentContextResponse,
    AgentDigestCommentSignal,
    AgentDigestComments,
    AgentDigestLimitsUsed,
    AgentDigestOmittedCounts,
    AgentDigestSignal,
    AgentDigestSourceIndexEntry,
    AgentDigestSourceRef,
    AgentEvidenceQuality,
    AgentExpertDigest,
    AgentExpandedSource,
    AgentExpertSourceBundle,
    AgentExternalLink,
    AgentLinkedContext,
    AgentMainSource,
    AgentSourceExpandRequest,
    AgentSourceExpandLimitsUsed,
    AgentSourceExpandResponse,
    AgentSourceExpandTruncation,
    AgentSourceComment,
    AgentSourceComments,
    RelevanceLevel,
    SelectionUsed,
)
from ..models.expert import Expert
from ..models.post import Post
from ..services.comment_group_map_service import CommentGroupMapService
from ..services.ai_scout_service import AIScoutService
from ..services.embedding_service import get_embedding_service
from ..services.hybrid_retrieval_service import HybridRetrievalService
from ..services.map_service import MapService
from ..services.medium_scoring_service import MediumScoringService
from ..services.monitored_client import create_monitored_client
from ..services.simple_resolve_service import SimpleResolveService
from ..utils.date_utils import get_cutoff_date

logger = logging.getLogger(__name__)


MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]\n]{1,200})\]\((https?://(?:[^\s()]|\([^\s()]*\))+)\)"
)
URL_RE = re.compile(r"https?://[^\s<>\]\"']+")
TRAILING_URL_PUNCTUATION = ".,;:!?]}*"
SOURCE_KEY_RE = re.compile(r"^([A-Za-z0-9_]+):([0-9]+)$")

SOURCE_BUNDLE_PIPELINE_USED = [
    "expert_selection",
    "ai_scout_query",
    "query_embedding",
    "retrieval",
    "hybrid_retrieval",
    "map_relevance",
    "medium_scoring_if_needed",
    "resolve_high_sources_if_needed",
    "source_selection",
    "main_source_comments",
    "external_link_references",
]

SOURCE_BUNDLE_PIPELINE_SKIPPED = [
    "reduce_answer_synthesis",
    "language_validation",
    "drift_comment_group_scoring",
    "comment_synthesis",
    "cross_expert_meta_synthesis",
    "reddit_synthesis",
]

SUPPORTED_AGENT_CONTEXT_RESPONSE_MODES = {"source_bundle", "expert_digest"}

PRACTITIONER_SOURCE_TERMS = (
    "in production",
    "we used",
    "i used",
    "my experience",
    "case study",
    "lesson",
    "checklist",
    "practical",
    "production experience",
    "опыт",
    "кейс",
    "чеклист",
    "практи",
    "в прод",
)

ANNOUNCEMENT_SOURCE_TERMS = (
    "announce",
    "announcement",
    "launch",
    "launched",
    "release",
    "released",
    "introducing",
    "waitlist",
    "public beta",
    "анонс",
    "релиз",
    "запуск",
    "запуст",
    "вышел",
    "представ",
)

ANALYSIS_SOURCE_TERMS = (
    "analysis",
    "because",
    "tradeoff",
    "trade-off",
    "architecture",
    "pattern",
    "approach",
    "why",
    "анализ",
    "почему",
    "подход",
    "архитект",
    "паттерн",
    "компромисс",
)

LOW_SIGNAL_COMMENT_TERMS = (
    "thanks",
    "thank you",
    "cool",
    "interesting",
    "nice",
    "+1",
    "спасибо",
    "класс",
    "интересно",
    "огонь",
)


@dataclass(frozen=True)
class AgentContextSearchContext:
    """Shared forced-hybrid search inputs for one Agent Context request."""

    scout_query: str
    query_embedding: List[float]
    warnings: List[str]


class AgentContextSearchUnavailable(RuntimeError):
    """Raised when Agent Context cannot satisfy its embedding-search contract."""


class AgentContextInvalidSourceKey(ValueError):
    """Raised when an expand request carries an invalid source_key."""


def _calibrate_evidence_quality(source: AgentMainSource) -> AgentEvidenceQuality:
    """Build deterministic evidence calibration over already selected source data."""
    content = source.content or ""
    reason = source.reason or ""
    score_reason = source.score_reason or ""
    combined = f"{content}\n{reason}\n{score_reason}".lower()
    content_chars = len(content.strip())
    author_comments = list(source.comments.author_comments)
    community_comments = list(source.comments.community_comments)
    author_count = len(author_comments)
    community_count = len(community_comments)
    external_links_count = len(source.external_links)

    source_type = _classify_source_type(
        combined=combined,
        content_chars=content_chars,
        external_links_count=external_links_count,
    )
    comment_signal = _classify_comment_signal(
        author_comments=author_comments,
        community_comments=community_comments,
    )
    depth = _classify_depth(
        source=source,
        source_type=source_type,
        content_chars=content_chars,
        author_comments_count=author_count,
        community_comments_count=community_count,
    )
    confidence = _classify_quality_confidence(
        source=source,
        depth=depth,
        source_type=source_type,
        comment_signal=comment_signal,
    )
    notes = _build_quality_notes(
        depth=depth,
        source_type=source_type,
        comment_signal=comment_signal,
        external_links_count=external_links_count,
    )
    return AgentEvidenceQuality(
        depth=depth,
        source_type=source_type,
        comment_signal=comment_signal,
        confidence=confidence,
        notes=notes,
    )


def _classify_source_type(
    *,
    combined: str,
    content_chars: int,
    external_links_count: int,
) -> str:
    has_practitioner_signal = any(term in combined for term in PRACTITIONER_SOURCE_TERMS)
    has_announcement_signal = any(term in combined for term in ANNOUNCEMENT_SOURCE_TERMS)
    has_analysis_signal = any(term in combined for term in ANALYSIS_SOURCE_TERMS)

    if has_practitioner_signal:
        return "practitioner_experience"
    if has_announcement_signal and external_links_count > 0:
        return "tool_release"
    if has_announcement_signal:
        return "announcement"
    if has_analysis_signal:
        return "analysis"
    if content_chars and content_chars < 360:
        return "mention"
    return "unknown"


def _classify_comment_signal(
    *,
    author_comments: List[AgentSourceComment],
    community_comments: List[AgentSourceComment],
) -> str:
    if author_comments and community_comments:
        return "mixed"
    if author_comments:
        return "author_support"
    if community_comments:
        if _comments_are_mostly_noise(community_comments):
            return "mostly_noise"
        return "community_support"
    return "none"


def _comments_are_mostly_noise(comments: List[AgentSourceComment]) -> bool:
    if not comments:
        return False

    low_signal_count = 0
    for comment in comments:
        text = (comment.comment_text or "").strip().lower()
        words = [word for word in re.split(r"\s+", text) if word]
        if len(words) <= 4 or any(term in text for term in LOW_SIGNAL_COMMENT_TERMS):
            low_signal_count += 1
    return low_signal_count / len(comments) >= 0.7


def _classify_depth(
    *,
    source: AgentMainSource,
    source_type: str,
    content_chars: int,
    author_comments_count: int,
    community_comments_count: int,
) -> str:
    relevance = _relevance_value(source.relevance)
    has_comments = author_comments_count > 0 or community_comments_count > 0

    if source_type in {"announcement", "mention"}:
        return "shallow"
    if source_type == "tool_release" and content_chars < 700:
        return "shallow"
    if source_type == "practitioner_experience" and (
        relevance == "HIGH" or author_comments_count > 0 or content_chars >= 260
    ):
        return "deep_practical"
    if source_type == "analysis" and content_chars >= 700:
        return "deep_practical"
    if content_chars >= 450 or has_comments or relevance == "HIGH":
        return "moderate"
    if content_chars > 0:
        return "shallow"
    return "unknown"


def _classify_quality_confidence(
    *,
    source: AgentMainSource,
    depth: str,
    source_type: str,
    comment_signal: str,
) -> str:
    relevance = _relevance_value(source.relevance)
    if (
        depth == "deep_practical"
        and relevance == "HIGH"
        and comment_signal in {"author_support", "mixed", "community_support"}
    ):
        return "high"
    if (
        relevance == "HIGH"
        and comment_signal in {"author_support", "mixed", "community_support"}
        and depth != "unknown"
    ):
        return "medium"
    if depth == "shallow" or source_type in {"announcement", "mention"}:
        return "low"
    if relevance == "HIGH" or depth in {"deep_practical", "moderate"}:
        return "medium"
    return "low"


def _build_quality_notes(
    *,
    depth: str,
    source_type: str,
    comment_signal: str,
    external_links_count: int,
) -> List[str]:
    notes: List[str] = []
    if depth == "shallow":
        notes.append("short or announcement-like source")
    if source_type in {"announcement", "tool_release"}:
        notes.append("announcement/release signal, not deep analysis")
    if comment_signal == "mostly_noise":
        notes.append("comments mostly noise")
    elif comment_signal != "none":
        notes.append(f"comments: {comment_signal}")
    if external_links_count:
        notes.append("external links are author-supplied and not fetched")
    return notes[:4]


def _relevance_value(relevance: Any) -> str:
    return str(getattr(relevance, "value", relevance) or "")


class AgentContextService:
    """Build source-backed evidence packets without running full Reduce."""

    def __init__(self, db: Session):
        self.db = db

    async def build_response(
        self,
        *,
        agent_request: AgentContextRequest,
        selection_used: SelectionUsed,
        expert_ids: List[str],
        request_id: str,
        start_time: float,
    ) -> AgentContextResponse:
        warnings: List[str] = []
        search_context = await self._prepare_search_context(agent_request.query)
        warnings.extend(search_context.warnings)
        expert_results = await self._build_expert_bundles_parallel(
            expert_ids=expert_ids,
            agent_request=agent_request,
            search_context=search_context,
        )
        experts = []
        for expert_bundle, expert_warnings in expert_results:
            experts.append(expert_bundle)
            warnings.extend(expert_warnings)

        pipeline_used = list(SOURCE_BUNDLE_PIPELINE_USED)
        pipeline_skipped = list(SOURCE_BUNDLE_PIPELINE_SKIPPED)
        if not agent_request.include_main_source_comments:
            pipeline_used.remove("main_source_comments")
            pipeline_skipped.append("main_source_comments")
        if agent_request.response_mode == "expert_digest":
            pipeline_used.append("expert_digest_reduce")

        return AgentContextResponse(
            request_id=request_id,
            mode=agent_request.response_mode,
            query=agent_request.query,
            selection_used=selection_used,
            experts=experts,
            reddit=None,
            pipeline_used=pipeline_used,
            pipeline_skipped=pipeline_skipped,
            warnings=warnings,
            processing_time_ms=int((time.perf_counter() - start_time) * 1000),
        )

    async def build_expand_response(
        self,
        *,
        expand_request: AgentSourceExpandRequest,
        request_id: str,
        start_time: float,
    ) -> AgentSourceExpandResponse:
        sources: List[AgentExpandedSource] = []
        not_found: List[str] = []
        warnings: List[str] = []

        for source_key in expand_request.source_keys:
            expert_id, telegram_message_id = self._parse_source_key(source_key)
            post = self._load_post_by_source_key(expert_id, telegram_message_id)
            if not post:
                not_found.append(source_key)
                continue
            sources.append(
                self._build_expanded_source(
                    source_key=source_key,
                    expert_id=expert_id,
                    telegram_message_id=telegram_message_id,
                    post=post,
                    expand_request=expand_request,
                )
            )

        return AgentSourceExpandResponse(
            request_id=request_id,
            limits_used=AgentSourceExpandLimitsUsed(
                include_comments=expand_request.include_comments,
                include_external_links=expand_request.include_external_links,
                max_content_chars=expand_request.max_content_chars,
                max_comments_per_source=expand_request.max_comments_per_source,
            ),
            sources=sources,
            not_found=not_found,
            warnings=warnings,
            processing_time_ms=int((time.perf_counter() - start_time) * 1000),
        )

    async def _build_expert_bundles_parallel(
        self,
        *,
        expert_ids: List[str],
        agent_request: AgentContextRequest,
        search_context: AgentContextSearchContext,
    ) -> List[tuple[AgentExpertSourceBundle, List[str]]]:
        max_concurrent_experts = max(1, int(config.MAX_CONCURRENT_EXPERTS))
        semaphore = asyncio.Semaphore(max_concurrent_experts)

        async def run_expert(
            expert_id: str,
        ) -> tuple[AgentExpertSourceBundle, List[str]]:
            expert_warnings: List[str] = []
            async with semaphore:
                try:
                    bundle = await self._build_expert_bundle(
                        expert_id=expert_id,
                        agent_request=agent_request,
                        search_context=search_context,
                        warnings=expert_warnings,
                    )
                except Exception as exc:
                    logger.exception(
                        "Agent Context source_bundle failed for expert %s", expert_id
                    )
                    expert_warnings.append(f"{expert_id}: source_bundle_failed: {exc}")
                    bundle = self._empty_expert_bundle(
                        expert_id=expert_id,
                        no_results_reason="source_bundle_failed",
                    )
                if agent_request.response_mode == "expert_digest":
                    bundle = await AgentExpertDigestReducer().compact_bundle(
                        bundle=bundle,
                        query=agent_request.query,
                        warnings=expert_warnings,
                    )
            return bundle, expert_warnings

        tasks = [
            asyncio.create_task(run_expert(expert_id))
            for expert_id in expert_ids
        ]
        return await asyncio.gather(*tasks)

    async def _build_expert_bundle(
        self,
        *,
        expert_id: str,
        agent_request: AgentContextRequest,
        search_context: AgentContextSearchContext,
        warnings: List[str],
    ) -> AgentExpertSourceBundle:
        cutoff_date = get_cutoff_date(months=3) if agent_request.use_recent_only else None
        posts = await self._load_candidate_posts_with_embeddings(
            expert_id=expert_id,
            query=agent_request.query,
            cutoff_date=cutoff_date,
            search_context=search_context,
            warnings=warnings,
        )

        if not posts:
            warnings.append(f"{expert_id}: no_runtime_posts")
            return self._empty_expert_bundle(
                expert_id=expert_id,
                no_results_reason="no_runtime_posts",
            )

        map_service = MapService(
            model=config.MODEL_MAP,
            chunk_size=config.MAP_CHUNK_SIZE,
            max_parallel=config.MAP_MAX_PARALLEL,
        )
        map_results = await map_service.process(
            posts=posts,
            query=agent_request.query,
            expert_id=expert_id,
            progress_callback=None,
        )
        relevant_posts = map_results.get("relevant_posts", [])
        high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
        medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

        selected_medium_posts = await self._select_medium_posts(
            expert_id=expert_id,
            query=agent_request.query,
            high_posts=high_posts,
            medium_posts=medium_posts,
            posts=posts,
        )

        selected_sources, unattached_context = await self._build_sources(
            expert_id=expert_id,
            query=agent_request.query,
            high_posts=high_posts,
            selected_medium_posts=selected_medium_posts,
            cutoff_date=cutoff_date,
            warnings=warnings,
        )

        if agent_request.include_main_source_comments and selected_sources:
            self._attach_main_source_comments(
                expert_id=expert_id,
                main_sources=selected_sources,
            )
            self._refresh_evidence_quality(selected_sources)

        no_results_reason = None if selected_sources else "no_relevant_sources"
        if not selected_sources:
            warnings.append(f"{expert_id}: no_relevant_sources")

        metadata = self._get_expert_metadata(expert_id)
        return AgentExpertSourceBundle(
            expert_id=expert_id,
            expert_name=metadata["expert_name"],
            channel_username=metadata["channel_username"],
            selected_sources_count=len(selected_sources),
            unattached_linked_context=unattached_context,
            main_sources=selected_sources,
            no_results_reason=no_results_reason,
        )

    async def _prepare_search_context(self, query: str) -> AgentContextSearchContext:
        """Prepare forced hybrid retrieval inputs once per Agent Context request."""
        scout_service = AIScoutService()
        embedding_service = get_embedding_service()
        warnings: List[str] = []

        async def build_scout_query() -> str:
            scout_query, scout_success = await scout_service.generate_match_query(query)
            if not scout_success:
                warnings.append("agent_context_ai_scout_fallback_used")
            return scout_query or query

        async def build_query_embedding() -> List[float]:
            try:
                embedding = await embedding_service.embed_query(query)
            except Exception as exc:
                raise AgentContextSearchUnavailable(
                    "agent_context_embedding_search_unavailable"
                ) from exc
            if not embedding:
                raise AgentContextSearchUnavailable(
                    "agent_context_embedding_search_unavailable"
                )
            return embedding

        scout_query, query_embedding = await asyncio.gather(
            build_scout_query(),
            build_query_embedding(),
        )
        return AgentContextSearchContext(
            scout_query=scout_query,
            query_embedding=query_embedding,
            warnings=warnings,
        )

    async def _load_candidate_posts_with_embeddings(
        self,
        *,
        expert_id: str,
        query: str,
        cutoff_date,
        search_context: AgentContextSearchContext,
        warnings: List[str],
    ) -> List[Post]:
        hybrid_service = HybridRetrievalService(self.db)
        posts, retrieval_stats = await hybrid_service.search_posts(
            expert_id=expert_id,
            query=query,
            match_query=search_context.scout_query,
            cutoff_date=cutoff_date,
            query_embedding=search_context.query_embedding,
        )
        retrieval_mode = str(retrieval_stats.get("mode") or "unknown")
        if retrieval_mode != "hybrid":
            warnings.append(f"{expert_id}: hybrid_retrieval_{retrieval_mode}")
        return posts

    def _load_candidate_posts(
        self,
        expert_id: str,
        cutoff_date=None,
    ) -> List[Post]:
        query = self.db.query(Post).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30,
        )
        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)
        return query.order_by(Post.created_at.desc()).all()

    def _load_post_by_source_key(
        self,
        expert_id: str,
        telegram_message_id: int,
    ) -> Optional[Post]:
        return (
            self.db.query(Post)
            .filter(
                Post.expert_id == expert_id,
                Post.telegram_message_id == telegram_message_id,
            )
            .first()
        )

    def _parse_source_key(self, source_key: str) -> tuple[str, int]:
        match = SOURCE_KEY_RE.match(source_key.strip())
        if not match:
            raise AgentContextInvalidSourceKey(
                "source_key must use '<expert_id>:<telegram_message_id>' format"
            )
        return match.group(1), int(match.group(2))

    def _build_expanded_source(
        self,
        *,
        source_key: str,
        expert_id: str,
        telegram_message_id: int,
        post: Post,
        expand_request: AgentSourceExpandRequest,
    ) -> AgentExpandedSource:
        metadata = self._get_expert_metadata(expert_id)
        raw_content = post.message_text or ""
        content, content_truncated = self._clip_with_truncation(
            raw_content,
            expand_request.max_content_chars,
        )
        comments = AgentSourceComments()
        comments_truncated = False
        if expand_request.include_comments:
            temp_source = AgentMainSource(
                telegram_message_id=telegram_message_id,
                source_key=source_key,
                relevance=RelevanceLevel.HIGH,
                content=raw_content,
                created_at=post.created_at.isoformat() if post.created_at else None,
                author_name=post.author_name,
            )
            self._attach_main_source_comments(
                expert_id=expert_id,
                main_sources=[temp_source],
            )
            comments, comments_truncated = self._cap_source_comments(
                temp_source.comments,
                expand_request.max_comments_per_source,
            )

        external_links = (
            self._extract_external_links(raw_content)
            if expand_request.include_external_links
            else []
        )
        quality_source = AgentMainSource(
            telegram_message_id=telegram_message_id,
            source_key=source_key,
            relevance=RelevanceLevel.HIGH,
            content=raw_content,
            created_at=post.created_at.isoformat() if post.created_at else None,
            author_name=post.author_name,
            comments=comments,
            external_links=external_links,
        )
        quality_source.evidence_quality = _calibrate_evidence_quality(quality_source)
        return AgentExpandedSource(
            source_key=source_key,
            expert_id=expert_id,
            expert_name=metadata["expert_name"],
            channel_username=metadata["channel_username"],
            telegram_message_id=telegram_message_id,
            content=content,
            created_at=post.created_at.isoformat() if post.created_at else None,
            author_name=post.author_name,
            comments=comments,
            external_links=external_links,
            truncation=AgentSourceExpandTruncation(
                content_truncated=content_truncated,
                comments_truncated=comments_truncated,
            ),
            evidence_quality=quality_source.evidence_quality,
        )

    def _cap_source_comments(
        self,
        comments: AgentSourceComments,
        max_comments: int,
    ) -> tuple[AgentSourceComments, bool]:
        author_comments = list(comments.author_comments)
        community_comments = list(comments.community_comments)
        total_comments = len(author_comments) + len(community_comments)
        if max_comments < 0 or total_comments <= max_comments:
            return comments, False

        remaining = max_comments
        capped_author = author_comments[:remaining]
        remaining -= len(capped_author)
        capped_community = community_comments[: max(0, remaining)]
        return (
            AgentSourceComments(
                author_comments=capped_author,
                community_comments=capped_community,
            ),
            True,
        )

    async def _select_medium_posts(
        self,
        *,
        expert_id: str,
        query: str,
        high_posts: List[Dict[str, Any]],
        medium_posts: List[Dict[str, Any]],
        posts: List[Post],
    ) -> List[Dict[str, Any]]:
        if not medium_posts:
            return []

        posts_by_id = {p.telegram_message_id: p for p in posts}
        medium_posts_with_content: List[Dict[str, Any]] = []
        for post_meta in medium_posts:
            telegram_message_id = post_meta["telegram_message_id"]
            post = posts_by_id.get(telegram_message_id)
            if not post:
                continue
            medium_posts_with_content.append(
                {
                    **post_meta,
                    "content": post.message_text or "",
                    "author": post.author_name or "Unknown",
                    "created_at": post.created_at.isoformat()
                    if post.created_at
                    else "",
                }
            )

        high_context = json.dumps(
            [
                {
                    "telegram_message_id": p["telegram_message_id"],
                    "content": p.get("content", ""),
                    "reason": p.get("reason", ""),
                }
                for p in high_posts
            ],
            ensure_ascii=False,
            indent=2,
        )

        scoring_service = MediumScoringService(model=config.MODEL_MEDIUM_SCORING)
        return await scoring_service.score_medium_posts(
            medium_posts=medium_posts_with_content,
            high_posts_context=high_context,
            query=query,
            expert_id=expert_id,
            progress_callback=None,
        )

    async def _build_sources(
        self,
        *,
        expert_id: str,
        query: str,
        high_posts: List[Dict[str, Any]],
        selected_medium_posts: List[Dict[str, Any]],
        cutoff_date,
        warnings: List[str],
    ) -> tuple[List[AgentMainSource], List[AgentLinkedContext]]:
        source_by_key: Dict[str, AgentMainSource] = {}
        unattached_context: List[AgentLinkedContext] = []

        if high_posts:
            resolve_service = SimpleResolveService()
            resolve_results = await resolve_service.process(
                relevant_posts=high_posts,
                query=query,
                expert_id=expert_id,
                cutoff_date=cutoff_date,
                progress_callback=None,
            )
            for post in resolve_results.get("enriched_posts", []):
                if post.get("is_original", True):
                    source = self._build_main_source(expert_id, post)
                    source_by_key[source.source_key] = source
                    continue

                context = self._build_linked_context(expert_id, post)
                linked_from_keys = self._linked_from_source_keys(post)
                attached = False
                for source_key in linked_from_keys:
                    main_source = source_by_key.get(source_key)
                    if main_source:
                        main_source.linked_context.append(context)
                        attached = True

                if not attached:
                    unattached_context.append(context)
                    warnings.append(
                        f"{expert_id}:{context.telegram_message_id}: "
                        "linked_context_without_provenance"
                    )

        for post in selected_medium_posts:
            source = self._build_main_source(
                expert_id,
                {
                    **post,
                    "relevance": "MEDIUM",
                    "is_original": True,
                },
            )
            source_by_key[source.source_key] = source

        selected_sources = list(source_by_key.values())
        selected_sources.sort(
            key=lambda source: (
                0 if source.relevance == RelevanceLevel.HIGH else 1,
                source.created_at or "",
            ),
            reverse=False,
        )
        high_sources = [
            source for source in selected_sources if source.relevance == RelevanceLevel.HIGH
        ]
        medium_sources = [
            source
            for source in selected_sources
            if source.relevance == RelevanceLevel.MEDIUM
        ]
        high_sources.sort(key=lambda source: source.created_at or "", reverse=True)
        medium_sources.sort(key=lambda source: source.created_at or "", reverse=True)
        return high_sources + medium_sources, unattached_context

    def _build_main_source(
        self,
        expert_id: str,
        post: Dict[str, Any],
    ) -> AgentMainSource:
        telegram_message_id = post["telegram_message_id"]
        source = AgentMainSource(
            telegram_message_id=telegram_message_id,
            source_key=self._source_key(expert_id, telegram_message_id),
            source_role="main",
            relevance=post.get("relevance", "MEDIUM"),
            reason=post.get("reason", ""),
            content=post.get("content"),
            created_at=post.get("created_at"),
            author_name=post.get("author_name") or post.get("author"),
            is_original=True,
            score=post.get("score"),
            score_reason=post.get("score_reason"),
            external_links=self._extract_external_links(post.get("content")),
        )
        source.evidence_quality = _calibrate_evidence_quality(source)
        return source

    def _refresh_evidence_quality(self, main_sources: List[AgentMainSource]) -> None:
        for source in main_sources:
            source.evidence_quality = _calibrate_evidence_quality(source)

    def _build_linked_context(
        self,
        expert_id: str,
        post: Dict[str, Any],
    ) -> AgentLinkedContext:
        telegram_message_id = post["telegram_message_id"]
        linked_from_source_keys = self._linked_from_source_keys(post)
        parent_source_key = post.get("parent_source_key")
        if not parent_source_key and len(linked_from_source_keys) == 1:
            parent_source_key = linked_from_source_keys[0]

        return AgentLinkedContext(
            telegram_message_id=telegram_message_id,
            source_key=self._source_key(expert_id, telegram_message_id),
            source_role="context",
            relevance="CONTEXT",
            reason=post.get("reason", ""),
            content=post.get("content"),
            created_at=post.get("created_at"),
            author_name=post.get("author_name") or post.get("author"),
            is_original=False,
            parent_source_key=parent_source_key,
            linked_from_source_keys=linked_from_source_keys or None,
        )

    def _linked_from_source_keys(self, post: Dict[str, Any]) -> List[str]:
        keys: List[str] = []
        parent_source_key = post.get("parent_source_key")
        if parent_source_key:
            keys.append(parent_source_key)
        keys.extend(post.get("linked_from_source_keys") or [])
        return self._dedupe(keys)

    def _extract_external_links(self, content: Optional[str]) -> List[AgentExternalLink]:
        if not content:
            return []

        links: List[AgentExternalLink] = []
        seen_urls: set[str] = set()
        markdown_url_spans: List[tuple[int, int]] = []

        for match in MARKDOWN_LINK_RE.finditer(content):
            label = self._clean_link_label(match.group(1))
            link = self._build_external_link(
                raw_url=match.group(2),
                label=label,
                content=content,
                context_start=match.start(),
                context_end=match.end(),
            )
            markdown_url_spans.append(match.span(2))
            if link and link.url not in seen_urls:
                links.append(link)
                seen_urls.add(link.url)

        for match in URL_RE.finditer(content):
            if self._is_inside_span(match.start(), markdown_url_spans):
                continue

            link = self._build_external_link(
                raw_url=match.group(0),
                label=None,
                content=content,
                context_start=match.start(),
                context_end=match.end(),
            )
            if link and link.url not in seen_urls:
                links.append(link)
                seen_urls.add(link.url)

        return links

    def _build_external_link(
        self,
        *,
        raw_url: str,
        label: Optional[str],
        content: str,
        context_start: int,
        context_end: int,
    ) -> Optional[AgentExternalLink]:
        url = self._clean_url(raw_url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        domain = self._normalize_domain(parsed.netloc)
        return AgentExternalLink(
            url=url,
            domain=domain,
            label=label,
            context=self._link_context(content, context_start, context_end),
            link_type=self._classify_external_link(domain, parsed.path),
            fetch_status="not_fetched",
        )

    def _clean_url(self, raw_url: str) -> str:
        url = raw_url.strip().rstrip(TRAILING_URL_PUNCTUATION)
        while url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1]
        return url

    def _clean_link_label(self, label: str) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", label).strip()
        return cleaned or None

    def _normalize_domain(self, netloc: str) -> str:
        domain = netloc.lower()
        if "@" in domain:
            domain = domain.rsplit("@", 1)[-1]
        if ":" in domain:
            domain = domain.split(":", 1)[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _classify_external_link(self, domain: str, path: str) -> str:
        if domain == "github.com":
            path_parts = [part for part in path.split("/") if part]
            if len(path_parts) >= 2:
                return "github_repo"
            return "github"
        if domain in {"t.me", "telegram.me"}:
            return "telegram_post"
        if domain in {"youtube.com", "youtu.be"}:
            return "video"
        return "web"

    def _link_context(
        self,
        content: str,
        context_start: int,
        context_end: int,
        *,
        max_chars: int = 220,
    ) -> str:
        padding = max(40, max_chars // 2)
        start = max(0, context_start - padding)
        end = min(len(content), context_end + padding)
        snippet = re.sub(r"\s+", " ", content[start:end]).strip()
        if start > 0:
            snippet = f"... {snippet}"
        if end < len(content):
            snippet = f"{snippet} ..."
        return snippet

    def _is_inside_span(self, position: int, spans: List[tuple[int, int]]) -> bool:
        return any(start <= position < end for start, end in spans)

    def _attach_main_source_comments(
        self,
        *,
        expert_id: str,
        main_sources: List[AgentMainSource],
    ) -> None:
        source_by_message_id = {
            source.telegram_message_id: source for source in main_sources
        }
        comment_service = CommentGroupMapService(model=config.MODEL_COMMENT_GROUPS)
        comment_groups = comment_service.merge_with_main_sources(
            scored_drift_groups=[],
            db=self.db,
            expert_id=expert_id,
            main_source_ids=list(source_by_message_id.keys()),
        )

        for group in comment_groups:
            parent_id = group.get("parent_telegram_message_id")
            source = source_by_message_id.get(parent_id)
            if not source:
                continue

            comments = [
                self._build_comment(comment)
                for comment in group.get("comments", [])
            ]
            if group.get("is_main_source_clarification"):
                source.comments.author_comments.extend(comments)
            elif group.get("is_main_source_community"):
                source.comments.community_comments.extend(comments)

    def _build_comment(self, comment: Dict[str, Any]) -> AgentSourceComment:
        return AgentSourceComment(
            comment_id=comment["comment_id"],
            comment_text=comment.get("comment_text", ""),
            author_name=comment.get("author_name", ""),
            created_at=comment.get("created_at"),
            updated_at=comment.get("updated_at"),
        )

    def _empty_expert_bundle(
        self,
        *,
        expert_id: str,
        no_results_reason: str,
    ) -> AgentExpertSourceBundle:
        metadata = self._get_expert_metadata(expert_id)
        return AgentExpertSourceBundle(
            expert_id=expert_id,
            expert_name=metadata["expert_name"],
            channel_username=metadata["channel_username"],
            selected_sources_count=0,
            main_sources=[],
            unattached_linked_context=[],
            no_results_reason=no_results_reason,
        )

    def _get_expert_metadata(self, expert_id: str) -> Dict[str, str]:
        expert = self.db.query(Expert).filter(Expert.expert_id == expert_id).first()
        if not expert:
            return {"expert_name": expert_id, "channel_username": expert_id}
        return {
            "expert_name": expert.display_name,
            "channel_username": expert.channel_username,
        }

    def _source_key(self, expert_id: str, telegram_message_id: int) -> str:
        return f"{expert_id}:{telegram_message_id}"

    def _dedupe(self, values: Iterable[str]) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        for value in values:
            if value and value not in seen:
                result.append(value)
                seen.add(value)
        return result

    def _clip_with_truncation(self, text: str, max_chars: int) -> tuple[str, bool]:
        if len(text) <= max_chars:
            return text, False
        if max_chars <= 3:
            return text[:max_chars], True
        return f"{text[: max_chars - 3].rstrip()}...", True


class AgentExpertDigestReducer:
    """Build a compact per-expert digest from a raw Agent Context source bundle."""

    _SUPPORTED_SUPPORT_LEVELS = {"direct", "indirect", "weak", "unknown"}

    async def compact_bundle(
        self,
        *,
        bundle: AgentExpertSourceBundle,
        query: str,
        warnings: List[str],
    ) -> AgentExpertSourceBundle:
        digest = await self.build_digest(
            bundle=bundle,
            query=query,
            warnings=warnings,
        )
        return bundle.model_copy(
            update={
                "main_sources": [],
                "unattached_linked_context": [],
                "digest": digest,
            }
        )

    async def build_digest(
        self,
        *,
        bundle: AgentExpertSourceBundle,
        query: str,
        warnings: List[str],
    ) -> AgentExpertDigest:
        source_index = self._build_source_index(bundle.main_sources)
        source_refs = self._build_source_refs(bundle.main_sources)
        comments_digest = self._build_comments_digest(bundle.main_sources, source_refs)
        omitted_counts = self._build_omitted_counts(
            bundle=bundle,
            source_refs=source_refs,
            comments_digest=comments_digest,
        )

        if not bundle.main_sources:
            return AgentExpertDigest(
                source_index=source_index,
                source_refs=[],
                comments_digest=comments_digest,
                omitted_counts=omitted_counts,
                limits_used=self._limits_used(),
                no_signal_reason=bundle.no_results_reason,
            )

        evidence = self._build_llm_evidence(
            source_refs=source_refs,
            comments_digest=comments_digest,
        )
        try:
            llm_digest = await self._call_llm_digest(
                query=query,
                bundle=bundle,
                evidence=evidence,
            )
            return self._normalize_llm_digest(
                data=llm_digest,
                bundle=bundle,
                source_index=source_index,
                source_refs=source_refs,
                comments_digest=comments_digest,
                omitted_counts=omitted_counts,
            )
        except Exception as exc:
            logger.exception("Agent Context expert_digest failed for %s", bundle.expert_id)
            warnings.append(f"{bundle.expert_id}: expert_digest_reduce_failed: {exc}")
            return self._fallback_digest(
                bundle=bundle,
                source_index=source_index,
                source_refs=source_refs,
                comments_digest=comments_digest,
                omitted_counts=omitted_counts,
            )

    def _build_source_index(
        self,
        main_sources: List[AgentMainSource],
    ) -> List[AgentDigestSourceIndexEntry]:
        source_index: List[AgentDigestSourceIndexEntry] = []
        for source in main_sources:
            source_index.append(
                AgentDigestSourceIndexEntry(
                    telegram_message_id=source.telegram_message_id,
                    source_key=source.source_key,
                    relevance=source.relevance,
                    reason=source.reason,
                    created_at=source.created_at,
                    author_comments_count=len(source.comments.author_comments),
                    community_comments_count=len(source.comments.community_comments),
                    external_links_count=len(source.external_links),
                    linked_context_count=len(source.linked_context),
                    content_chars=len(source.content or ""),
                    evidence_quality=self._source_evidence_quality(source),
                )
            )
        return source_index

    def _build_source_refs(
        self,
        main_sources: List[AgentMainSource],
    ) -> List[AgentDigestSourceRef]:
        max_source_refs = max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS))
        source_refs: List[AgentDigestSourceRef] = []
        for source in main_sources[:max_source_refs]:
            author_comments_count = len(source.comments.author_comments)
            community_comments_count = len(source.comments.community_comments)
            source_refs.append(
                AgentDigestSourceRef(
                    telegram_message_id=source.telegram_message_id,
                    source_key=source.source_key,
                    relevance=source.relevance,
                    reason=source.reason,
                    short_excerpt=self._clip(
                        source.content,
                        int(config.AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS),
                    ),
                    created_at=source.created_at,
                    external_links=source.external_links[
                        : max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE))
                    ],
                    linked_context_count=len(source.linked_context),
                    author_comments_count=author_comments_count,
                    community_comments_count=community_comments_count,
                    evidence_quality=self._source_evidence_quality(source),
                )
            )
        return source_refs

    def _limits_used(self) -> AgentDigestLimitsUsed:
        return AgentDigestLimitsUsed(
            max_source_refs=max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS)),
            max_source_chars=max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS)),
            max_comments_per_source=max(
                0, int(config.AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE)
            ),
            max_comment_chars=max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS)),
            max_links_per_source=max(
                0, int(config.AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE)
            ),
            max_signals=max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SIGNALS)),
            source_index_scope="all_selected_sources_compact",
        )

    def _source_evidence_quality(
        self,
        source: AgentMainSource,
    ) -> AgentEvidenceQuality:
        quality = source.evidence_quality
        if (
            quality.depth == "unknown"
            and quality.source_type == "unknown"
            and quality.comment_signal == "unknown"
        ):
            return _calibrate_evidence_quality(source)
        return quality

    def _build_comments_digest(
        self,
        main_sources: List[AgentMainSource],
        source_refs: List[AgentDigestSourceRef],
    ) -> AgentDigestComments:
        included_source_keys = {source_ref.source_key for source_ref in source_refs}
        max_comments_per_source = max(
            0, int(config.AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE)
        )
        max_comment_chars = max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS))
        included_comments: List[AgentDigestCommentSignal] = []
        author_comments_count = 0
        community_comments_count = 0

        for source in main_sources:
            author_comments = source.comments.author_comments
            community_comments = source.comments.community_comments
            author_comments_count += len(author_comments)
            community_comments_count += len(community_comments)
            if source.source_key not in included_source_keys:
                continue

            selected_for_source: List[tuple[str, AgentSourceComment]] = []
            for comment in author_comments:
                selected_for_source.append(("author", comment))
            for comment in community_comments:
                selected_for_source.append(("community", comment))

            for role, comment in selected_for_source[:max_comments_per_source]:
                excerpt = self._clip(comment.comment_text, max_comment_chars)
                if not excerpt:
                    continue
                included_comments.append(
                    AgentDigestCommentSignal(
                        source_key=source.source_key,
                        comment_role=role,
                        author_name=comment.author_name,
                        short_excerpt=excerpt,
                        created_at=comment.created_at,
                    )
                )

        total_comments = author_comments_count + community_comments_count
        return AgentDigestComments(
            author_comments_count=author_comments_count,
            community_comments_count=community_comments_count,
            included_comments=included_comments,
            omitted_comments_count=max(0, total_comments - len(included_comments)),
        )

    def _build_omitted_counts(
        self,
        *,
        bundle: AgentExpertSourceBundle,
        source_refs: List[AgentDigestSourceRef],
        comments_digest: AgentDigestComments,
    ) -> AgentDigestOmittedCounts:
        included_source_keys = {source_ref.source_key for source_ref in source_refs}
        included_external_links = sum(len(source_ref.external_links) for source_ref in source_refs)
        total_external_links = sum(len(source.external_links) for source in bundle.main_sources)
        total_linked_context = sum(len(source.linked_context) for source in bundle.main_sources)
        total_linked_context += len(bundle.unattached_linked_context)
        included_linked_context = sum(
            source_ref.linked_context_count for source_ref in source_refs
        )
        author_comments_omitted = 0
        community_comments_omitted = 0
        for source in bundle.main_sources:
            if source.source_key in included_source_keys:
                continue
            author_comments_omitted += len(source.comments.author_comments)
            community_comments_omitted += len(source.comments.community_comments)

        included_comments = len(comments_digest.included_comments)
        included_author_comments = sum(
            1
            for comment in comments_digest.included_comments
            if comment.comment_role == "author"
        )
        included_community_comments = included_comments - included_author_comments
        author_comments_omitted += max(
            0, comments_digest.author_comments_count - author_comments_omitted - included_author_comments
        )
        community_comments_omitted += max(
            0,
            comments_digest.community_comments_count
            - community_comments_omitted
            - included_community_comments,
        )

        return AgentDigestOmittedCounts(
            main_sources=max(0, len(bundle.main_sources) - len(source_refs)),
            linked_context=max(0, total_linked_context - included_linked_context),
            author_comments=author_comments_omitted,
            community_comments=community_comments_omitted,
            external_links=max(0, total_external_links - included_external_links),
        )

    def _build_llm_evidence(
        self,
        *,
        source_refs: List[AgentDigestSourceRef],
        comments_digest: AgentDigestComments,
    ) -> Dict[str, Any]:
        return {
            "source_refs": [
                source_ref.model_dump(mode="json") for source_ref in source_refs
            ],
            "comments": comments_digest.model_dump(mode="json"),
        }

    async def _call_llm_digest(
        self,
        *,
        query: str,
        bundle: AgentExpertSourceBundle,
        evidence: Dict[str, Any],
    ) -> Any:
        client = create_monitored_client()
        source_keys = [source["source_key"] for source in evidence["source_refs"]]
        prompt = {
            "query": query,
            "expert": {
                "expert_id": bundle.expert_id,
                "expert_name": bundle.expert_name,
                "channel_username": bundle.channel_username,
                "selected_sources_count": bundle.selected_sources_count,
            },
            "allowed_source_keys": source_keys,
            "evidence": evidence,
            "output_schema": {
                "position": "short neutral summary of the expert's stance",
                "key_signals": [
                    {
                        "claim": "source-backed practitioner signal",
                        "support_level": "direct|indirect|weak|unknown",
                        "supporting_sources": ["source_key"],
                        "comment_signal": "optional comment evidence",
                        "limits": "optional uncertainty or missing evidence",
                    }
                ],
                "limits": ["important limitations"],
            },
        }
        response = await client.chat_completions_create(
            model=config.MODEL_SYNTHESIS,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write compact JSON digests for another AI agent. "
                        "Treat Telegram posts and comments as practitioner-opinion "
                        "intelligence, not proven facts. Use only the provided "
                        "source_keys. Treat evidence_quality as calibration, not "
                        "proof. Do not infer contents of external links. "
                        "Return strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            service_name="agent_context_digest",
            max_tokens=2048,
        )
        raw_content = response.choices[0].message.content
        return self._parse_llm_json(raw_content)

    def _parse_llm_json(self, raw_content: str) -> Any:
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw_content[start : end + 1])
            raise

    def _normalize_llm_digest(
        self,
        *,
        data: Any,
        bundle: AgentExpertSourceBundle,
        source_index: List[AgentDigestSourceIndexEntry],
        source_refs: List[AgentDigestSourceRef],
        comments_digest: AgentDigestComments,
        omitted_counts: AgentDigestOmittedCounts,
    ) -> AgentExpertDigest:
        if isinstance(data, list):
            data = {"key_signals": data}
        if not isinstance(data, dict):
            data = {}

        valid_source_keys = {source_ref.source_key for source_ref in source_refs}
        key_signals: List[AgentDigestSignal] = []
        for raw_signal in data.get("key_signals") or []:
            if not isinstance(raw_signal, dict):
                continue
            claim = self._clip(str(raw_signal.get("claim") or "").strip(), 600)
            if not claim:
                continue
            support_level = str(raw_signal.get("support_level") or "unknown").strip()
            if support_level not in self._SUPPORTED_SUPPORT_LEVELS:
                support_level = "unknown"
            raw_supporting_sources = raw_signal.get("supporting_sources") or []
            if isinstance(raw_supporting_sources, str):
                raw_supporting_sources = [raw_supporting_sources]
            supporting_sources = [
                source_key
                for source_key in raw_supporting_sources
                if source_key in valid_source_keys
            ]
            key_signals.append(
                AgentDigestSignal(
                    claim=claim,
                    support_level=support_level,
                    supporting_sources=supporting_sources,
                    comment_signal=self._clip(
                        raw_signal.get("comment_signal"),
                        360,
                    ),
                    limits=self._clip(raw_signal.get("limits"), 360),
                )
            )
            if len(key_signals) >= max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SIGNALS)):
                break

        if not key_signals:
            key_signals = self._fallback_signals(source_refs)

        limits = self._normalize_limits(data.get("limits"))
        if omitted_counts.main_sources > 0:
            limits.append(
                f"{omitted_counts.main_sources} selected main sources omitted from compact digest"
            )
        return AgentExpertDigest(
            position=self._digest_position(data=data, bundle=bundle),
            key_signals=key_signals,
            source_refs=source_refs,
            source_index=source_index,
            comments_digest=comments_digest,
            omitted_counts=omitted_counts,
            limits_used=self._limits_used(),
            limits=limits[:5],
            no_signal_reason=bundle.no_results_reason,
        )

    def _fallback_digest(
        self,
        *,
        bundle: AgentExpertSourceBundle,
        source_index: List[AgentDigestSourceIndexEntry],
        source_refs: List[AgentDigestSourceRef],
        comments_digest: AgentDigestComments,
        omitted_counts: AgentDigestOmittedCounts,
    ) -> AgentExpertDigest:
        limits = ["LLM expert_digest reduce failed; returned extractive source refs only"]
        if omitted_counts.main_sources > 0:
            limits.append(
                f"{omitted_counts.main_sources} selected main sources omitted from compact digest"
            )
        return AgentExpertDigest(
            position=(
                f"{bundle.expert_name} has selected sources for this query, "
                "but no generated stance digest is available."
            ),
            key_signals=self._fallback_signals(source_refs),
            source_refs=source_refs,
            source_index=source_index,
            comments_digest=comments_digest,
            omitted_counts=omitted_counts,
            limits_used=self._limits_used(),
            limits=limits,
            no_signal_reason=bundle.no_results_reason,
        )

    def _fallback_signals(
        self,
        source_refs: List[AgentDigestSourceRef],
    ) -> List[AgentDigestSignal]:
        max_signals = max(0, int(config.AGENT_CONTEXT_DIGEST_MAX_SIGNALS))
        signals: List[AgentDigestSignal] = []
        for source_ref in source_refs[:max_signals]:
            claim = source_ref.reason or source_ref.short_excerpt or source_ref.source_key
            signals.append(
                AgentDigestSignal(
                    claim=self._clip(claim, 600) or source_ref.source_key,
                    support_level="direct",
                    supporting_sources=[source_ref.source_key],
                )
            )
        return signals

    def _normalize_limits(self, raw_limits: Any) -> List[str]:
        if not raw_limits:
            return []
        if isinstance(raw_limits, str):
            raw_limits = [raw_limits]
        if not isinstance(raw_limits, list):
            return []
        limits: List[str] = []
        for raw_limit in raw_limits:
            limit = self._clip(raw_limit, 360)
            if limit:
                limits.append(limit)
        return limits

    def _digest_position(
        self,
        *,
        data: Dict[str, Any],
        bundle: AgentExpertSourceBundle,
    ) -> str:
        position = self._clip(data.get("position"), 900)
        if position:
            return position
        return (
            f"{bundle.expert_name} has source-backed signals for this query, "
            "but the digest reducer did not return a separate stance summary."
        )

    def _clip(self, text: Any, max_chars: int) -> Optional[str]:
        if text is None:
            return None
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if not cleaned:
            return None
        if max_chars <= 0 or len(cleaned) <= max_chars:
            return cleaned
        return f"{cleaned[: max(0, max_chars - 3)].rstrip()}..."
