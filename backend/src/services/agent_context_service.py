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
    AgentExpertSourceBundle,
    AgentExternalLink,
    AgentLinkedContext,
    AgentMainSource,
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
from ..services.simple_resolve_service import SimpleResolveService
from ..utils.date_utils import get_cutoff_date

logger = logging.getLogger(__name__)


MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]\n]{1,200})\]\((https?://(?:[^\s()]|\([^\s()]*\))+)\)"
)
URL_RE = re.compile(r"https?://[^\s<>\]\"']+")
TRAILING_URL_PUNCTUATION = ".,;:!?]}*"

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


@dataclass(frozen=True)
class AgentContextSearchContext:
    """Shared forced-hybrid search inputs for one Agent Context request."""

    scout_query: str
    query_embedding: List[float]
    warnings: List[str]


class AgentContextSearchUnavailable(RuntimeError):
    """Raised when Agent Context cannot satisfy its embedding-search contract."""


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

        return AgentContextResponse(
            request_id=request_id,
            mode="source_bundle",
            query=agent_request.query,
            selection_used=selection_used,
            experts=experts,
            reddit=None,
            pipeline_used=pipeline_used,
            pipeline_skipped=pipeline_skipped,
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
        return AgentMainSource(
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
