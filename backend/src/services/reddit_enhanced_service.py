"""Enhanced Reddit Service with deep content analysis.

This module provides advanced Reddit aggregation strategies:
1. Parallel searches with different parameters (relevance, hot, new, top)
2. Multi-subreddit targeting for tech/business queries
3. Deep content fetching via get_post_details
4. Comment analysis for top posts
"""

import asyncio
import logging
import re
import json
import math
import html
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime

import httpx

from .. import config
from .reddit_service import RedditServiceError, CircuitBreaker
from .vertex_llm_client import get_vertex_llm_client

logger = logging.getLogger(__name__)

# Configuration
REDDIT_PROXY_URL = config.REDDIT_PROXY_URL
DEFAULT_TIMEOUT = 60.0  # HTTP timeout - enough for sidecar MCP spawn + multi-strategy search
MAX_RETRIES = 3

# Hard recency window (days) applied when the user enables use_recent_only.
# Reddit API only has coarse time buckets, so exact "last N months" is a post-filter.
REDDIT_RECENT_WINDOW_DAYS = 90

# Discovery channels whose candidates arrive snippet-only: no created_utc and
# no engagement signals. They are force-enriched before the AI rerank.
_UNDATED_DISCOVERY_STRATEGIES = {"serp_google_discovery"}

# Model for Subreddit Scouting
# Use the shared config model so Vertex-compatible defaults apply everywhere.
MODEL_SCOUT = config.MODEL_SCOUT

# Tech-related subreddits for targeted searches
# Query Expansions for Technical Terms
# Maps short acronyms to broader search terms including synonyms and related concepts
QUERY_EXPANSIONS = {
    "llm": ['"Large Language Model"', "LLM", "GPT", "Claude", "Llama", "Mistral", "LocalLLaMA", "GGUF", "quantization"],
    "rag": ["RAG", '"Retrieval Augmented Generation"', '"vector database"', "embeddings", "GraphRAG"],
    "tts": ["TTS", '"text to speech"', '"voice synthesis"', "ElevenLabs", "Kokoro"],
    "stt": ["STT", '"speech to text"', '"voice recognition"', "Whisper", "transcription"],
    "mcp": ["MCP", '"Model Context Protocol"', "server"],
    "gpu": ["GPU", "NVIDIA", "CUDA", "VRAM", "hardware", "3090", "4090"],
    "docker": ["Docker", "container", "kubernetes", "k8s", "compose"],
    "python": ["Python", "pip", "PyPI", "script", "asyncio"],
    "rust": ["Rust", "Rustlang", "cargo", "crate"],
    "react": ["React", "ReactJS", "NextJS", "frontend"],
    "arch": ["architecture", "design", "pattern", "trade-off", "latency", "throughput", "production"],
    "biz": ["cost", "pricing", "billing", "margin", "COGS", "economics"],
}

# Pre-compile expansion logic for performance
# 1. Build map: 'llm' -> '(Large Language Model OR LLM ...)'
_EXPANSION_MAP = {k.lower(): f"({' OR '.join(v)})" for k, v in QUERY_EXPANSIONS.items()}

# 2. Build regex pattern once: \b(llm|rag|...)\b
_EXPANSION_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _EXPANSION_MAP.keys()) + r')\b',
    re.IGNORECASE
)

# Constants
MAX_TARGET_SUBREDDITS = 7

# High-Signal Markers for "Title-Only" Strategy
# Used to find structured guides, tutorials, and deep dives
HIGH_SIGNAL_MARKERS = [
    '"Guide"', '"Tutorial"', '"Deep Dive"', '"Analysis"', 
    '"Benchmark"', '"Cheat Sheet"', '"Roadmap"', '"How to"',
    '"Post-Mortem"', '"Lessons Learned"'
]

# Conflict/Solution Markers for "Discussion" Strategy
# Used to find comparisons and solved problems
COMPARISON_MARKERS = [
    "vs", "versus", "comparison", "alternative", 
    "solved", "solution", "fixed", "workaround",
    "switched to", "migrated from", "failed", "regret"
]

# General popular subreddits
POPULAR_SUBREDDITS = [
    "AskReddit",
    "explainlikeimfive",
    "NoStupidQuestions",
    "LifeProTips",
    "personalfinance",
    "investing",
]

COMMON_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "best", "for", "from", "how", "i", "in", "is",
    "it", "my", "of", "on", "or", "the", "to", "vs", "what", "with", "why",
    "workflow", "guide", "setup", "issue", "problem", "help", "using",
}

SOLUTION_MARKERS = [
    "guide", "tutorial", "how to", "step", "fixed", "workaround", "solution",
    "resolved", "benchmark", "comparison", "best practice", "lessons learned",
    "migrated", "switched", "config", "configuration", "settings",
]

DIRECT_COMPARISON_MARKERS = [
    " vs ", "versus", "comparison", "compared", "compare", "alternative",
    "better than", "faster than", "slower than", "overhead", "benchmark",
    "switched", "migrated",
]

PROMOTIONAL_MARKERS = [
    "for hire", "top companies", "best companies", "agency", "services",
    "consulting", "boilerplate", "template", "newsletter", "sponsored",
]

# SEO/affiliate promo title mechanics: credit giveaways, signup bonuses,
# ALL-CAPS FREE. Distinct from hands-on experience posts ("I tested X for a
# month"), which carry none of these patterns.
SPAM_TITLE_PATTERNS = [
    re.compile(r"gives? you \d+", re.I),
    re.compile(r"\d+\s*(free\s+)?credits?\b", re.I),
    re.compile(r"free credits?", re.I),
    re.compile(r"(sign[- ]?up|registration)\s+(bonus|promo|credit|deal)", re.I),
    re.compile(r"promo code|coupon code|lifetime deal|affiliate", re.I),
]
# Subreddit name fragments observed as keyword-stuffed promo hubs.
SPAM_SUBREDDIT_FRAGMENTS = ["seo"]

PRACTITIONER_DISCOVERY_INTENTS = {
    "use_cases",
    "practitioner_examples",
}

# Unambiguous solicitation/job-board patterns. Do not treat "I built ..." as
# spam: first-person build reports are often the best practitioner evidence.
JOB_SOLICITATION_PATTERNS = [
    re.compile(r"\bfor hire\b", re.I),
    re.compile(r"\bhiring\b", re.I),
    re.compile(r"\bopen to (?:work|remote|roles|opportunities)\b", re.I),
    re.compile(r"\blooking for (?:work|clients|a job|roles)\b", re.I),
]

GENERIC_ANCHOR_STOPWORDS = COMMON_QUERY_STOPWORDS | {
    "ai", "production", "system", "systems", "reduce", "improve", "prevent",
    "avoid", "prod", "tool", "tools", "model", "models", "strategy",
    "strategies", "pattern", "patterns", "practice", "practices",
    "performance", "comparison", "benchmark", "latency",
    "reverse", "proxy", "remote", "access", "server", "servers", "setup",
    "output", "outputs", "json", "schema", "schemas", "structured",
    "chunking", "chunk", "chunks", "prompt", "prompts", "hallucination",
    "hallucinations", "deployment", "deployments", "offline", "fix",
    "troubleshooting", "security", "slow", "speed",
}


@dataclass
class RedditPost:
    """Enhanced Reddit post with full content."""
    id: str
    title: str
    url: str
    permalink: str
    score: int
    num_comments: int
    subreddit: str
    author: str
    created_utc: int
    selftext: str = ""
    is_self: bool = False
    is_technical_guide: bool = False
    found_by_strategy: Optional[str] = None
    strategy_hits: List[str] = field(default_factory=list)
    heuristic_score: float = 0.0
    anchor_matches: int = 0
    title_anchor_matches: int = 0
    body_anchor_matches: int = 0
    comment_anchor_matches: int = 0
    title_body_anchor_matches: int = 0
    direct_comparison_hits: int = 0
    ai_score: float = 0.0
    final_score: float = 0.0
    ranking_reason: str = ""
    # Enriched data
    full_content: Optional[str] = None
    top_comments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EnhancedSearchResult:
    """Result from enhanced Reddit search."""
    posts: List[RedditPost]
    total_found: int
    query: str
    strategies_used: List[str]
    processing_time_ms: int
    debug_trace: Dict[str, Any] = field(default_factory=dict)


class RedditEnhancedService:
    """Enhanced Reddit service with parallel searches and deep analysis.
    
    Features:
    - Parallel searches with different sort parameters
    - Multi-subreddit targeting
    - Deep content fetching for top posts
    - Comment analysis
    - Deduplication across sources
    """
    
    def __init__(
        self,
        base_url: str = REDDIT_PROXY_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._circuit_breaker = CircuitBreaker()
        self._client: Optional[httpx.AsyncClient] = None
        self._llm_client = get_vertex_llm_client()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _expand_query(self, query: str) -> str:
        """Expand query with technical synonyms to improve recall.
        
        Uses pre-compiled single-pass regex replacement.
        Example: "best LLM" -> "best (LLM OR "Large Language Model" OR GPT ...)"
        """
        # Avoid double expansion if query already contains OR/AND
        if " OR " in query or " AND " in query:
            return query
            
        def replace_callback(match):
            word = match.group(0).lower()
            return _EXPANSION_MAP.get(word, match.group(0))

        # Perform single-pass substitution using global pre-compiled pattern
        return _EXPANSION_PATTERN.sub(replace_callback, query)
    
    async def _plan_search_strategy(
        self,
        query: str,
        *,
        original_user_query: Optional[str] = None,
        user_intent: Optional[str] = None,
        must_keep_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Use Gemini 3 Flash to create a search plan (Subreddits + Intent-based Queries).
        
        Returns:
            Dict with keys:
            - 'subreddits': List[str]
            - 'queries': List[str]
            - 'keywords': List[str]
            - 'time_filter': str ('month' | 'year' | 'all')
            - 'intent': str ('how_to' | 'comparison' | 'troubleshooting' | 'news' | 'discussion')
        """
        try:
            prompt = f"""You are an expert Reddit OSINT Navigator.
Reddit Search Query: "{query}"
Original User Question: "{original_user_query or query}"
Preferred Intent: "{user_intent or 'infer from the question'}"
Must-Keep Meaning Anchors: {must_keep_terms or ["none"]}

Task: Create a precise Search Plan.
1. Identify 3-7 relevant technical subreddits.
2. Generate 3-5 SPECIFIC search queries.
3. Extract 2-3 CRITICAL keywords.
4. Assess Temporal Context:
   - Is this a fast-moving topic (AI, News, Bugs)? -> "month" or "year"
   - Is this evergreen (Concepts, Algorithms)? -> "all"
5. Classify Intent: how_to, comparison, troubleshooting, news, discussion,
   recommendation, use_cases, or practitioner_examples. Preserve Preferred
   Intent when it fits the Original User Question.
6. Search queries must be plain Reddit keywords only.
7. DO NOT use web-search syntax like site:, subreddit:, r/, quotes, or boolean operators.
8. Every search query must preserve the must-keep meaning anchors where they
   materially distinguish relevant posts. For practitioner_examples/use_cases,
   search for concrete things people built, custom features, commands,
   shortcuts, and automations rather than generic architecture or latency.

Output JSON structure:
{{
  "subreddits": ["LocalLLaMA", "ClaudeAI"],
  "queries": ["Claude Code workflow", "Claude setup"],
  "keywords": ["Skills", "CLI"],
  "time_filter": "month",
  "intent": "how_to"
}}
"""
            # Use Gemini 3 Flash Preview for high-intelligence scouting
            response = await self._llm_client.chat_completions_create(
                model=MODEL_SCOUT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0  # Deterministic: stable plans across runs
            )
            
            content = response.choices[0].message.content.strip()
            
            # Robust JSON extraction
            try:
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]
                    plan = json.loads(json_str)
                else:
                    logger.warning(f"Gemini Scout returned no JSON object: {content[:100]}...")
                    return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini Scout JSON parse error: {e}. Content: {content[:100]}...")
                return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
            
            # Validation and Sanitization
            valid_subs = []
            raw_subs = plan.get("subreddits", [])
            if isinstance(raw_subs, list):
                for s in raw_subs:
                    if isinstance(s, str) and len(s) > 1:
                        # Clean up 'r/' prefix if present
                        clean_name = s.strip().replace('r/', '').replace('/r/', '')
                        # Reddit names are alphanumeric + underscore
                        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name)
                        if clean_name:
                            valid_subs.append(clean_name)
            
            valid_queries = []
            raw_queries = plan.get("queries", [])
            if isinstance(raw_queries, list):
                for q in raw_queries:
                    if not isinstance(q, str):
                        continue
                    cleaned_query = self._sanitize_scout_query(q)
                    if len(cleaned_query) > 3:
                        valid_queries.append(cleaned_query)

            valid_keywords = []
            raw_keywords = plan.get("keywords", [])
            if isinstance(raw_keywords, list):
                for keyword in raw_keywords:
                    if not isinstance(keyword, str):
                        continue
                    cleaned_keyword = self._sanitize_scout_query(keyword)
                    if len(cleaned_keyword) > 2:
                        valid_keywords.append(cleaned_keyword)
                
            time_filter = plan.get("time_filter", "all")
            if time_filter not in ["hour", "day", "week", "month", "year", "all"]:
                time_filter = "all"
                
            intent = plan.get("intent", "discussion")

            result = {
                "subreddits": valid_subs, 
                "queries": valid_queries, 
                "keywords": valid_keywords,
                "time_filter": time_filter,
                "intent": intent
            }
            
            if valid_subs or valid_queries:
                logger.info(f"🤖 Gemini Scout Plan for '{query}': {result}")
            
            return result
            
        except Exception as e:
            logger.warning(f"Gemini Scout failed: {e}. Falling back to global search.")
            return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}

    def _log_debug_trace(self, label: str, trace: Dict[str, Any]) -> None:
        """Emit structured Reddit trace only when explicitly enabled."""
        if not config.REDDIT_SEARCH_DEBUG:
            return

        try:
            payload = json.dumps(trace, ensure_ascii=False, default=str)
        except Exception:
            payload = str(trace)

        if len(payload) > 4000:
            payload = payload[:4000] + "...<truncated>"
        logger.info("REDDIT TRACE %s: %s", label, payload)

    def _tokenize_query_terms(
        self, query: str, extra_terms: Optional[List[str]] = None
    ) -> List[str]:
        """Extract significant lexical terms used for answerability scoring."""
        terms: List[str] = []
        seen: Set[str] = set()

        raw_tokens = re.findall(r"[A-Za-z0-9_+.#-]{2,}", query.lower())
        if extra_terms:
            raw_tokens.extend(
                token
                for term in extra_terms
                for token in re.findall(r"[A-Za-z0-9_+.#-]{2,}", term.lower())
            )

        for token in raw_tokens:
            cleaned = token.strip("\"'()[]{}.,:;!?")
            if len(cleaned) < 2 or cleaned in COMMON_QUERY_STOPWORDS:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                terms.append(cleaned)

        return terms

    def _extract_anchor_terms(self, query: str) -> List[str]:
        """Extract semantically specific anchor terms from the literal user query."""
        anchors: List[str] = []
        seen: Set[str] = set()

        for token in re.findall(r"[A-Za-z0-9_+.#-]{2,}", query.lower()):
            cleaned = token.strip("\"'()[]{}.,:;!?")
            if len(cleaned) < 3 or cleaned in GENERIC_ANCHOR_STOPWORDS:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                anchors.append(cleaned)

        return anchors

    def _sanitize_scout_query(self, query: str) -> str:
        """Remove web-search syntax from LLM-generated scout queries."""
        cleaned = query.strip()
        cleaned = re.sub(r"site:[^\s]+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"subreddit:[A-Za-z0-9_]+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"/?r/[A-Za-z0-9_]+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace('"', " ").replace("'", " ")
        cleaned = re.sub(r"\b(AND|OR|NOT)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")
        return cleaned

    def _select_soft_target_subreddits(
        self,
        suggested_subreddits: List[str],
        anchor_terms: List[str],
        query_terms: List[str],
        limit: int = 2,
    ) -> List[str]:
        """Pick a tiny set of high-signal subreddit hints without returning to strict mode."""
        if not suggested_subreddits:
            return []

        ranked: List[Any] = []
        anchor_set = {term.lower() for term in anchor_terms}
        query_set = {term.lower() for term in query_terms}

        for idx, subreddit in enumerate(suggested_subreddits):
            cleaned = subreddit.strip()
            lowered = cleaned.lower()
            if not cleaned:
                continue

            score = 0
            if lowered in anchor_set:
                score += 5
            if lowered in query_set:
                score += 3
            if lowered not in {s.lower() for s in POPULAR_SUBREDDITS}:
                score += 1
            if len(cleaned) <= 16:
                score += 1

            ranked.append((score, idx, cleaned))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [subreddit for _, _, subreddit in ranked[:limit]]

    def _extract_comment_snippets(
        self, post: RedditPost, limit: int = 2, per_comment_chars: int = 220
    ) -> List[str]:
        """Return short high-signal comment previews for ranking."""
        snippets: List[str] = []
        for comment in post.top_comments[:limit]:
            if not isinstance(comment, dict):
                continue
            body = (comment.get("body") or "").strip()
            if not body:
                continue
            author = comment.get("author") or "unknown"
            compact = re.sub(r"\s+", " ", body)
            if len(compact) > per_comment_chars:
                compact = compact[:per_comment_chars].rstrip() + "..."
            snippets.append(f"{author}: {compact}")
        return snippets

    def _score_post_v2(
        self,
        post: RedditPost,
        query_terms: List[str],
        anchor_terms: List[str],
        target_keywords: List[str],
        intent: str,
    ) -> float:
        """Precision-first heuristic score before the LLM reranker."""
        title_lower = (post.title or "").lower()
        body_lower = (post.selftext or post.full_content or "").lower()
        comments_lower = " ".join(
            snippet.lower() for snippet in self._extract_comment_snippets(post, limit=3)
        )
        combined_lower = " ".join(part for part in [title_lower, body_lower, comments_lower] if part)

        if not combined_lower.strip():
            return 0.0

        title_matches = sum(1 for term in query_terms if term in title_lower)
        body_matches = sum(1 for term in query_terms if term in body_lower)
        comment_matches = sum(1 for term in query_terms if term in comments_lower)
        total_terms = max(len(query_terms), 1)

        title_anchor_matches = sum(1 for term in anchor_terms if term in title_lower)
        body_anchor_matches = sum(1 for term in anchor_terms if term in body_lower)
        comment_anchor_matches = sum(1 for term in anchor_terms if term in comments_lower)
        title_body_anchor_matches = sum(
            1 for term in anchor_terms if term in title_lower or term in body_lower
        )
        direct_comparison_hits = sum(
            1 for marker in DIRECT_COMPARISON_MARKERS if marker in f" {title_lower} {body_lower} "
        )
        post.title_anchor_matches = title_anchor_matches
        post.body_anchor_matches = body_anchor_matches
        post.comment_anchor_matches = comment_anchor_matches
        post.title_body_anchor_matches = title_body_anchor_matches
        post.direct_comparison_hits = direct_comparison_hits

        lexical_score = min(
            ((title_matches * 0.65) + (body_matches * 0.30) + (comment_matches * 0.15))
            / total_terms,
            1.0,
        )

        keyword_matches = 0
        for keyword in target_keywords:
            lowered = keyword.lower()
            if lowered and lowered not in COMMON_QUERY_STOPWORDS and lowered in combined_lower:
                keyword_matches += 1
        keyword_bonus = min(keyword_matches * 0.08, 0.24)

        answerability = 0.0
        if post.is_technical_guide:
            answerability += 0.10
        if any(marker in combined_lower for marker in SOLUTION_MARKERS):
            answerability += 0.10
        if intent in {"how_to", "troubleshooting"} and any(
            marker in combined_lower
            for marker in [
                "fix", "fixed", "workaround", "resolved", "steps", "config", "setup",
                "solution", "error", "issue",
            ]
        ):
            answerability += 0.18
        if intent == "comparison":
            # NB: bonuses are NOT gated on engagement — fresh quality posts
            # legitimately start with few comments. Starvation is passed as an
            # explicit Engagement signal to the AI reranker, which judges
            # whether a low-attention "vs" thread is bait or just new.
            if direct_comparison_hits > 0:
                answerability += 0.16
            if title_body_anchor_matches >= 2:
                answerability += 0.18
            elif title_anchor_matches >= 2:
                answerability += 0.24
        if intent == "discussion" and post.num_comments >= 10:
            answerability += 0.05
        if intent in PRACTITIONER_DISCOVERY_INTENTS:
            if any(
                marker in combined_lower
                for marker in [
                    "i built", "i made", "my setup", "my workflow",
                    "use case", "custom command", "shortcut", "automation",
                ]
            ):
                answerability += 0.12
            if post.top_comments:
                answerability += 0.05
        if post.top_comments:
            answerability += 0.07

        quality_signal = min(math.log1p(max(post.score, 0)) / 8.0, 0.18)
        quality_signal += min(math.log1p(max(post.num_comments, 0)) / 10.0, 0.10)

        penalty = 0.0
        anchor_matches = sum(1 for term in anchor_terms if term in combined_lower)
        post.anchor_matches = anchor_matches
        if anchor_terms:
            if anchor_matches == 0:
                penalty += 0.28
            elif anchor_matches == 1 and len(anchor_terms) >= 2:
                penalty += 0.10
        if intent == "comparison" and len(anchor_terms) >= 2:
            if title_body_anchor_matches == 0 and comment_anchor_matches >= 2:
                penalty += 0.34
            elif title_body_anchor_matches == 1:
                penalty += 0.12
            if direct_comparison_hits == 0:
                penalty += 0.16
            if title_anchor_matches == 0 and post.num_comments >= 20:
                penalty += 0.08
        if any(marker in title_lower for marker in PROMOTIONAL_MARKERS):
            penalty += 0.35
        if intent in PRACTITIONER_DISCOVERY_INTENTS and any(
            pattern.search(title_lower) for pattern in JOB_SOLICITATION_PATTERNS
        ):
            penalty += 0.75
        if "showcase" in title_lower and intent in {"how_to", "troubleshooting"}:
            penalty += 0.10
        if post.score <= 1 and post.num_comments <= 2 and len(body_lower) < 120:
            penalty += 0.12

        # Anti-spam: SEO/affiliate posts stuff titles with query keywords
        # ("Gives You 50 Free Credits") and carry no community validation.
        # Base penalty scales with pattern hits; the engagement-starved combo
        # (low score + no discussion) is near-certain ad and sinks hard.
        spam_hits = sum(
            1 for pattern in SPAM_TITLE_PATTERNS if pattern.search(title_lower)
        )
        if spam_hits:
            penalty += 0.15 * min(spam_hits, 2)
            if post.score <= 3 and post.num_comments <= 5:
                penalty += 0.18
        sub_lower = (post.subreddit or "").lower()
        if any(frag in sub_lower for frag in SPAM_SUBREDDIT_FRAGMENTS):
            penalty += 0.20

        raw_score = (lexical_score * 0.58) + keyword_bonus + answerability + quality_signal - penalty
        return max(0.0, min(raw_score, 1.4))

    def _build_search_tasks_v2(
        self,
        original_query: str,
        expanded_query: str,
        search_plan: Dict[str, Any],
        subreddits: Optional[List[str]],
        anchor_terms: Optional[List[str]] = None,
    ) -> (List[Any], Dict[str, Any]):
        """Create a small, high-recall candidate set without over-constraining Reddit."""
        intent = search_plan.get("intent", "discussion")
        scout_time_filter = search_plan.get("time_filter", "all")
        targeted_subs = [s.strip() for s in (subreddits or [])[:MAX_TARGET_SUBREDDITS] if s.strip()]
        anchor_terms = anchor_terms or []
        scout_queries = [
            q.strip() for q in search_plan.get("queries", []) if isinstance(q, str) and q.strip()
        ]

        sort_tasks: List[Any] = []
        strategy_meta: Dict[str, Any] = {}
        seen_signatures: Set[Any] = set()

        def add_strategy(
            name: str,
            query: str,
            *,
            sort: str,
            time: str,
            limit: int = 25,
            strategy_subreddits: Optional[List[str]] = None,
        ) -> None:
            clean_query = query.strip()
            if not clean_query:
                return

            signature = (
                clean_query.lower(),
                sort,
                time,
                tuple(strategy_subreddits or []),
            )
            if signature in seen_signatures:
                return

            seen_signatures.add(signature)
            strategy_meta[name] = {
                "query": clean_query,
                "sort": sort,
                "time": time,
                "subreddits": strategy_subreddits or [],
            }
            sort_tasks.append(
                (
                    name,
                    self._search_with_sort(
                        clean_query,
                        sort=sort,
                        limit=limit,
                        time=time,
                        subreddits=strategy_subreddits,
                    ),
                )
            )

        add_strategy(
            "literal_global_relevance",
            original_query,
            sort="relevance",
            time=scout_time_filter,
            limit=25,
        )

        if expanded_query != original_query:
            add_strategy(
                "expanded_global_relevance",
                expanded_query,
                sort="relevance",
                time=scout_time_filter,
                limit=20,
            )

        if scout_queries:
            add_strategy(
                "scout_global_relevance",
                scout_queries[0],
                sort="relevance",
                time=scout_time_filter,
                limit=20,
            )

        if targeted_subs:
            add_strategy(
                "targeted_literal_relevance",
                original_query,
                sort="relevance",
                time=scout_time_filter,
                limit=20,
                strategy_subreddits=targeted_subs,
            )

            if scout_queries:
                add_strategy(
                    "targeted_scout_relevance",
                    scout_queries[0],
                    sort="relevance",
                    time=scout_time_filter,
                    limit=18,
                    strategy_subreddits=targeted_subs,
                )

        # Recency/quality sorts (top/new): Reddit only applies the query seriously
        # with sort=relevance; global top/new drift into popular/fresh noise.
        # Restrict them to targeted subreddits where they add value.
        if intent in {"troubleshooting", "news"}:
            if targeted_subs:
                add_strategy(
                    "fresh_targeted_new",
                    original_query,
                    sort="new",
                    time="month",
                    limit=18,
                    strategy_subreddits=targeted_subs,
                )
        elif targeted_subs:
            add_strategy(
                "quality_targeted_top",
                original_query,
                sort="top",
                time="year",
                limit=18,
                strategy_subreddits=targeted_subs,
            )

        if intent == "comparison":
            if len(anchor_terms) >= 2:
                anchor_pair_query = f"{anchor_terms[0]} {anchor_terms[1]} benchmark"
                add_strategy(
                    "comparison_anchor_relevance",
                    anchor_pair_query,
                    sort="relevance",
                    time="year",
                    limit=18,
                )

            comparison_query = next(
                (
                    q
                    for q in scout_queries
                    if any(marker in q.lower() for marker in [" vs ", "versus", "comparison", "alternative"])
                ),
                None,
            )
            if comparison_query:
                add_strategy(
                    "comparison_global",
                    comparison_query,
                    sort="relevance",
                    time="year",
                    limit=18,
                )

        return sort_tasks, strategy_meta

    def _apply_confidence_threshold(
        self,
        posts: List[RedditPost],
        target_posts: int,
        require_anchor_match: bool = False,
        intent: str = "discussion",
    ) -> List[RedditPost]:
        """Prefer abstaining over returning noisy Reddit results."""
        def is_allowed(post: RedditPost, threshold: float) -> bool:
            if post.final_score < threshold:
                return False
            if intent in PRACTITIONER_DISCOVERY_INTENTS and any(
                pattern.search(post.title or "")
                for pattern in JOB_SOLICITATION_PATTERNS
            ):
                return False
            if require_anchor_match and post.anchor_matches == 0:
                return False
            if intent == "comparison":
                if post.title_body_anchor_matches == 0:
                    return False
                if threshold >= config.REDDIT_MIN_CONFIDENCE:
                    if post.anchor_matches >= 2 and post.direct_comparison_hits == 0:
                        return False
            return True

        strict = [
            post for post in posts if is_allowed(post, config.REDDIT_MIN_CONFIDENCE)
        ]
        if strict:
            return strict[:target_posts]

        soft = [
            post for post in posts if is_allowed(post, config.REDDIT_SOFT_CONFIDENCE)
        ]
        if soft:
            return soft[: min(target_posts, 4)]

        return []

    async def _search_enhanced_v2(
        self,
        query: str,
        target_posts: int = 25,
        include_comments: bool = True,
        subreddits: Optional[List[str]] = None,
        recent_only: bool = False,
        original_user_query: Optional[str] = None,
        user_intent: Optional[str] = None,
        must_keep_terms: Optional[List[str]] = None,
    ) -> EnhancedSearchResult:
        """Precision-first Reddit retrieval with softer subreddit hints and richer rerank context."""
        start_time = datetime.utcnow()
        strategies_used: List[str] = []
        all_posts: Dict[str, RedditPost] = {}
        debug_trace: Dict[str, Any] = {
            "version": "v2",
            "original_query": query,
            "strategy_results": {},
        }

        original_query = query.strip()
        expanded_query = self._expand_query(original_query)
        explicit_subreddit_filter = subreddits is not None
        search_plan = {
            "subreddits": [],
            "queries": [],
            "keywords": [],
            "time_filter": "all",
            "intent": "discussion",
        }

        if subreddits is None:
            search_plan = await self._plan_search_strategy(
                original_query,
                original_user_query=original_user_query,
                user_intent=user_intent,
                must_keep_terms=must_keep_terms,
            )
            subreddits = search_plan.get("subreddits", [])

        if user_intent:
            search_plan["intent"] = user_intent

        # Recency mandate: widen retrieval recall (never narrower than a year)
        # and enforce the exact window via the created_utc post-filter below.
        if recent_only and search_plan.get("time_filter", "all") == "all":
            search_plan["time_filter"] = "year"
            debug_trace["recent_only_time_bump"] = True

        target_keywords = search_plan.get("keywords", [])
        anchor_terms = self._extract_anchor_terms(original_query)
        for term in must_keep_terms or []:
            cleaned = self._sanitize_scout_query(term).lower()
            if cleaned and cleaned not in anchor_terms:
                anchor_terms.append(cleaned)
        query_terms = self._tokenize_query_terms(
            original_query,
            extra_terms=target_keywords,
        )

        debug_trace["expanded_query"] = expanded_query
        debug_trace["search_plan"] = search_plan
        debug_trace["scout_subreddits"] = subreddits or []
        debug_trace["query_terms"] = query_terms
        debug_trace["anchor_terms"] = anchor_terms

        soft_target_subreddits: Optional[List[str]] = None
        if not explicit_subreddit_filter and search_plan.get("intent") in {
            "how_to",
            "troubleshooting",
            "comparison",
            "recommendation",
            "use_cases",
            "practitioner_examples",
        }:
            soft_target_subreddits = self._select_soft_target_subreddits(
                subreddits or [],
                anchor_terms=anchor_terms,
                query_terms=query_terms,
            )
        elif explicit_subreddit_filter:
            soft_target_subreddits = subreddits

        debug_trace["soft_target_subreddits"] = soft_target_subreddits or []

        sort_tasks, strategy_meta = self._build_search_tasks_v2(
            original_query,
            expanded_query,
            search_plan,
            soft_target_subreddits,
            anchor_terms=anchor_terms,
        )

        # Google SERP discovery via Serper.dev (site:reddit.com).
        if config.SERPER_API_KEY:
            strategy_meta["serp_google_discovery"] = {
                "query": original_query,
                "source": "serper",
            }
            sort_tasks.append(
                (
                    "serp_google_discovery",
                    self._search_serper(original_query, recent_only=recent_only),
                )
            )
        else:
            debug_trace["serp_google_discovery"] = "disabled (SERPER_API_KEY not set)"

        # Exhaustive archive recall within scout-suggested subreddits.
        if config.ARCTIC_SHIFT_ENABLED and soft_target_subreddits:
            strategy_meta["arctic_targeted_archive"] = {
                "query": original_query,
                "source": "arctic_shift",
                "subreddits": soft_target_subreddits[: config.ARCTIC_TARGET_SUBREDDITS],
            }
            sort_tasks.append(
                (
                    "arctic_targeted_archive",
                    self._search_arctic_shift(
                        original_query,
                        soft_target_subreddits,
                        recent_only=recent_only,
                    ),
                )
            )

        results = await asyncio.gather(
            *[task for _, task in sort_tasks],
            return_exceptions=True,
        )

        for (strategy_name, _), result in zip(sort_tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Strategy {strategy_name} failed: {result}")
                debug_trace["strategy_results"][strategy_name] = {
                    **strategy_meta.get(strategy_name, {}),
                    "error": str(result),
                    "count": 0,
                }
                continue

            strategies_used.append(strategy_name)
            debug_trace["strategy_results"][strategy_name] = {
                **strategy_meta.get(strategy_name, {}),
                "count": len(result),
            }

            for post in result:
                existing = all_posts.get(post.id)
                if existing is None:
                    post.found_by_strategy = strategy_name
                    post.strategy_hits = [strategy_name]
                    all_posts[post.id] = post
                    continue

                existing.score = max(existing.score, post.score)
                existing.num_comments = max(existing.num_comments, post.num_comments)
                if len(post.selftext or "") > len(existing.selftext or ""):
                    existing.selftext = post.selftext
                if post.top_comments and not existing.top_comments:
                    existing.top_comments = post.top_comments
                if strategy_name not in existing.strategy_hits:
                    existing.strategy_hits.append(strategy_name)

        if not all_posts:
            logger.warning("V2 search found no posts, trying one final broad fallback")
            try:
                fallback_posts = await self._search_with_sort(
                    original_query,
                    sort="top",
                    limit=20,
                    time="year",
                )
                for post in fallback_posts:
                    post.found_by_strategy = "fallback_top_year"
                    post.strategy_hits = ["fallback_top_year"]
                    all_posts[post.id] = post
                if fallback_posts:
                    strategies_used.append("fallback_top_year")
                    debug_trace["strategy_results"]["fallback_top_year"] = {
                        "query": original_query,
                        "sort": "top",
                        "time": "year",
                        "subreddits": [],
                        "count": len(fallback_posts),
                    }
            except Exception as e:
                logger.error(f"Fallback Reddit search failed: {e}")

        unique_posts = self._deduplicate_posts(list(all_posts.values()))

        if recent_only:
            cutoff_ts = datetime.utcnow().timestamp() - REDDIT_RECENT_WINDOW_DAYS * 86400
            before_count = len(unique_posts)

            def _is_fresh(p: RedditPost) -> bool:
                if (p.created_utc or 0) >= cutoff_ts:
                    return True
                # Serper candidates carry no created_utc; no exact window
                # exists Google-side. Accepted trade-off for Google ranking.
                return p.found_by_strategy == "serp_google_discovery"

            kept_ids = {p.id for p in unique_posts if _is_fresh(p)}
            # Drop from the list AND from all_posts: the post-enrichment step
            # rebuilds unique_posts from all_posts and would resurrect old posts.
            unique_posts = [p for p in unique_posts if p.id in kept_ids]
            for stale_id in list(all_posts.keys()):
                if stale_id not in kept_ids:
                    del all_posts[stale_id]
            debug_trace["recent_only_filter"] = {
                "window_days": REDDIT_RECENT_WINDOW_DAYS,
                "before": before_count,
                "after": len(unique_posts),
            }
            logger.info(
                f"REDDIT recent_only: kept {len(unique_posts)}/{before_count} posts "
                f"within {REDDIT_RECENT_WINDOW_DAYS}d window"
            )

        for post in unique_posts:
            post.heuristic_score = self._score_post_v2(
                post,
                query_terms=query_terms,
                anchor_terms=anchor_terms,
                target_keywords=target_keywords,
                intent=search_plan.get("intent", "discussion"),
            )

        heuristic_sorted = sorted(
            unique_posts,
            key=lambda p: p.heuristic_score,
            reverse=True,
        )

        # Fair enrichment: snippet-only discovery candidates (Serper/CSE)
        # arrive without engagement signals, so heuristic ranking alone would
        # starve them of full content + comments before the AI rerank —
        # they are force-added to the enrichment set beyond the heuristic cut.
        enrich_targets = heuristic_sorted[
            : min(config.REDDIT_PRE_RERANK_ENRICH_LIMIT, len(heuristic_sorted))
        ]
        seen_target_ids = {p.id for p in enrich_targets}
        for post in heuristic_sorted:
            if len(enrich_targets) >= config.REDDIT_RERANK_CANDIDATES * 2:
                break  # hard safety cap on /details calls
            if post.id in seen_target_ids:
                continue
            if post.found_by_strategy in _UNDATED_DISCOVERY_STRATEGIES:
                enrich_targets.append(post)
                seen_target_ids.add(post.id)

        if include_comments and enrich_targets:
            enriched_results = await asyncio.gather(
                *[self._enrich_post_content(post) for post in enrich_targets],
                return_exceptions=True,
            )

            for idx, result in enumerate(enriched_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed early enrichment for post {enrich_targets[idx].id}: {result}"
                    )
                    continue
                all_posts[result.id] = result

            unique_posts = self._deduplicate_posts(list(all_posts.values()))
            for post in unique_posts:
                post.heuristic_score = self._score_post_v2(
                    post,
                    query_terms=query_terms,
                    anchor_terms=anchor_terms,
                    target_keywords=target_keywords,
                    intent=search_plan.get("intent", "discussion"),
                )
            heuristic_sorted = sorted(
                unique_posts,
                key=lambda p: p.heuristic_score,
                reverse=True,
            )

        candidates_for_rerank = heuristic_sorted[: config.REDDIT_RERANK_CANDIDATES]
        remaining_posts = heuristic_sorted[config.REDDIT_RERANK_CANDIDATES :]

        if candidates_for_rerank:
            try:
                reranked_candidates = await self._ai_rerank_posts(
                    original_query,
                    candidates_for_rerank,
                    intent=search_plan.get("intent", "discussion"),
                    anchor_terms=anchor_terms,
                    original_user_query=original_user_query,
                    must_keep_terms=must_keep_terms,
                )
            except Exception as e:
                logger.error(f"AI reranking failed in V2: {e}")
                reranked_candidates = candidates_for_rerank
        else:
            reranked_candidates = []

        reranked_ids = {post.id for post in reranked_candidates}
        final_sorted = reranked_candidates + [
            post for post in remaining_posts if post.id not in reranked_ids
        ]

        selected_posts = self._apply_confidence_threshold(
            final_sorted,
            target_posts,
            require_anchor_match=bool(anchor_terms),
            intent=search_plan.get("intent", "discussion"),
        )

        if include_comments and selected_posts:
            selected_by_id = {post.id for post in selected_posts}
            missing_context = [
                post
                for post in selected_posts
                if not post.top_comments and post.id in selected_by_id
            ]
            if missing_context:
                enriched_results = await asyncio.gather(
                    *[self._enrich_post_content(post) for post in missing_context],
                    return_exceptions=True,
                )
                for idx, result in enumerate(enriched_results):
                    if isinstance(result, Exception):
                        logger.warning(
                            f"Failed final enrichment for post {missing_context[idx].id}: {result}"
                        )
                        continue
                    for selected_idx, selected in enumerate(selected_posts):
                        if selected.id == result.id:
                            selected_posts[selected_idx] = result
                            break

        debug_trace["unique_posts"] = len(unique_posts)
        debug_trace["selected_posts"] = len(selected_posts)
        debug_trace["pre_rank"] = [
            {
                "id": post.id,
                "title": post.title[:120],
                "heuristic_score": round(post.heuristic_score, 3),
                "anchor_matches": post.anchor_matches,
                "title_body_anchor_matches": post.title_body_anchor_matches,
                "comment_anchor_matches": post.comment_anchor_matches,
                "direct_comparison_hits": post.direct_comparison_hits,
                "strategy_hits": post.strategy_hits,
            }
            for post in heuristic_sorted[:10]
        ]
        debug_trace["post_rank"] = [
            {
                "id": post.id,
                "title": post.title[:120],
                "ai_score": round(post.ai_score, 3),
                "final_score": round(post.final_score, 3),
                "anchor_matches": post.anchor_matches,
                "title_body_anchor_matches": post.title_body_anchor_matches,
                "comment_anchor_matches": post.comment_anchor_matches,
                "direct_comparison_hits": post.direct_comparison_hits,
                "reason": post.ranking_reason,
            }
            for post in final_sorted[:10]
        ]
        self._log_debug_trace("reddit_search_v2", debug_trace)

        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        return EnhancedSearchResult(
            posts=selected_posts,
            total_found=len(unique_posts),
            query=query,
            strategies_used=strategies_used,
            processing_time_ms=processing_time_ms,
            debug_trace=debug_trace,
        )
    
    async def search_enhanced(
        self,
        query: str,
        target_posts: int = 25,
        include_comments: bool = True,
        subreddits: Optional[List[str]] = None,
        recent_only: bool = False,
        original_user_query: Optional[str] = None,
        user_intent: Optional[str] = None,
        must_keep_terms: Optional[List[str]] = None,
    ) -> EnhancedSearchResult:
        """Execute enhanced Reddit search with multiple strategies.

        Args:
            query: Search query
            target_posts: Target number of unique posts to return
            include_comments: Whether to fetch top comments for best posts
            subreddits: Optional list of specific subreddits to search
            recent_only: Hard-filter results to the last REDDIT_RECENT_WINDOW_DAYS days

        Returns:
            EnhancedSearchResult with posts from multiple search strategies
        """
        return await self._search_enhanced_v2(
            query=query,
            target_posts=target_posts,
            include_comments=include_comments,
            subreddits=subreddits,
            recent_only=recent_only,
            original_user_query=original_user_query,
            user_intent=user_intent,
            must_keep_terms=must_keep_terms,
        )

    def _deduplicate_posts(self, posts: List[RedditPost]) -> List[RedditPost]:
        """Deduplicate posts based on URL and fuzzy title match."""
        unique = []
        seen_urls = set()
        seen_titles = set()
        seen_signatures = set()
        
        # Helper to normalize URL (remove query params, trailing slash)
        def normalize_url(url: str) -> str:
            if not url: return ""
            u = url.split('?')[0].rstrip('/')
            return u
            
        # Helper to normalize title (simple alphanum sort)
        def normalize_title(title: str) -> str:
            # "How to fix X?" -> "howtofixx"
            return re.sub(r'[^a-z0-9]', '', title.lower())

        def title_signature(title: str) -> str:
            tokens = [
                token
                for token in re.findall(r"[a-z0-9_+#.-]{2,}", title.lower())
                if token not in COMMON_QUERY_STOPWORDS
            ]
            return " ".join(tokens[:8])

        for post in posts:
            norm_url = normalize_url(post.url)
            norm_title = normalize_title(post.title)
            signature = title_signature(post.title)
            
            # Check URL exact match
            if norm_url in seen_urls:
                continue
                
            # Check Title exact match (simple dedup)
            # This handles cross-posts effectively enough for MVP
            if norm_title in seen_titles:
                continue
            if signature and signature in seen_signatures:
                continue
                
            seen_urls.add(norm_url)
            seen_titles.add(norm_title)
            if signature:
                seen_signatures.add(signature)
            unique.append(post)
            
        return unique

    async def _ai_rerank_posts(
        self,
        query: str,
        posts: List[RedditPost],
        *,
        intent: str = "discussion",
        anchor_terms: Optional[List[str]] = None,
        original_user_query: Optional[str] = None,
        must_keep_terms: Optional[List[str]] = None,
    ) -> List[RedditPost]:
        """Rerank posts using Gemini 3 Flash based on semantic relevance."""
        if not posts:
            return []
            
        logger.info(f"🧠 AI Reranking {len(posts)} posts for query: '{query}'")
        anchor_terms = anchor_terms or []
        
        # Prepare batch prompt
        posts_context = []
        for i, p in enumerate(posts):
            preview = re.sub(r"\s+", " ", (p.selftext or p.full_content or "")[:320])
            comment_snippets = self._extract_comment_snippets(p, limit=2)
            comments_block = " | ".join(comment_snippets) if comment_snippets else "None"
            posts_context.append(
                f"ID: {i} | Title: {p.title} | Sub: {p.subreddit} | "
                f"Engagement: score={p.score}, comments={p.num_comments} | "
                f"Strategy: {','.join(p.strategy_hits[:3]) or p.found_by_strategy or 'unknown'} | "
                f"TitleBodyAnchors: {p.title_body_anchor_matches}/{max(len(anchor_terms), 1)} | "
                f"CommentAnchors: {p.comment_anchor_matches}/{max(len(anchor_terms), 1)} | "
                f"ComparisonSignals: {p.direct_comparison_hits} | "
                f"Preview: {preview} | Comments: {comments_block}"
            )
            
        context_str = "\n".join(posts_context)
        
        prompt = f"""You are a Reddit Retrieval Ranking Engine.
Query: "{query}"
Original User Question: "{original_user_query or query}"
Intent: "{intent}"
Anchor terms that should appear directly in the post when relevant: {anchor_terms or ["none"]}
Must-Keep Meaning Anchors: {must_keep_terms or ["none"]}

Task: Rate each Reddit post for ANSWERABILITY, not just topical similarity.

Prefer posts that:
- directly solve the user's problem
- contain concrete setup steps, configs, trade-offs, benchmarks, or troubleshooting fixes
- include useful practitioner detail in the post body or top comments
- preserve the Original User Question's platform, audience, and requested
  evidence type; do not rank a merely adjacent use of the same technology high

For use_cases and practitioner_examples queries:
- prefer concrete features, commands, shortcuts, automations, and things users
  actually built or repeatedly use
- penalize generic architecture, futurism, unrelated business automation, job
  postings, and a showcase whose body/comments contain no reusable detail

For comparison queries:
- strongly prefer posts that compare the requested tools directly in the title or body
- prefer explicit benchmarks, trade-offs, "X vs Y" discussions, or migration reports
- penalize posts where both tools appear only in comments or incidentally
- penalize broad benchmark/news posts that are not actually about the requested comparison

Penalize posts that are:
- vague discussion without actionable substance
- self-promotion, agency/freelancer marketing, SEO-style listicles
- credit-giveaway / signup-promo pitches and keyword-stuffed titles with
  no hands-on testing or community discussion behind them
- starved engagement (score < ~5, almost no comments) on a listicle or
  "A vs B vs C" style title is a strong SEO-bait signal — rank such posts
  LOW unless the body/comments prove genuine hands-on detail
- off-topic showcase/news when the user asked for a guide or fix
- only weakly adjacent to the query

Posts:
{context_str}

Output JSON format ONLY:
{{
  "ratings": [
    {{"id": 0, "score": 0.95, "reason": "Exact fix with practical comments"}},
    {{"id": 1, "score": 0.10, "reason": "Adjacent showcase, not an answer"}}
  ]
}}
"""
        try:
            # Adversarial categories (comparisons attract SEO "vs"-bait) need
            # the discerning judge; everything else stays on cheap flash-lite.
            rerank_model = (
                config.MODEL_SYNTHESIS
                if intent in {"comparison"}
                else config.MODEL_ANALYSIS
            )
            # Rerank is a scoring task, not a creative one: MODEL_ANALYSIS
            # (flash-lite tier) is sufficient and much cheaper than SYNTHESIS.
            response = await self._llm_client.chat_completions_create(
                model=rerank_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            try:
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    data = json.loads(content[start_idx:end_idx+1])
                    # Robust parsing: handle string IDs from LLM
                    ratings = {}
                    for r in data.get('ratings', []):
                        try:
                            r_id = int(r.get('id'))
                            ratings[r_id] = r
                        except (ValueError, TypeError):
                            continue
                else:
                    ratings = {}
            except Exception:
                logger.warning("Failed to parse reranking JSON")
                ratings = {}
                
            # Assign scores and sort
            # We combine AI score with original engagement signal for robustness
            scored_posts = []
            for i, post in enumerate(posts):
                rating = ratings.get(i)
                ai_score = float(rating['score']) if rating else 0.5 # Default neutral
                
                heuristic_component = min(post.heuristic_score / 1.4, 1.0)
                engagement = max(post.score, 0) + post.num_comments
                norm_engagement = min(math.log1p(engagement) / 8.0, 1.0)
                
                final_score = (
                    (ai_score * 0.72)
                    + (heuristic_component * 0.23)
                    + (norm_engagement * 0.05)
                )

                post.ai_score = ai_score
                post.final_score = final_score
                if rating and 'reason' in rating:
                    post.ranking_reason = str(rating['reason'])[:240]
                else:
                    post.ranking_reason = "LLM rerank fallback"
                    
                scored_posts.append((post, final_score))
            
            # Sort desc
            scored_posts.sort(key=lambda x: x[1], reverse=True)
            
            # Return just posts
            return [p for p, _ in scored_posts]
            
        except Exception as e:
            logger.error(f"Error in _ai_rerank_posts: {e}")
            return posts # Fallback to original order
    
    @staticmethod
    def _clean_serp_text(text: str) -> str:
        """CSE titles/snippets contain HTML tags and entities — strip them."""
        if not text:
            return ""
        cleaned = html.unescape(re.sub(r"<[^>]+>", " ", text))
        return re.sub(r"\s+", " ", cleaned).strip()

    async def _search_serper(
        self, query: str, recent_only: bool = False
    ) -> List[RedditPost]:
        """Google SERP discovery via Serper.dev (site:reddit.com).

        Brings Google-quality ranking and comment-level indexing that native
        Reddit search lacks. Returns snippet-only candidates; created_utc is
        unknown (exempt from the recent_only post-filter, same as CSE).
        Silently returns [] when SERPER_API_KEY is not configured.
        """
        if not config.SERPER_API_KEY:
            return []

        payload: Dict[str, Any] = {
            "q": f"{query} site:reddit.com",
            # <=10 results keeps the call at 1 credit
            "num": max(1, min(config.SERPER_RESULTS, 10)),
        }
        try:
            client = await self._get_client()
            resp = await client.post(
                config.SERPER_ENDPOINT,
                json=payload,
                headers={"X-API-KEY": config.SERPER_API_KEY},
            )
            if resp.status_code != 200:
                logger.warning(
                    f"Serper error {resp.status_code}: {resp.text[:200]}"
                )
                return []
            items = (resp.json() or {}).get("organic") or []
        except Exception as e:
            logger.warning(f"Serper request failed: {e}")
            return []

        posts: List[RedditPost] = []
        for item in items:
            link = item.get("link") or ""
            id_m = re.search(r"/comments/([a-z0-9]+)/", link, re.IGNORECASE)
            sub_m = re.search(r"/r/([A-Za-z0-9_]+)/", link)
            if not (id_m and sub_m):
                continue  # not a post permalink
            posts.append(
                RedditPost(
                    id=id_m.group(1),
                    title=self._clean_serp_text(item.get("title", "")),
                    url=link,
                    permalink=link,
                    score=0,
                    num_comments=0,
                    subreddit=sub_m.group(1),
                    author="unknown",
                    created_utc=0,  # unknown; see recent_only exemption
                    selftext=self._clean_serp_text(item.get("snippet", ""))[:1000],
                    found_by_strategy="serp_google_discovery",
                    strategy_hits=["serp_google_discovery"],
                )
            )

        logger.info(
            f"🌐 Serper Google discovery: {len(posts)} candidates for '{query[:50]}'"
        )
        return posts

    async def _search_arctic_shift(
        self,
        query: str,
        subreddits: List[str],
        recent_only: bool = False,
    ) -> List[RedditPost]:
        """Exhaustive full-text recall within scout-suggested subreddits.

        Arctic Shift is a free community mirror with live ingestion (minutes
        of lag, verified 2026-08) and a COMPLETE per-subreddit index — unlike
        native search it does not miss existing threads due to ranking quirks.
        Limitation (by design): text search requires a subreddit scope.

        Strategy: title-match on the top scout subreddits, newest first.
        recent_only maps to Arctic's human-readable `after` window.
        """
        if not config.ARCTIC_SHIFT_ENABLED:
            return []
        subs = [
            s.strip() for s in (subreddits or [])[: config.ARCTIC_TARGET_SUBREDDITS]
            if s.strip()
        ]
        clean_query = (query or "").strip()
        if not subs or not clean_query:
            return []

        async def fetch_one(sub: str, field: str) -> List[Dict[str, Any]]:
            params: Dict[str, Any] = {
                "subreddit": sub,
                field: clean_query,
                "limit": max(1, min(config.ARCTIC_LIMIT_PER_SUB, 100)),
                "sort": "desc",
            }
            if recent_only:
                params["after"] = f"{REDDIT_RECENT_WINDOW_DAYS}d"
            client = await self._get_client()
            resp = await client.get(config.ARCTIC_SHIFT_ENDPOINT, params=params)
            if resp.status_code != 200:
                logger.warning(
                    f"Arctic Shift error {resp.status_code} for r/{sub}: "
                    f"{resp.text[:150]}"
                )
                return []
            return (resp.json() or {}).get("data") or []

        try:
            # Title matches are high-precision; selftext widens recall for
            # questions whose answer lives in the post body, not the title.
            results = await asyncio.gather(
                *[fetch_one(s, f) for s in subs for f in ("title", "selftext")],
                return_exceptions=True,
            )
        except Exception as e:  # pragma: no cover - gather rarely raises here
            logger.warning(f"Arctic Shift request failed: {e}")
            return []

        posts_by_id: Dict[str, RedditPost] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Arctic Shift channel failed: {result}")
                continue
            for p in result:
                pid = p.get("id")
                if not pid or pid in posts_by_id:
                    continue
                permalink = p.get("permalink") or ""
                posts_by_id[str(pid)] = RedditPost(
                    id=str(pid),
                    title=(p.get("title") or "").strip(),
                    url=f"https://reddit.com{permalink}",
                    permalink=f"https://reddit.com{permalink}",
                    score=int(p.get("score") or 0),
                    num_comments=int(p.get("num_comments") or 0),
                    subreddit=p.get("subreddit") or "",
                    author=p.get("author") or "",
                    created_utc=int(p.get("created_utc") or 0),
                    selftext=(p.get("selftext") or "")[:4000],
                    found_by_strategy="arctic_targeted_archive",
                    strategy_hits=["arctic_targeted_archive"],
                )

        if posts_by_id:
            logger.info(
                f"🔎 Arctic Shift: {len(posts_by_id)} candidates from "
                f"r/{', r/'.join(subs)} for '{query[:50]}'"
            )
        return list(posts_by_id.values())

    async def _search_with_sort(
        self,
        query: str,
        sort: str = "relevance",
        limit: int = 25,
        time: str = "all",
        subreddits: Optional[List[str]] = None,
    ) -> List[RedditPost]:
        """Search Reddit with specific sort parameter."""
        payload = {
            "query": query,
            "limit": min(limit, 25),
            "sort": sort,
            "time": time,
        }
        if subreddits:
            payload["subreddits"] = subreddits
        
        return await self._circuit_breaker.call(
            self._execute_search,
            payload
        )
    
    async def _search_subreddit(
        self,
        query: str,
        subreddit: str,
        limit: int = 25
    ) -> List[RedditPost]:
        """Search within a specific subreddit."""
        return await self._search_with_sort(
            query,
            sort="relevance",
            limit=limit,
            time="all",
            subreddits=[subreddit],
        )
    
    async def _execute_search(self, payload: Dict[str, Any]) -> List[RedditPost]:
        """Execute search request and parse results."""
        client = await self._get_client()
        url = f"{self.base_url}/search"
        
        logger.debug(f"Reddit search: {payload}")
        
        response = await client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # DEBUG: Check what we got from proxy
        sources = data.get("sources", [])
        logger.info(f"REDDIT PROXY DEBUG: Got {len(sources)} sources")
        if sources:
            first = sources[0]
            has_selftext = bool(first.get("selftext"))
            logger.info(f"REDDIT PROXY DEBUG: First source has selftext: {has_selftext}, keys: {list(first.keys())}")
        
        posts = []
        for src in data.get("sources", []):
            url = src.get("url", "")
            # Extract post ID from Reddit URL safely
            # Reddit URL format: .../comments/{post_id}/{slug}/ or .../comments/{post_id}/
            post_id = ""
            if "/" in url:
                parts = [p for p in url.split("/") if p]
                # Find 'comments' segment and take the next part as post_id
                if "comments" in parts:
                    idx = parts.index("comments")
                    if idx + 1 < len(parts):
                        post_id = parts[idx + 1]
                # Fallback: if no comments segment, use last non-empty part
                elif len(parts) >= 1:
                    post_id = parts[-1]
            
            # Try to parse creation date
            created_utc = src.get("created_utc") or src.get("created") or 0
            
            post = RedditPost(
                id=post_id or "unknown",
                title=src.get("title") or "Untitled",
                url=url,
                permalink=url,
                score=src.get("score") or 0,
                num_comments=src.get("commentsCount") or 0,
                subreddit=src.get("subreddit") or "unknown",
                author=src.get("author") or "unknown",
                created_utc=created_utc,
                selftext=src.get("selftext") or "",  # CRITICAL: Get content from proxy
                top_comments=src.get("top_comments") or [] # NEW: Get comments from proxy
            )
            posts.append(post)
        
        return posts
    
    async def _enrich_post_content(self, post: RedditPost) -> RedditPost:
        """Fetch full content and comments for a post via Proxy /details endpoint."""
        try:
            client = await self._get_client()
            url = f"{self.base_url}/details"
            
            payload = {
                "postId": post.id,
                # Reddit resolves a post by id alone; subreddit not needed here
                "comment_limit": 100,  # more comments for "30% more meat"
                "comment_depth": 5     # deeper into threads
            }
            
            # Using circuit breaker logic for robustness, though individual failures shouldn't stop the pipeline
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Enriched data from proxy
                # Proxy returns sanitized 'selftext' which we treat as full_content
                full_text = data.get("selftext") or data.get("body") or ""
                post.full_content = full_text
                post.top_comments = data.get("top_comments") or []
                
                # Update basic fields if better data available
                # If original selftext was truncated or missing, update it
                if full_text and len(full_text) > len(post.selftext):
                     post.selftext = full_text

                logger.info(f"✅ Enriched post {post.id} (r/{post.subreddit}): {len(post.top_comments)} comments")
            else:
                logger.warning(f"Failed to enrich post {post.id}: Status {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Error enriching post {post.id}: {e}")
            
        return post
    
    async def health_check(self) -> bool:
        """Check if Reddit Proxy service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Reddit Proxy health check failed: {e}")
            return False


# Singleton instance
_enhanced_service: Optional[RedditEnhancedService] = None


def get_reddit_enhanced_service() -> RedditEnhancedService:
    """Get or create singleton RedditEnhancedService instance."""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = RedditEnhancedService()
    return _enhanced_service


async def search_reddit_enhanced(
    query: str,
    target_posts: int = 25,
    include_comments: bool = True,
    subreddits: Optional[List[str]] = None,
    recent_only: bool = False,
    original_user_query: Optional[str] = None,
    user_intent: Optional[str] = None,
    must_keep_terms: Optional[List[str]] = None,
) -> EnhancedSearchResult:
    """Convenience function for enhanced Reddit search.

    Args:
        query: Search query
        target_posts: Target number of unique posts
        include_comments: Whether to fetch comments for top posts
        subreddits: Optional list of subreddits to search
        recent_only: Hard-filter results to the last REDDIT_RECENT_WINDOW_DAYS days

    Returns:
        EnhancedSearchResult
    """
    service = get_reddit_enhanced_service()
    return await service.search_enhanced(
        query=query,
        target_posts=target_posts,
        include_comments=include_comments,
        subreddits=subreddits,
        recent_only=recent_only,
        original_user_query=original_user_query,
        user_intent=user_intent,
        must_keep_terms=must_keep_terms,
    )
