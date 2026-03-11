"""AI Scout Service for Super-Passport Search.

Generates FTS5 MATCH queries from user queries using AI.
Handles Russian-English slang translations and morphological variations.
"""

import json
import logging
from typing import Optional, Tuple
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..config import MODEL_ANALYSIS

logger = logging.getLogger(__name__)


class AIScoutService:
    """Service for generating FTS5 MATCH queries using AI.

    Translates user queries into FTS5-compatible search expressions
    that handle:
    - Russian-English technical slang (кубер↔kubernetes)
    - Morphological variations (деплой*, настрой*)
    - Multi-language synonyms
    """

    # Known Russian-English tech slang mappings for fallback
    KNOWN_SLANG = {
        "кубер": "kubernetes OR k8s",
        "куберу": "kubernetes",
        "постгря": "postgresql OR postgres",
        "постгрес": "postgresql OR postgres",
        "эластик": "elasticsearch",
        "редис": "redis",
        "кафка": "kafka",
        "зукпер": "zookeeper",
        "докер": "docker",
        "контейнер": "container",
        "деплой": "deploy OR deployment",
        "раскатка": "deploy OR deployment OR rollout",
        "пайплайн": "pipeline OR ci OR cd",
        "хелм": "helm OR chart",
        "чарт": "helm OR chart",
        "инфра": "infrastructure OR infra",
        "бэкенд": "backend",
        "фронтенд": "frontend",
        "база": "database OR db",
        "бд": "database",
        "нейронка": "neural OR network OR nn",
        "моделька": "model",
        "промпт": "prompt",
        "токен": "token",
        "эмбеддинг": "embedding OR vector",
        "раг": "rag OR retrieval",
        "лм": "lm OR language OR model",
        "бигдат": "bigdata OR big OR data",
        "мл": "ml OR machine OR learning",
        "дата": "data",
    }

    def __init__(self, model: str = None):
        """Initialize AI Scout Service.

        Args:
            model: Model to use (default: MODEL_ANALYSIS)
        """
        self.client = create_google_ai_studio_client()
        self.model = model or MODEL_ANALYSIS
        logger.info(f"AIScoutService initialized with model: {self.model}")

    async def generate_match_query(self, user_query: str) -> Tuple[str, bool]:
        """Generate FTS5 MATCH query from user query.

        Args:
            user_query: User's natural language query

        Returns:
            Tuple of (match_query, success)
            match_query: FTS5 MATCH expression or fallback keywords
            success: True if AI generation succeeded, False if fallback used
        """
        try:
            match_query = await self._generate_with_ai(user_query)

            # Validate the generated query
            if not self.validate_match_query(match_query):
                logger.warning(f"[AI Scout] Generated invalid query, using fallback: {match_query}")
                return self._generate_fallback(user_query), False

            logger.info(f"[AI Scout] Generated MATCH query: {match_query}")
            return match_query, True
        except Exception as e:
            logger.warning(f"[AI Scout] AI generation failed, using fallback: {e}")
            match_query = self._generate_fallback(user_query)
            logger.info(f"[AI Scout] Fallback MATCH query: {match_query}")
            return match_query, False

    async def _generate_with_ai(self, user_query: str) -> str:
        """Generate FTS5 MATCH query using AI."""

        prompt = f"""You are an expert at generating SQLite FTS5 MATCH queries for technical content search.

Given the user query, generate an FTS5 MATCH expression that will find relevant posts.

RULES:
1. Extract ALL keywords from the query (both Russian and English)
2. Add English equivalents for Russian tech slang:
   - кубер → kubernetes, k8s
   - постгр* → postgresql, postgres
   - докер → docker
   - деплой → deploy, deployment
   - раскатка → deploy, rollout
   - пайплайн → pipeline, ci, cd
3. Add Russian equivalents for English terms where applicable
4. Use prefix wildcards (*) for morphological variations
5. Use OR for synonyms, AND for combining concepts
6. Keep it simple - don't over-generate

OUTPUT FORMAT: Return ONLY the FTS5 MATCH string, nothing else.

EXAMPLES:
Query: "как настроить kubernetes"
Output: (kubernetes OR кубер* OR k8s) AND (настрой* OR config*)

Query: "deploy в продакшен"
Output: (deploy* OR деплой* OR раскатка) AND (prod* OR продакшен*)

Query: "postgresql performance tuning"
Output: (postgresql OR postgres OR постгр*) AND (performance OR производитель*) AND (tuning OR настрой*)

USER QUERY: {user_query}
OUTPUT:"""

        response = await self.client.chat_completions_create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )

        match_query = response.choices[0].message.content.strip()

        # Clean up response (remove markdown if present)
        if match_query.startswith("```"):
            lines = match_query.split("\n")
            match_query = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        # Remove any quotes or extra whitespace
        match_query = match_query.strip().strip('"').strip("'")

        return match_query

    def _generate_fallback(self, user_query: str) -> str:
        """Generate simple FTS5 MATCH query as fallback.

        Uses known slang mappings and basic keyword extraction.
        """
        words = user_query.lower().split()
        expanded_terms = []

        for word in words:
            # Skip common stop words
            if word in ("как", "что", "где", "когда", "зачем", "почему", "и", "или", "в", "на", "с", "для", "по", "a", "an", "the", "is", "are", "to", "how"):
                continue

            # Check for known slang
            found_slang = False
            for ru, en in self.KNOWN_SLANG.items():
                if ru in word or word in ru:
                    expanded_terms.append(f"({word}* OR {en})")
                    found_slang = True
                    break

            if not found_slang and len(word) >= 3:
                # Add prefix wildcard
                expanded_terms.append(f"{word}*")

        if not expanded_terms:
            # Ultimate fallback: just use original query words
            return " OR ".join(f"{w}*" for w in words if len(w) >= 2)

        return " AND ".join(expanded_terms)

    def validate_match_query(self, match_query: str) -> bool:
        """Validate FTS5 MATCH query syntax.

        Basic validation to catch obvious errors.
        Returns True if query is valid, False otherwise.
        """
        # Check for empty query
        if not match_query.strip():
            return False

        # Should not contain MATCH keyword (it's added by the SQL query itself)
        if "MATCH" in match_query.upper():
            return False

        # Check for balanced parentheses
        if match_query.count("(") != match_query.count(")"):
            return False

        # Check for balanced quotes
        if match_query.count('"') % 2 != 0:
            return False

        # Warn about potentially too-simple queries (but still allow them)
        if len(match_query) < 20:
            logger.warning(f"[AI Scout] Generated query may be too simple/short: {match_query}")

        return True
