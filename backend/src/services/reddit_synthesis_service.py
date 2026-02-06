"""Reddit Synthesis Service - Gemini-powered analysis of Reddit content.

This module provides synthesis of Reddit search results using Google Gemini AI
to extract insights, sentiment, and actionable information from community discussions.
"""

import logging
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
        reddit_result: RedditSearchResult,
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
        if not reddit_result.sources:
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
                temperature=0.3  # Lower temp for factual analysis
            )
            
            synthesis = response.choices[0].message.content.strip()
            logger.info(
                f"Reddit synthesis completed for query: {query[:50]}... "
                f"(found {reddit_result.found_count} posts)"
            )
            
            return synthesis
            
        except GoogleAIStudioError as e:
            logger.error(f"Gemini synthesis failed: {e}")
            # Fallback: return raw markdown if synthesis fails
            return self._create_fallback_response(reddit_result, query_language)
        except Exception as e:
            logger.error(f"Unexpected error in synthesis: {e}")
            return self._create_fallback_response(reddit_result, query_language)
    
    def _build_context(
        self,
        reddit_result: RedditSearchResult,
        max_sources: int
    ) -> str:
        """Build context string from Reddit sources.
        
        Args:
            reddit_result: Reddit search result
            max_sources: Maximum sources to include
        
        Returns:
            Formatted context string
        """
        sources = reddit_result.sources[:max_sources]
        
        # DEBUG: Log sources content
        logger.info(f"SYNTHESIS DEBUG: Building context from {len(sources)} sources")
        for i, src in enumerate(sources[:3]):
            has_content = bool(src.content) and len(src.content) > 10
            logger.info(f"SYNTHESIS DEBUG: Source {i}: title='{src.title[:50]}...' has_content={has_content} content_len={len(src.content) if src.content else 0}")
        
        context_parts = []
        for i, src in enumerate(sources, 1):
            # Include post content (truncated to ~2500 chars to fit context window including comments)
            content_preview = src.content[:2500] if src.content else "[No content available]"
            if len(src.content) > 2500:
                content_preview += "..."
            
            context_parts.append(
                f"{i}. **{src.title}** (r/{src.subreddit})\n"
                f"   - Content: {content_preview}\n"
                f"   - Score: {src.score} | Comments: {src.comments_count}\n"
                f"   - URL: {src.url}"
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
        
        if is_russian:
            system_prompt = """Вы — Аналитик Сообществ, специализирующийся на извлечении практических инсайтов из обсуждений на Reddit.

Ваша задача — проанализировать посты Reddit, связанные с запросом пользователя, и предоставить структурированный анализ:

1. **Проверка реальности**: Баги, edge cases, проблемы с железом/софтом, упомянутые пользователями
2. **Лайфхаки и обходные пути**: Неофициальные решения, креативные фиксы, советы от сообщества
3. **Атмосфера**: Общий сентимент, частые фрустрации, консенсус сообщества

Правила:
- Будьте краткими, но конкретными — ссылайтесь на конкретные посты
- Используйте bullet points для удобства чтения
- Если в категории нет инсайтов, напишите "Ничего конкретного не упомянуто"
- Тон — информативный и нейтральный
- Фокус на практичной, actionable информации
- Упоминайте конкретные сабреддиты
- ОБРАЩАЙТЕ ВНИМАНИЕ НА КОММЕНТАРИИ: Часто решение находится именно там (раздел "TOP COMMENTS")

ВАЖНО: Отвечайте ТОЛЬКО на русском языке, даже если посты Reddit на английском.

Формат ответа — markdown с секциями:

### Проверка реальности
- Упомянутые баги и проблемы
- Edge cases от пользователей
- Проблемы совместимости

### Лайфхаки и обходные пути
- Неофициальные решения
- Советы от сообщества
- Креативные фиксы

### Атмосфера
- Общий сентимент сообщества
- Частые жалобы или похвала
- Консенсус, если есть

### Краткое резюме
- Краткое резюме ключевых выводов (2-3 предложения)"""

            user_prompt = f"""**Запрос пользователя:** {query}

**Найденные посты Reddit:**

{context}

Проанализируйте эти обсуждения на Reddit и извлеките инсайты. Отвечайте на русском языке."""
        else:
            system_prompt = """You are a Community Analyst specializing in extracting actionable insights from Reddit discussions.

Your task is to analyze Reddit posts related to the user's query and provide a structured analysis focusing on:

1. **Reality Check**: Bugs, edge cases, hardware issues, or problems mentioned by users
2. **Hacks & Workarounds**: Unofficial solutions, creative fixes, or community-discovered tips
3. **Vibe Check**: Overall sentiment, common frustrations, and community consensus

Guidelines:
- Be concise but specific - cite specific posts when making claims
- Use bullet points for readability
- If no relevant insights found in a category, say "Nothing specific mentioned"
- Keep tone informative and neutral
- Focus on practical, actionable information
- Mention specific subreddits when relevant
- PAY ATTENTION TO COMMENTS: Often the real solution is in the "TOP COMMENTS" section

Format your response as markdown with these sections:

### Reality Check
- Any bugs or issues mentioned
- Edge cases reported by users
- Hardware/software compatibility problems

### Hacks & Workarounds  
- Unofficial solutions
- Community tips and tricks
- Creative workarounds

### Vibe Check
- Overall community sentiment
- Common frustrations or praise
- Consensus opinion if any

### Summary
- Brief 2-3 sentence summary of key takeaways"""

            user_prompt = f"""**User Query:** {query}

**Reddit Posts Found:**

{context}

Please analyze these Reddit discussions and extract insights."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _create_fallback_response(
        self, 
        reddit_result: RedditSearchResult,
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
        
        if not reddit_result.sources:
            if is_russian:
                return "Обсуждения в сообществе не найдены для этого запроса."
            return "No community discussions found for this query."
        
        if is_russian:
            lines = ["### Обсуждения в сообществе", ""]
            lines.append(f"Найдено {reddit_result.found_count} релевантных постов на Reddit:")
        else:
            lines = ["### Community Discussions", ""]
            lines.append(f"Found {reddit_result.found_count} relevant posts on Reddit:")
        
        lines.append("")
        
        for src in reddit_result.sources[:5]:
            # FIX: Escape markdown special characters to prevent injection/broken formatting
            escaped_title = src.title.replace("[", "\\[").replace("]", "\\]")
            escaped_url = src.url.replace(")", "%29")  # URL-encode closing parenthesis
            lines.append(f"- **[{escaped_title}]({escaped_url})** (r/{src.subreddit})")
            if is_russian:
                lines.append(f"  Рейтинг: {src.score} | Комментариев: {src.comments_count}")
            else:
                lines.append(f"  Score: {src.score} | Comments: {src.comments_count}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def quick_synthesize(
        self,
        query: str,
        reddit_result: RedditSearchResult
    ) -> Dict[str, Any]:
        """Quick synthesis returning structured data.
        
        Args:
            query: User query
            reddit_result: Reddit search result
        
        Returns:
            Dictionary with synthesis text and metadata
        """
        synthesis_text = await self.synthesize(query, reddit_result)
        
        return {
            "synthesis": synthesis_text,
            "sources_count": len(reddit_result.sources),
            "total_found": reddit_result.found_count,
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
