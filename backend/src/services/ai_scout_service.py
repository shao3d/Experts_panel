"""AI Scout Service for Super-Passport Search.

Generates FTS5 MATCH queries from user queries using AI.
Handles Russian-English slang translations and morphological variations.
"""

import json
import logging
import re
from typing import Optional, Tuple
from .vertex_llm_client import get_vertex_llm_client
from ..config import MODEL_SCOUT

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
        # Special characters - must use safe equivalents (FTS5 ignores +, #, .)
        "c++": "cpp OR cplusplus OR \"си плюс плюс\"",
        "с++": "cpp OR cplusplus OR \"си плюс плюс\"",  # Russian 'с'
        "c#": "csharp OR \"си шарп\"",
        "с#": "csharp OR \"си шарп\"",  # Russian 'с'
        "f#": "fsharp OR \"эф шарп\"",
        ".net": "dotnet OR \"дотнет\"",
        "node.js": "nodejs OR \"нода\"",
    }

    def __init__(self, model: str = None):
        """Initialize AI Scout Service.

        Args:
            model: Model to use (default: MODEL_SCOUT)
        """
        self.client = get_vertex_llm_client()
        self.model = model or MODEL_SCOUT
        logger.info(f"AIScoutService initialized with model: {self.model}")

    async def generate_match_query(self, user_query: str) -> Tuple[str, bool]:
        """Generate FTS5 MATCH query from user query.

        Entity-Centric v2: Enforces OR-only queries for maximum recall.

        Args:
            user_query: User's natural language query

        Returns:
            Tuple of (match_query, success)
            match_query: FTS5 MATCH expression or fallback keywords
            success: True if AI generation succeeded, False if fallback used
        """
        try:
            match_query = await self._generate_with_ai(user_query)

            # ═══════════════════════════════════════════════════════════════
            # ENTITY-CENTRIC v2: Force OR-only (replace AND with OR)
            # The model sometimes ignores prompt instructions, so we enforce it
            # ═══════════════════════════════════════════════════════════════
            original_query = match_query
            match_query = self._force_or_only(match_query)

            if match_query != original_query:
                logger.info(f"[AI Scout] Forced OR-only: {original_query[:80]}... → {match_query[:80]}...")

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

    def _force_or_only(self, query: str) -> str:
        """Force OR-only query by replacing AND with OR.

        Entity-Centric v2: AND kills recall, so we replace all AND with OR.
        Map Phase will handle semantic filtering.

        NOTE: This replaces ALL AND operators, including inside quotes.
        Scout v3 prompt prohibits AND entirely, so phrase search with AND
        inside quotes should never occur in practice.
        """
        import re
        # Replace AND (case-insensitive, word boundary) with OR
        result = re.sub(r'\bAND\b', 'OR', query, flags=re.IGNORECASE)
        return result

    async def _generate_with_ai(self, user_query: str) -> str:
        """Generate FTS5 MATCH query using AI."""

        prompt = f"""You are an expert at generating SQLite FTS5 MATCH queries for technical content search.

═══════════════════════════════════════════════════════════════════
ENTITY-CENTRIC SCOUT v3 - ALIGNED WITH METADATA TAXONOMY
═══════════════════════════════════════════════════════════════════

The database you are searching is indexed using a strict taxonomy. Posts are tagged with normalized bilingual keywords.
Your ONLY job: Extract entities and concepts from the user's query and expand them into OR-only synonyms matching this taxonomy.
The Map Phase will handle semantic filtering. MAXIMIZE RECALL.

═══════════════════════════════════════════════════════════════════
ABSOLUTE RULES:
1. OUTPUT MUST BE OR-ONLY, NEVER USE AND.
2. YOU MUST INCLUDE BOTH ENGLISH AND RUSSIAN TRANSLATIONS.
═══════════════════════════════════════════════════════════════════

❌ FORBIDDEN: (term1) AND (term2)
❌ FORBIDDEN: term1 AND term2
✓ REQUIRED: term1 OR term2 OR term3 OR term4

═══════════════════════════════════════════════════════════════════
TAXONOMY ALIGNMENT (HOW POSTS ARE INDEXED):
═══════════════════════════════════════════════════════════════════

1. RAG → rag OR retrieval* OR augmented* OR generation* OR вектор* OR эмбеддинг* OR чанк* OR langchain OR llamaindex OR faiss OR pinecone OR контекст* OR semantic* OR embedding* OR vector* OR chunk*
2. LLM → llm OR "large language model*" OR нейросет* OR модель* OR gpt* OR claude* OR language*
3. Kubernetes → kubernetes OR k8s OR кубер* OR container* OR контейнер* OR pod* OR helm* OR kubectl
4. Database → database* OR баз* OR db OR postgres* OR mysql OR mongo*
5. Special chars (CRITICAL for FTS5):
   - C++ → cpp OR cplusplus OR "си плюс плюс"
   - C# → csharp OR "си шарп"
   - .NET → dotnet OR "дотнет"

═══════════════════════════════════════════════════════════════════
EXAMPLES (STUDY THESE CAREFULLY):
═══════════════════════════════════════════════════════════════════

Query: "как поднять кубер"
Output: kubernetes OR кубер* OR кубернетис OR k8s OR container* OR контейнер* OR pod* OR helm* OR kubectl OR setup OR развертывание OR deploy* OR деплой*

Query: "настройка бд для RAG"
Output: database* OR баз* OR бд OR db OR postgres* OR mysql OR rag OR retrieval* OR вектор* OR эмбеддинг* OR настройка OR setup OR config*

═══════════════════════════════════════════════════════════════════
NOW PROCESS THIS QUERY (REMEMBER: BILINGUAL SYNONYMS, OR-ONLY, NO AND):
═══════════════════════════════════════════════════════════════════

USER QUERY: {user_query}

OUTPUT (OR-only FTS5 query):"""

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

        Entity-Centric v2: OR-only, no AND operators.
        Uses known slang mappings and basic keyword extraction.
        """
        words = user_query.lower().split()
        expanded_terms = []

        for word in words:
            # Skip common stop words (intent/action words - let Map Phase handle semantics)
            if word in ("как", "что", "где", "когда", "зачем", "почему", "и", "или", "в", "на", "с", "для", "по", "a", "an", "the", "is", "are", "to", "how", "сделать", "использовать", "настроить"):
                continue

            # Check for known slang
            found_slang = False
            for ru, en in self.KNOWN_SLANG.items():
                if ru in word or word in ru:
                    # Check if the word itself has special chars - don't add wildcard
                    if any(c in word for c in '+#.'):
                        expanded_terms.append(f"{en}")
                    else:
                        expanded_terms.append(f"{word}*")
                        # Also add the expanded English terms
                        expanded_terms.append(f"{en}")
                    found_slang = True
                    break

            if not found_slang and len(word) >= 3:
                # Add prefix wildcard
                expanded_terms.append(f"{word}*")

        if not expanded_terms:
            # Ultimate fallback: just use original query words
            return " OR ".join(f"{w}*" for w in words if len(w) >= 2)

        # Entity-Centric v2: OR-only, no AND
        return " OR ".join(expanded_terms)

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

        # Protect against FTS5 Syntax Error on special chars (catches C++*, C#*, C+ *)
        if re.search(r'[+#][+#\s]*\*', match_query):
            logger.warning(f"[AI Scout] Invalid wildcard after special char: {match_query}")
            return False

        # Warn about potentially too-simple queries (but still allow them)
        if len(match_query) < 20:
            logger.warning(f"[AI Scout] Generated query may be too simple/short: {match_query}")

        return True
