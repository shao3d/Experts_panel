"""Reddit Synthesis Service - Gemini-powered analysis of Reddit content.

This module provides synthesis of Reddit search results using Google Gemini AI
to extract insights, sentiment, and actionable information from community discussions.
"""

import logging
from typing import Optional, List, Dict, Any

from .. import config
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
            Markdown-formatted synthesis with insights
        """
        if not reddit_result.sources:
            return "No community discussions found for this query."
        
        # Build context from sources
        context = self._build_context(reddit_result, max_sources_in_context)
        
        # Create synthesis prompt
        messages = self._create_synthesis_prompt(query, context)
        
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
            return self._create_fallback_response(reddit_result)
        except Exception as e:
            logger.error(f"Unexpected error in synthesis: {e}")
            return self._create_fallback_response(reddit_result)
    
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
        
        context_parts = []
        for i, src in enumerate(sources, 1):
            context_parts.append(
                f"{i}. **{src.title}** (r/{src.subreddit})\n"
                f"   - Score: {src.score} | Comments: {src.comments_count}\n"
                f"   - URL: {src.url}"
            )
        
        return "\n\n".join(context_parts)
    
    def _create_synthesis_prompt(
        self,
        query: str,
        context: str
    ) -> List[Dict[str, str]]:
        """Create synthesis prompt for Gemini.
        
        Args:
            query: User query
            context: Reddit posts context
        
        Returns:
            Messages list for chat completion
        """
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

Format your response as markdown with these sections:

### 🔍 Reality Check
- Any bugs or issues mentioned
- Edge cases reported by users
- Hardware/software compatibility problems

### 🛠️ Hacks & Workarounds  
- Unofficial solutions
- Community tips and tricks
- Creative workarounds

### 😎 Vibe Check
- Overall community sentiment
- Common frustrations or praise
- Consensus opinion if any

### 📊 Summary
- Brief 2-3 sentence summary of key takeaways"""

        user_prompt = f"""**User Query:** {query}

**Reddit Posts Found:**

{context}

Please analyze these Reddit discussions and extract insights."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _create_fallback_response(self, reddit_result: RedditSearchResult) -> str:
        """Create fallback response when synthesis fails.
        
        Args:
            reddit_result: Reddit search result
        
        Returns:
            Basic markdown response with sources
        """
        if not reddit_result.sources:
            return "No community discussions found for this query."
        
        lines = ["### Community Discussions", ""]
        lines.append(f"Found {reddit_result.found_count} relevant posts on Reddit:")
        lines.append("")
        
        for src in reddit_result.sources[:5]:
            # FIX: Escape markdown special characters to prevent injection/broken formatting
            escaped_title = src.title.replace("[", "\\[").replace("]", "\\]")
            escaped_url = src.url.replace(")", "%29")  # URL-encode closing parenthesis
            lines.append(f"- **[{escaped_title}]({escaped_url})** (r/{src.subreddit})")
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
