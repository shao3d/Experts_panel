"""Reddit Synthesis Service - Gemini-powered analysis of Reddit content.

This module provides synthesis of Reddit search results using Google Gemini AI
to extract insights, sentiment, and actionable information from community discussions.
"""

import logging
import html
from typing import Optional, List, Dict, Any

from .. import config
from ..utils.language_utils import detect_query_language
from .reddit_service import RedditSearchResult, RedditSource
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError

logger = logging.getLogger(__name__)

DEFAULT_SYNTHESIS_MODEL = "gemini-2.0-flash"


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
            model: Gemini model to use (default: gemini-2.0-flash)
        """
        # FIX: Use MODEL_SYNTHESIS (gemini-3-flash-preview) for high-quality Reddit analysis
        # This matches the main synthesis model for expert responses
        self.model = model or config.MODEL_SYNTHESIS or DEFAULT_SYNTHESIS_MODEL
        self._client = create_google_ai_studio_client()
    
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

        try:
            response = await self._client.chat_completions_create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temp for factual analysis
                max_tokens=4096
            )
            
            synthesis = response.choices[0].message.content.strip()
            
            # Unified access for logging
            if hasattr(reddit_result, 'posts'):
                count = reddit_result.total_found
            else:
                count = reddit_result.found_count
                
            logger.info(
                f"Reddit synthesis completed for query: {query[:50]}... "
                f"(found {count} posts)"
            )
            
            return synthesis
            
        except GoogleAIStudioError as e:
            logger.error(f"Gemini synthesis failed: {e}")
            # Fallback: return raw markdown if synthesis fails
            return self._create_fallback_response(reddit_result, query_language)
        except Exception as e:
            logger.error(f"Unexpected error in synthesis: {e}")
            return self._create_fallback_response(reddit_result, query_language)
    
    # High-signal keywords indicating the OP found the solution helpful
    VERIFICATION_KEYWORDS = {
        "worked", "thanks", "thank you", "solved", "fixed", 
        "сработало", "спасибо", "решил"
    }

    def _format_comments_recursive(self, comments: List[Dict[str, Any]], depth: int = 0, max_depth: int = 3, post_author: str = None) -> str:
        """Recursively format comments tree.
        
        Args:
            comments: List of comment dictionaries
            depth: Current nesting depth
            max_depth: Maximum recursion depth
            post_author: Username of the post author (OP) to detect verified solutions
        """
        if depth > max_depth or not comments:
            return ""
        
        output = []
        indent = "  " * (depth + 1)
        
        for i, comment in enumerate(comments, 1):
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
        for i, src in enumerate(sources, 1):
            # Handle different content attributes (selftext vs content)
            raw_content = getattr(src, 'selftext', '') or getattr(src, 'content', '') or "[No content available]"
            
            # Increase limit to 15,000 chars to leverage Gemini's context window
            content_preview = raw_content[:15000]
            if len(raw_content) > 15000:
                content_preview += "... (truncated)"
            
            # Format top comments with tree structure
            comments_section = ""
            # Handle comments attribute (top_comments vs comments)
            comments_data = getattr(src, 'top_comments', []) or getattr(src, 'comments', [])
            
            if comments_data:
                # Pass post author to recursive formatter for OP verification detection
                post_author = getattr(src, 'author', 'unknown')
                comments_text = self._format_comments_recursive(comments_data, post_author=post_author)
                if comments_text:
                    comments_section = f"\n   - **Discussion Tree:**\n{comments_text}"
            
            context_parts.append(
                f"{i}. **{src.title}** (r/{src.subreddit})\n"
                f"   - Content: {content_preview}\n"
                # Use getattr for stats to be safe
                f"   - Stats: Score: {getattr(src, 'score', 0)} | Comments: {getattr(src, 'num_comments', getattr(src, 'comments_count', 0))}\n"
                f"   - URL: {src.url}"
                f"{comments_section}"
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
    <task>Синтезировать ИСЧЕРПЫВАЮЩИЙ технический ответ (+30% деталей по сравнению с обычным summary).</task>
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
        <rule type="trend">PIVOT ALERT: Если сообщество меняет стандарт (например, "LangChain умер, бери LangGraph") — начните с блока `🚨 **СМЕНА ТРЕНДА**`.</rule>
        <rule type="relevance_gate" priority="highest">РЕЛЕВАНТНОСТЬ: Перед синтезом проверьте — найденные посты ДЕЙСТВИТЕЛЬНО отвечают на вопрос пользователя? Если посты не по теме (например, вопрос про Claude Code Skills, а посты про Unix CLI), честно скажите: "Релевантных обсуждений на Reddit по этой конкретной теме не найдено." НЕ синтезируйте нерелевантный контент как будто он отвечает на вопрос.</rule>
    </analysis_rules>
    <output_format>
        <section order="1">Executive Summary: Прямой ответ, консенсус 2026 года.</section>
        <section order="2">Deep Dive: Код, конфиги, архитектура. Самая большая секция.</section>
        <section order="3">Minority Report: Альтернативные мнения опытных инженеров (особенно с Flair), несогласные с мейнстримом.</section>
        <section order="4">Battle-tested Edge Cases: Реальные баги и проблемы из продакшена.</section>
        <style>Максимальная плотность информации. Без воды. Используйте Markdown таблицы для сравнения. Отвечайте ТОЛЬКО на русском языке.</style>
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
    <task>Synthesize a COMPREHENSIVE technical answer (+30% detail density compared to standard summary).</task>
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
        <rule type="trend">PIVOT ALERT: If the community is shifting standards (e.g., "LangChain is dead, use LangGraph") — start with a `🚨 **COMMUNITY PIVOT**` block.</rule>
        <rule type="relevance_gate" priority="highest">RELEVANCE CHECK: Before synthesizing, verify that the posts actually answer the user's question. If posts are off-topic (e.g., question is about Claude Code Skills but posts discuss Unix CLI), honestly state: "No relevant Reddit discussions found for this specific topic." Do NOT synthesize irrelevant content as if it answers the question.</rule>
    </analysis_rules>
    <output_format>
        <section order="1">Executive Summary: Direct answer, 2026 consensus.</section>
        <section order="2">Deep Dive: Code, configs, architecture. Largest section.</section>
        <section order="3">Minority Report: Alternative views from experienced engineers (esp. with Flair) against the mainstream.</section>
        <section order="4">Battle-tested Edge Cases: Real-world bugs and production issues.</section>
        <style>Maximum information density. No fluff. Use Markdown tables for comparisons. Answer in English.</style>
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
