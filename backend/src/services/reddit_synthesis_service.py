"""Reddit Synthesis Service - Gemini-powered analysis of Reddit content.

This module provides synthesis of Reddit search results using Gemini via
Vertex AI to extract insights, sentiment, and actionable information from
community discussions.
"""

import asyncio
import logging
import html
import time
from typing import Optional, List, Dict, Any

from .. import config
from ..utils.language_utils import detect_query_language
from .reddit_service import RedditSearchResult, RedditSource
from .vertex_llm_client import get_vertex_llm_client, VertexLLMError
from .opencode_synth_client import (
    OpenCodeSynthesisError,
    synthesize_markdown,
)

logger = logging.getLogger(__name__)

DEFAULT_SYNTHESIS_MODEL = "gemini-3-flash-preview"

# Floor for the per-source comment budget: a huge body must not zero out
# the discussion tree (the first root is always kept regardless).
MIN_COMMENT_BUDGET_CHARS = 2000

# Step 3 of the audit plan: never let an answer die mid-table silently.
# finish_reason=length triggers exactly ONE retry with a doubled budget.
SYNTH_ESCALATION_FACTOR = 2


class RedditSynthesisService:
    """Service for synthesizing Reddit content via Gemini AI.
    
    Analyzes Reddit posts and extracts:
    - Reality Check: Bugs, edge cases, hardware issues
    - Hacks: Workarounds and unofficial solutions
    - Vibe: Overall sentiment and community opinion
    """
    
    def __init__(self, model: Optional[str] = None):
        """Initialize synthesis service.
        
        Args:
            model: Gemini model to use (default: gemini-3-flash-preview)
        """
        # FIX: Use MODEL_SYNTHESIS (gemini-3-flash-preview) for high-quality Reddit analysis
        # This matches the main synthesis model for expert responses
        self.model = model or config.MODEL_SYNTHESIS or DEFAULT_SYNTHESIS_MODEL
        self._client = get_vertex_llm_client()
        # Strong references to in-flight shadow runs (prevents task GC)
        self._shadow_tasks: set = set()

    async def _generate_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ):
        """Single synthesis LLM call.

        Returns:
            Tuple (text, finish_reason); text may be empty on provider hiccups.
        """
        response = await self._client.chat_completions_create(
            model=self.model,
            messages=messages,
            temperature=0.3,  # Lower temp for factual analysis
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        text = (getattr(choice.message, 'content', None) or "").strip()
        return text, getattr(choice, 'finish_reason', 'stop') or 'stop'
    
    async def synthesize(
        self,
        query: str,
        reddit_result: Any, # Typed as Any to support both result types
        max_sources_in_context: int = 10
    ) -> str:
        """Synthesize Reddit insights via Gemini.
        
        Args:
            query: Original user query
            reddit_result: Result from Reddit search
            max_sources_in_context: Max number of sources to include in prompt
        
        Returns:
            Markdown-formatted synthesis with insights (in query language)
        """
        # Unified check for empty results
        has_posts = False
        if hasattr(reddit_result, 'posts') and reddit_result.posts:
            has_posts = True
        elif hasattr(reddit_result, 'sources') and reddit_result.sources:
            has_posts = True
            
        if not has_posts:
            query_lang = detect_query_language(query)
            if query_lang == "Russian":
                return "Обсуждения в сообществе не найдены для этого запроса."
            return "No community discussions found for this query."
        
        # Detect query language for response
        query_language = detect_query_language(query)
        
        # Build context from sources
        context = self._build_context(reddit_result, max_sources_in_context)
        
        # Create synthesis prompt in query language
        messages = self._create_synthesis_prompt(query, context, query_language)

        backend = config.REDDIT_SYNTH_BACKEND
        started_at = time.time()

        if backend == "gemini":
            return await self._synthesize_gemini(
                query, messages, reddit_result, query_language,
                max_sources_in_context, backend="gemini",
            )

        if backend == "shadow":
            # User gets the proven Gemini answer; opencode outcome is logged
            # in parallel for A/B evaluation only. The shadow run must NOT
            # delay the user response: fire-and-forget with a kept reference.
            gemini_task = asyncio.create_task(
                self._synthesize_gemini(
                    query, messages, reddit_result, query_language,
                    max_sources_in_context, backend="gemini",
                )
            )
            shadow_task = asyncio.create_task(
                self._log_opencode_shadow(messages, query_language)
            )
            self._shadow_tasks.add(shadow_task)
            shadow_task.add_done_callback(self._shadow_tasks.discard)
            result = await gemini_task
            return result

        if backend == "opencode":
            # Explicit opt-in: tolerate longer waits, sequential fallback.
            try:
                synthesis = await self._synthesize_opencode(
                    messages, query_language,
                    timeout_s=config.OPENCODE_SYNTH_TIMEOUT_S * 1.5,
                )
                logger.info(
                    f"Reddit synthesis completed for query: {query[:50]}... | "
                    f"telemetry: backend=opencode "
                    f"model={config.OPENCODE_SYNTH_MODEL} chars={len(synthesis)} "
                    f"latency_ms={int((time.time() - started_at) * 1000)}"
                )
                return synthesis
            except Exception as e:
                logger.warning(
                    f"opencode synthesis unavailable ({e}); falling back to Gemini"
                )
            return await self._synthesize_gemini(
                query, messages, reddit_result, query_language,
                max_sources_in_context, backend="opencode->gemini_fallback",
            )

        # auto: head-start race. Free model starts immediately; if it has not
        # finished within OPENCODE_SYNTH_HEADSTART_S, Gemini joins and the
        # first complete answer wins. Worst-case latency is capped at roughly
        # head-start + one Gemini call instead of full-timeout + Gemini.
        oc_task = asyncio.create_task(
            self._synthesize_opencode(
                messages, query_language,
                timeout_s=config.OPENCODE_SYNTH_TIMEOUT_S,
            )
        )
        done, _ = await asyncio.wait(
            {oc_task}, timeout=config.OPENCODE_SYNTH_HEADSTART_S
        )
        if done:
            try:
                synthesis = oc_task.result()
                logger.info(
                    f"Reddit synthesis completed for query: {query[:50]}... | "
                    f"telemetry: backend=auto-opencode "
                    f"model={config.OPENCODE_SYNTH_MODEL} chars={len(synthesis)} "
                    f"latency_ms={int((time.time() - started_at) * 1000)}"
                )
                return synthesis
            except Exception as e:
                logger.warning(
                    f"opencode synthesis failed fast ({e}); using Gemini"
                )
                return await self._synthesize_gemini(
                    query, messages, reddit_result, query_language,
                    max_sources_in_context, backend="auto->gemini_fallback",
                )

        logger.info("opencode synthesis missed the head-start window; racing Gemini")
        gemini_task = asyncio.create_task(
            self._synthesize_gemini(
                query, messages, reddit_result, query_language,
                max_sources_in_context, backend="auto-race",
            )
        )
        winner: Optional[str] = None
        pending_tasks = {oc_task, gemini_task}
        while pending_tasks and winner is None:
            done, pending_tasks = await asyncio.wait(
                pending_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for finished in done:
                if finished.cancelled():
                    continue
                exc = finished.exception()
                if exc is None:
                    winner = finished.result()
                else:
                    logger.warning(f"synthesis race participant failed: {exc}")
        for leftover in pending_tasks:
            leftover.cancel()  # opencode client cleans up its session
        if winner is not None:
            return winner

        # Unreachable in practice: _synthesize_gemini never raises.
        return await self._synthesize_gemini(
            query, messages, reddit_result, query_language,
            max_sources_in_context, backend="auto->gemini_last_resort",
        )

    async def _synthesize_gemini(
        self,
        query: str,
        messages: List[Dict[str, str]],
        reddit_result: Any,
        query_language: str,
        max_sources_in_context: int,
        *,
        backend: str,
    ) -> str:
        """Gemini/OpenRouter synthesis path (previous default behavior)."""
        try:
            # How many sources actually entered the context (for telemetry)
            if hasattr(reddit_result, 'posts'):
                context_source_count = min(
                    len(reddit_result.posts or []), max_sources_in_context
                )
                count = reddit_result.total_found
            else:
                context_source_count = min(
                    len(reddit_result.sources or []), max_sources_in_context
                )
                count = reddit_result.found_count

            synthesis, finish_reason = await self._generate_completion(
                messages, config.REDDIT_SYNTH_MAX_TOKENS
            )
            used_max_tokens = config.REDDIT_SYNTH_MAX_TOKENS

            # Auto-escalation (Step 3): a length-truncated answer is silently
            # broken (cut mid-table / before the action block). Retry ONCE
            # with a doubled budget instead of shipping the stump.
            if finish_reason == "length":
                used_max_tokens *= SYNTH_ESCALATION_FACTOR
                logger.warning(
                    f"Reddit synthesis truncated at {config.REDDIT_SYNTH_MAX_TOKENS} "
                    f"tokens (finish_reason=length), retrying once with "
                    f"{used_max_tokens}"
                )
                retry_text, retry_finish = await self._generate_completion(
                    messages, used_max_tokens
                )
                if retry_text:
                    synthesis, finish_reason = retry_text, retry_finish

            logger.info(
                f"Reddit synthesis completed for query: {query[:50]}... "
                f"(found {count} posts) | telemetry: backend={backend} "
                f"finish_reason={finish_reason} "
                f"chars={len(synthesis)} max_tokens={used_max_tokens} "
                f"context_sources={context_source_count}"
            )

            return synthesis

        except VertexLLMError as e:
            logger.error(f"Gemini synthesis failed: {e}")
            # Fallback: return raw markdown if synthesis fails
            return self._create_fallback_response(reddit_result, query_language)
        except Exception as e:
            logger.error(f"Unexpected error in synthesis: {e}")
            return self._create_fallback_response(reddit_result, query_language)

    @staticmethod
    def is_explicit_abstention(text: str) -> bool:
        """Recognize only the canonical, standalone synthesis abstention."""
        normalized = (text or "").strip().lstrip("#>*_- \t\r\n").lower()
        normalized = normalized.rstrip(".!?。 ")
        return normalized in {
            "релевантных обсуждений на reddit по этой конкретной теме не найдено",
            "no relevant reddit discussions found for this specific topic",
        }

    @staticmethod
    def _reject_opencode_output(text: str, query_language: str) -> Optional[str]:
        """Return a rejection reason, or None when output is acceptable."""
        if not text or not text.strip():
            return "empty response"
        if RedditSynthesisService.is_explicit_abstention(text):
            return None  # honest abstain is a valid short answer
        stripped = text.strip()
        if len(stripped) < 200:
            return f"suspiciously short ({len(stripped)} chars)"
        final_marker = "КУДА ИДИ" if query_language == "Russian" else "WHERE TO GO"
        if final_marker not in text:
            return "final action block missing (likely truncation)"
        return None

    async def _synthesize_opencode(
        self,
        messages: List[Dict[str, str]],
        query_language: str,
        *,
        timeout_s: float,
    ) -> str:
        """One headless-opencode attempt; raises on failure/rejection."""
        system_prompt = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        user_prompt = next(
            (m["content"] for m in messages if m["role"] == "user"), ""
        )
        text = await synthesize_markdown(
            system_prompt, user_prompt, timeout_s=timeout_s
        )
        reason = self._reject_opencode_output(text, query_language)
        if reason:
            raise OpenCodeSynthesisError(f"output rejected: {reason}")
        return text

    async def _log_opencode_shadow(
        self,
        messages: List[Dict[str, str]],
        query_language: str,
    ) -> None:
        """Run the free-model path for A/B telemetry; never raises."""
        started_at = time.time()
        try:
            text = await self._synthesize_opencode(
                messages,
                query_language,
                timeout_s=config.OPENCODE_SYNTH_TIMEOUT_S,
            )
            logger.info(
                f"[shadow] opencode synthesis OK model="
                f"{config.OPENCODE_SYNTH_MODEL} chars={len(text)} "
                f"latency_ms={int((time.time() - started_at) * 1000)}"
            )
        except Exception as e:
            logger.warning(
                f"[shadow] opencode synthesis failed: {e} "
                f"latency_ms={int((time.time() - started_at) * 1000)}"
            )
    
    # High-signal keywords indicating the OP found the solution helpful
    VERIFICATION_KEYWORDS = {
        "worked", "thanks", "thank you", "solved", "fixed", 
        "сработало", "спасибо", "решил"
    }

    def _format_comments_recursive(self, comments: List[Dict[str, Any]], depth: int = 0, max_depth: int = 3, post_author: str = None, start_number: int = 1) -> str:
        """Recursively format comments tree.
        
        Args:
            comments: List of comment dictionaries
            depth: Current nesting depth
            max_depth: Maximum recursion depth
            post_author: Username of the post author (OP) to detect verified solutions
            start_number: Numbering seed for top-level entries (the budget
                fitter renumbers roots after score-desc sorting)
        """
        if depth > max_depth or not comments:
            return ""
        
        output = []
        indent = "  " * (depth + 1)
        
        for i, comment in enumerate(comments, start_number):
            # Handle different comment structures
            if isinstance(comment, str):
                # Legacy format: simple string comment
                author = "unknown"
                body = comment
                score = 0
                replies = []
                flair = ""
                distinguished = ""
                stickied = False
                is_op = False
            elif isinstance(comment, dict):
                author = comment.get('author', 'unknown')
                raw_body = comment.get('body', '') or comment.get('text', '')
                body = html.unescape(raw_body)
                score = comment.get('score', 0)
                replies = comment.get('replies') or []
                # New Metadata Fields
                flair = comment.get('flair', '')
                distinguished = comment.get('distinguished', '')
                stickied = comment.get('stickied', False)
                # Check for explicit is_op flag or compare with post_author (ignoring deleted/unknown)
                is_valid_author = author and author.lower() not in ["[deleted]", "unknown"]
                is_op = comment.get('is_op', False) or (is_valid_author and post_author and author.lower() == post_author.lower())
            else:
                # Fallback for objects
                author = getattr(comment, 'author', 'unknown')
                raw_body = getattr(comment, 'body', '') or getattr(comment, 'text', '')
                body = html.unescape(raw_body)
                score = getattr(comment, 'score', 0)
                replies = getattr(comment, 'replies', []) or []
                # New Metadata Fields
                flair = getattr(comment, 'flair', '')
                distinguished = getattr(comment, 'distinguished', '')
                stickied = getattr(comment, 'stickied', False)
                # Check for explicit is_op flag or compare with post_author (ignoring deleted/unknown)
                is_valid_author = author and author.lower() not in ["[deleted]", "unknown"]
                is_op = getattr(comment, 'is_op', False) or (is_valid_author and post_author and author.lower() == post_author.lower())

            if body:
                # Detect OP Verification (Golden Answer)
                # If the OP replied to this comment saying "thanks", "solved", "worked", etc.
                is_verified = False
                if post_author and post_author != "unknown" and replies:
                    for reply in replies:
                        # Check reply author safely
                        if isinstance(reply, str):
                            r_author = "unknown"
                            r_body = reply
                        elif isinstance(reply, dict):
                            r_author = reply.get('author', 'unknown')
                            r_body = reply.get('body', '') or reply.get('text', '')
                        else:
                            r_author = getattr(reply, 'author', 'unknown')
                            r_body = getattr(reply, 'body', '') or getattr(reply, 'text', '')
                        
                        if r_author == post_author and any(kw in r_body.lower() for kw in self.VERIFICATION_KEYWORDS):
                            is_verified = True
                            break

                # Truncate extremely long comments but keep enough for context (2000 chars)
                if len(body) > 2000:
                    body = body[:2000] + "... (truncated)"
                
                # Build Metadata Tags
                tags = []
                if is_op:
                    tags.append("[OP]")
                if distinguished: # moderator/admin
                    tags.append(f"[{distinguished.upper()}]")
                if stickied:
                    tags.append("[PINNED]")
                if flair:
                    tags.append(f'[Flair: "{flair}"]')
                if is_verified:
                    tags.append("[✅ OP VERIFIED SOLUTION]")
                
                tags_str = " ".join(tags) + " " if tags else ""
                
                prefix = "└─ " if depth > 0 else f"{i}. "
                # Format: [OP] [Flair: "Dev"] [User | Score: 100]: Body
                header = f"{indent}{prefix}{tags_str}[{author} | Score: {score}]: "
                
                # Handle multi-line content (code blocks, paragraphs) by indenting subsequent lines
                # This preserves structure for the LLM
                content_indent = "\n" + indent + ("   " if depth > 0 else "   ")
                formatted_body = body.replace("\n", content_indent)
                
                output.append(f"{header}{formatted_body}")
                
                # Process replies if they exist and we haven't hit max depth
                if replies:
                    replies_text = self._format_comments_recursive(replies, depth + 1, max_depth, post_author=post_author)
                    if replies_text:
                        output.append(replies_text)
        
        return "\n".join(output)

    def _fit_comments_to_budget(
        self,
        comments: List[Any],
        post_author: str,
        budget_chars: int,
    ):
        """Fit the comment tree into a char budget (Step 2 of the audit plan).

        Top-level roots are ranked by score desc and capped at
        REDDIT_SYNTH_COMMENT_TOP_K. Whole roots (with their reply subtrees)
        are appended while they fit into budget_chars — never truncated
        mid-comment. The first root is always kept even if it alone exceeds
        the budget, so a source can never lose all discussion.

        Args:
            comments: Top-level comment list (any supported shape)
            post_author: Post author for OP verification detection
            budget_chars: Char budget for the whole formatted tree

        Returns:
            Tuple (formatted_text, hit_budget) where hit_budget is True only
            when the char budget stopped further roots from being added.
        """
        def _root_score(c: Any) -> int:
            if isinstance(c, dict):
                return c.get('score', 0) or 0
            if isinstance(c, str):
                return 0
            return getattr(c, 'score', 0) or 0

        top_k = max(1, config.REDDIT_SYNTH_COMMENT_TOP_K)
        roots = sorted(comments, key=_root_score, reverse=True)[:top_k]

        chunks: List[str] = []
        used = 0
        hit_budget = False
        for i, root in enumerate(roots, 1):
            chunk = self._format_comments_recursive(
                [root], post_author=post_author, start_number=i
            )
            if chunks and used + len(chunk) > budget_chars:
                hit_budget = True
                break
            chunks.append(chunk)
            used += len(chunk)

        return "\n".join(chunks), hit_budget

    def _build_context(
        self,
        reddit_result: Any, # Typed as Any to support both result types during migration
        max_sources: int
    ) -> str:
        """Build context string from Reddit sources.
        
        Args:
            reddit_result: Reddit search result (EnhancedSearchResult or RedditSearchResult)
            max_sources: Maximum sources to include
        
        Returns:
            Formatted context string
        """
        # Handle both result types
        if hasattr(reddit_result, 'posts'):
            sources = reddit_result.posts[:max_sources]
        else:
            sources = reddit_result.sources[:max_sources]
        
        # DEBUG: Log sources content
        logger.info(f"SYNTHESIS DEBUG: Building context from {len(sources)} sources")
        
        context_parts = []
        budget_capped_sources = 0
        for i, src in enumerate(sources, 1):
            # Handle different content attributes (selftext vs content)
            raw_content = getattr(src, 'selftext', '') or getattr(src, 'content', '') or "[No content available]"

            # Body preview cap: the answer-bearing part sits in the opening
            # body; the discussion tree below carries practitioner detail.
            SYNTH_SOURCE_CHAR_CAP = 8000
            content_preview = raw_content[:SYNTH_SOURCE_CHAR_CAP]
            if len(raw_content) > SYNTH_SOURCE_CHAR_CAP:
                content_preview += "... (truncated)"

            # Comment budget (Step 2): score-desc top-K roots fitted into the
            # per-source char cap shared between body and discussion tree.
            comments_section = ""
            # Handle comments attribute (top_comments vs comments)
            comments_data = getattr(src, 'top_comments', []) or getattr(src, 'comments', [])

            if comments_data:
                # Pass post author to recursive formatter for OP verification detection
                post_author = getattr(src, 'author', 'unknown')
                comment_budget = max(
                    MIN_COMMENT_BUDGET_CHARS,
                    config.REDDIT_SYNTH_SOURCE_CHAR_CAP - len(content_preview),
                )
                comments_text, hit_budget = self._fit_comments_to_budget(
                    comments_data,
                    post_author=post_author,
                    budget_chars=comment_budget,
                )
                if comments_text:
                    comments_section = f"\n   - **Discussion Tree:**\n{comments_text}"
                if hit_budget:
                    budget_capped_sources += 1
            
            # Thread age: created_utc is present on RedditPost; discovery
            # candidates (Serper) carry 0 → unknown age.
            created_utc = getattr(src, 'created_utc', 0) or 0
            if created_utc > 0:
                age_days = max(1, int((time.time() - created_utc) / 86400))
                age_label = f"{age_days} days ago"
            else:
                age_label = "unknown"
            channel = getattr(src, 'found_by_strategy', None) or "native_search"

            context_parts.append(
                f"{i}. **{src.title}** (r/{src.subreddit})\n"
                f"   - Content: {content_preview}\n"
                # Use getattr for stats to be safe
                f"   - Stats: Score: {getattr(src, 'score', 0)} | Comments: {getattr(src, 'num_comments', getattr(src, 'comments_count', 0))}\n"
                f"   - Age: {age_label} | Channel: {channel}\n"
                f"   - URL: {src.url}"
                f"{comments_section}"
            )

        if budget_capped_sources:
            logger.info(
                f"Comment budget: {budget_capped_sources}/{len(sources)} sources "
                f"trimmed to fit REDDIT_SYNTH_SOURCE_CHAR_CAP="
                f"{config.REDDIT_SYNTH_SOURCE_CHAR_CAP} "
                f"(top_k={config.REDDIT_SYNTH_COMMENT_TOP_K})"
            )

        return "\n\n".join(context_parts)
    
    def _create_synthesis_prompt(
        self,
        query: str,
        context: str,
        query_language: str = "English"
    ) -> List[Dict[str, str]]:
        """Create synthesis prompt for Gemini.
        
        Args:
            query: User query
            context: Reddit posts context
            query_language: Language of the query (English or Russian)
        
        Returns:
            Messages list for chat completion
        """
        # Determine response language
        is_russian = query_language == "Russian"
        
        # Get current date for context (Project is in 2026)
        from datetime import datetime
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        if is_russian:
            system_prompt = f"""<?xml version="1.0" encoding="UTF-8"?>
<system_prompt>
    <role>Вы — Ведущий Инженер (Staff Engineer), анализирующий базу знаний Reddit для коллеги.</role>
    <context>
        <date>СЕГОДНЯ: {current_date_str}. Учитывайте, что мы в 2026 году.</date>
    </context>
    <task>Синтезировать плотный технический ответ без повторов и необязательных деталей. Сначала дать решение и действия, затем — подтверждающие подробности.</task>
    <evaluation_criteria>
        <signal type="authority">FLAIRS: Доверяйте пользователям с плашками типа "Maintainer", "Dev", "Contributor".</signal>
        <signal type="verification" priority="highest">OP VERIFICATION: Решения, помеченные `[✅ OP VERIFIED SOLUTION]`, имеют наивысший приоритет (автор подтвердил, что это сработало).</signal>
        <signal type="skepticism">SCORE SKEPTICISM: Высокий рейтинг комментария не всегда означает техническую правоту (это может быть шутка). Проверяйте факты.</signal>
    </evaluation_criteria>
    <analysis_rules>
        <rule type="discovery">HIDDEN GEMS: Ищите в глубине комментариев конкретные флаги, конфиги, бенчмарки, которые упустил автор поста.</rule>
        <rule type="alternative">CONTROVERSIAL TAKES: Если есть сильные аргументы ПРОТИВ популярного мнения — вы обязаны их привести.</rule>
        <rule type="context">VERSION SPECIFIC: Указывайте версии библиотек/софта, о которых идет речь.</rule>
        <rule type="citation">LINK PRIORITY: Ссылки на GitHub/HuggingFace = [PRIMARY SOURCE].</rule>
        <rule type="evidence_language" priority="highest">EVIDENCE LANGUAGE: Слова «консенсус», «стандарт» и «смена тренда» разрешены только когда утверждение независимо подтверждают минимум два разных релевантных источника [S#]. В том же предложении приведите обе ссылки. Иначе пишите «в одном обсуждении», «несколько пользователей» или «данных недостаточно».</rule>
        <rule type="trend">PIVOT ALERT: Блок `🚨 **СМЕНА ТРЕНДА**` разрешён только при выполнении правила EVIDENCE LANGUAGE и явном сравнении прежней и новой практики в источниках. Не добавляйте его для привлечения внимания.</rule>
        <rule type="relevance_gate" priority="highest">РЕЛЕВАНТНОСТЬ: Перед синтезом проверьте — найденные посты ДЕЙСТВИТЕЛЬНО отвечают на вопрос пользователя? Если посты не по теме (например, вопрос про Claude Code Skills, а посты про Unix CLI), верните ровно одно предложение и больше ничего: "Релевантных обсуждений на Reddit по этой конкретной теме не найдено." НЕ синтезируйте нерелевантный контент как будто он отвечает на вопрос.</rule>
    </analysis_rules>
    <output_format>
        <section order="1" max_words="120">Executive Summary: прямой ответ с уровнем уверенности, без объявления консенсуса по умолчанию.</section>
        <section order="2" required="always" max_words="150">КУДА ИДТИ: ранжированные действия 1→2→3 с условиями («если есть X → путь Y»; «если бюджет Z → вариант N»). Этот итоговый блок обязан идти ДО Deep Dive, чтобы ответ оставался полезным при обрыве генерации.</section>
        <section order="3" required="only_if_enough_numeric_evidence" max_rows="6">СРАВНИТЕЛЬНАЯ ТАБЛИЦА: добавляйте только если источники дают минимум две содержательные строки сравнения с конкретными числами. Каждая строка должна иметь ссылку [S#]. Если чисел недостаточно, используйте короткий маркированный список или пропустите сравнение; не заполняйте таблицу общими словами.</section>
        <section order="4" max_words="600">Deep Dive: только код, конфиги, архитектура и причинно-следственные детали, которые непосредственно отвечают на вопрос.</section>
        <section order="5" max_words="180">Minority Report: только реально представленное в источниках альтернативное мнение; пропустите секцию, если такого мнения нет.</section>
        <section order="6" max_words="220">Battle-tested Edge Cases: только реальные баги и проблемы из источников; пропустите секцию, если данных нет.</section>
        <style>Максимальная плотность информации без повторов. Соблюдайте лимиты секций. Не повторяйте Executive Summary или КУДА ИДТИ в конце. Отвечайте ТОЛЬКО на русском языке.</style>
        <style type="numbers">ИЗВЛЕКАЙ ЧИСЛА из тредов: цены, лимиты, VRAM, бенчмарки, сроки. Общие слова («быстрый», «дешёвый») без числа не считаются фактом.</style>
        <style type="confidence">МАРКИРУЙ ДОСТОВЕРНОСТЬ ключевых утверждений: [подтверждено сообществом] — несколько независимых тредов или OP VERIFIED; [единичный отчёт] — один источник без подтверждения; [вывод автора анализа] — твой синтез без прямого подтверждения в тредах.</style>
        <style type="freshness">Учитывай Age источника: для быстро меняющихся данных (цены, версии, лимиты) предпочитай свежие треды и помечай данные из старых тредов как возможно устаревшие.</style>
        <style type="provenance">Учитывай Channel источника: serp_google_discovery = тред валидирован Google-ранжированием; arctic_targeted_archive = архивный поиск по сабам; *_relevance / fallback_top_year = нативный поиск Reddit.</style>
    </output_format>
</system_prompt>"""

            user_prompt = f"""**Вопрос:** {query}

**База знаний Reddit:**

{context}

Дайте экспертный ответ, актуальный на {current_date_str}."""
        else:
            system_prompt = f"""<?xml version="1.0" encoding="UTF-8"?>
<system_prompt>
    <role>You are a Staff Engineer analyzing the Reddit knowledge base for a colleague.</role>
    <context>
        <date>TODAY IS: {current_date_str}. Keep in mind we are in 2026.</date>
    </context>
    <task>Synthesize a dense technical answer without repetition or optional detail. Give the decision and actions first, then supporting detail.</task>
    <evaluation_criteria>
        <signal type="authority">FLAIRS: Trust users with flairs like "Maintainer", "Dev", "Contributor".</signal>
        <signal type="verification" priority="highest">OP VERIFICATION: Solutions marked `[✅ OP VERIFIED SOLUTION]` have highest priority (author confirmed it worked).</signal>
        <signal type="skepticism">SCORE SKEPTICISM: High score does not always mean technical correctness (could be a joke). Verify facts.</signal>
    </evaluation_criteria>
    <analysis_rules>
        <rule type="discovery">HIDDEN GEMS: Dig deep into comments for specific flags, configs, benchmarks that the OP missed.</rule>
        <rule type="alternative">CONTROVERSIAL TAKES: If there are strong arguments AGAINST the popular opinion, you MUST include them.</rule>
        <rule type="context">VERSION SPECIFIC: Mention library/software versions discussed.</rule>
        <rule type="citation">LINK PRIORITY: Links to GitHub/HuggingFace = [PRIMARY SOURCE].</rule>
        <rule type="evidence_language" priority="highest">EVIDENCE LANGUAGE: The terms "consensus", "standard", and "community pivot" may be used only when at least two distinct relevant sources [S#] independently support the claim. Cite both sources in the same sentence. Otherwise say "one discussion", "several users", or "the evidence is insufficient".</rule>
        <rule type="trend">PIVOT ALERT: A `🚨 **COMMUNITY PIVOT**` block is allowed only when the EVIDENCE LANGUAGE rule is satisfied and the sources explicitly contrast an earlier and a newer practice. Never add it merely for emphasis.</rule>
        <rule type="relevance_gate" priority="highest">RELEVANCE CHECK: Before synthesizing, verify that the posts actually answer the user's question. If posts are off-topic (e.g., question is about Claude Code Skills but posts discuss Unix CLI), return exactly one sentence and nothing else: "No relevant Reddit discussions found for this specific topic." Do NOT synthesize irrelevant content as if it answers the question.</rule>
    </analysis_rules>
    <output_format>
        <section order="1" max_words="120">Executive Summary: direct answer with confidence level; do not declare consensus by default.</section>
        <section order="2" required="always" max_words="150">WHERE TO GO: ranked actions 1→2→3 with conditions ("if X → path Y"; "if budget Z → option N"). This final recommendation block must appear BEFORE the Deep Dive so the answer remains useful if generation is truncated.</section>
        <section order="3" required="only_if_enough_numeric_evidence" max_rows="6">COMPARISON TABLE: include it only when the sources provide at least two meaningful comparison rows with concrete numbers. Cite [S#] in every row. If numeric evidence is insufficient, use a short bullet list or omit the comparison; never fill a table with generic wording.</section>
        <section order="4" max_words="600">Deep Dive: only code, configuration, architecture, and causal details that directly answer the question.</section>
        <section order="5" max_words="180">Minority Report: only an alternative view actually present in the sources; omit the section when none exists.</section>
        <section order="6" max_words="220">Battle-tested Edge Cases: only real bugs and production issues found in the sources; omit the section when evidence is absent.</section>
        <style>Maximum information density without repetition. Respect every section limit. Do not repeat the Executive Summary or WHERE TO GO at the end. Answer in English.</style>
        <style type="numbers">EXTRACT NUMBERS from threads: prices, limits, VRAM, benchmarks, timelines. Vague wording ("fast", "cheap") without a number does not count as a fact.</style>
        <style type="confidence">TAG CONFIDENCE of key claims: [community-confirmed] — multiple independent threads or OP VERIFIED; [single report] — one uncorroborated source; [analyst inference] — your synthesis without direct confirmation in threads.</style>
        <style type="freshness">Respect source Age: for fast-moving data (prices, versions, limits) prefer fresh threads and flag data from old threads as possibly outdated.</style>
        <style type="provenance">Respect source Channel: serp_google_discovery = thread validated by Google ranking; arctic_targeted_archive = subreddit archive search; *_relevance / fallback_top_year = native Reddit search.</style>
    </output_format>
</system_prompt>"""

            user_prompt = f"""**Query:** {query}

**Reddit Knowledge Base:**

{context}

Provide an expert technical synthesis relevant for {current_date_str}."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _create_fallback_response(
        self, 
        reddit_result: Any,
        query_language: str = "English"
    ) -> str:
        """Create fallback response when synthesis fails.
        
        Args:
            reddit_result: Reddit search result
            query_language: Language of the query
        
        Returns:
            Basic markdown response with sources
        """
        is_russian = query_language == "Russian"
        
        # Unified access
        if hasattr(reddit_result, 'posts'):
            sources = reddit_result.posts
            count = reddit_result.total_found
        else:
            sources = reddit_result.sources
            count = reddit_result.found_count
            
        if not sources:
            if is_russian:
                return "Обсуждения в сообществе не найдены для этого запроса."
            return "No community discussions found for this query."
        
        if is_russian:
            lines = ["### Обсуждения в сообществе", ""]
            lines.append(f"Найдено {count} релевантных постов на Reddit:")
        else:
            lines = ["### Community Discussions", ""]
            lines.append(f"Found {count} relevant posts on Reddit:")
        
        lines.append("")
        
        for src in sources[:5]:
            # FIX: Escape markdown special characters to prevent injection/broken formatting
            escaped_title = src.title.replace("[", "\\[").replace("]", "\\]")
            escaped_url = src.url.replace(")", "%29")  # URL-encode closing parenthesis
            
            # Use getattr for unified access
            subreddit = getattr(src, 'subreddit', 'unknown')
            score = getattr(src, 'score', 0)
            comments = getattr(src, 'num_comments', getattr(src, 'comments_count', 0))
            
            lines.append(f"- **[{escaped_title}]({escaped_url})** (r/{subreddit})")
            if is_russian:
                lines.append(f"  Рейтинг: {score} | Комментариев: {comments}")
            else:
                lines.append(f"  Score: {score} | Comments: {comments}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def quick_synthesize(
        self,
        query: str,
        reddit_result: Any
    ) -> Dict[str, Any]:
        """Quick synthesis returning structured data.
        
        Args:
            query: User query
            reddit_result: Reddit search result
        
        Returns:
            Dictionary with synthesis text and metadata
        """
        synthesis_text = await self.synthesize(query, reddit_result)
        
        # Unified access for stats
        if hasattr(reddit_result, 'posts'):
            count = len(reddit_result.posts)
            total = reddit_result.total_found
        else:
            count = len(reddit_result.sources)
            total = reddit_result.found_count
        
        return {
            "synthesis": synthesis_text,
            "sources_count": count,
            "total_found": total,
            "processing_time_ms": reddit_result.processing_time_ms,
            "model_used": self.model
        }


# Convenience function
async def synthesize_reddit_content(
    query: str,
    reddit_result: RedditSearchResult,
    model: Optional[str] = None
) -> str:
    """Convenience function to synthesize Reddit content.
    
    Args:
        query: User query
        reddit_result: Reddit search result
        model: Optional model override
    
    Returns:
        Synthesis markdown text
    """
    service = RedditSynthesisService(model)
    return await service.synthesize(query, reddit_result)
