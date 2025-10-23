---
name: reranking_final.md
branch: feature/reranking-final
status: pending
created: 2025-10-22
submodules:
---

# Гибридный ре-ранкинг Medium постов (итоговая реализация)

## Problem/Goal
Объединить два существующих файла задач по ре-ранкингу Medium постов и реализовать гибридный подход, где GPT-4o-mini оценивает все Medium посты, а код принимает финальное решение на основе порога score >= 0.7.

Текущие файлы для объединения:
- `/sessions/tasks/m-medium-reranking-service_1.md` - базовый ре-ранкинг с Top-K подходом
- `/sessions/tasks/m-medium-reranking-service_2.md` - гибридный подход с оценкой и пороговым отбором

## Success Criteria
- [ ] Создан unified `MediumScoringService` с GPT-4o-mini
- [ ] Реализован гибридный подход: LLM оценивает все Medium посты, код отбирает по порогу >= 0.7
- [ ] Сервис интегрирован в query pipeline после Map фазы
- [ ] **КРИТИЧНО**: Ре-ранкинг происходит независимо для каждого эксперта (параллельная обработка)
- [ ] Все старые файлы задач удалены или перемещены в archive
- [ ] Проведено тестирование и измерение производительности
- [ ] Обновлена документация в CLAUDE.md

## Context Manifest

### How This Currently Works: Multi-Expert Query Processing Pipeline

The current system implements a sophisticated six-phase parallel processing pipeline that handles multiple experts simultaneously. Understanding this architecture is crucial for implementing the Medium posts reranking system effectively.

**Current Pipeline Architecture:**
```
User Query → Multi-Expert Detection → Parallel Processing per Expert:
Map → Filter (HIGH+MEDIUM) → Resolve → Reduce → Comment Groups → Comment Synthesis
```

**Multi-Expert Parallel Processing:**
The system processes all experts in parallel using async tasks. Each expert runs through the complete pipeline independently, with expert isolation at every level - posts, comments, links, and drift groups are all filtered by `expert_id`. The parallel architecture reduces total processing time to the maximum of individual expert times rather than the sum.

**Map Phase - Current Implementation:**
- **Service:** `MapService` in `backend/src/services/map_service.py`
- **Model:** Qwen 2.5-72B Instruct (`qwen/qwen-2.5-72b-instruct`)
- **Process:** Processes posts in chunks of 40 with robust retry mechanism (3 per-chunk + 1 global retry)
- **Output:** Posts classified as HIGH/MEDIUM/LOW relevance with explanations
- **Key Method:** `process(posts, query, expert_id, progress_callback)` returns dictionary with `relevant_posts` list

**Current Filtering Logic:**
In `simplified_query_endpoint.py` lines 145-149, the system currently filters for HIGH and MEDIUM posts:
```python
filtered_posts = [
    p for p in relevant_posts
    if p.get("relevance") in ["HIGH", "MEDIUM"]
]
```

**Expert Isolation Pattern:**
All services receive `expert_id` parameter and implement database-level filtering:
```python
# Pattern used across all services
posts = db.query(Post).filter(Post.expert_id == expert_id).all()
```

**OpenRouter Integration Pattern:**
Services use standardized OpenAI client through `openrouter_adapter.py`:
```python
from .openrouter_adapter import create_openrouter_client, convert_model_name

self.client = create_openrouter_client(api_key=api_key)
self.model = convert_model_name(model)  # Maps "gpt-4o-mini" → "openai/gpt-4o-mini"
```

**Progress Tracking & SSE:**
All services implement progress callbacks with consistent structure:
```python
await progress_callback({
    "phase": "service_name",
    "status": "processing",
    "message": "Description of current operation",
    "expert_id": expert_id  # Added for multi-expert tracking
})
```

**Error Handling Patterns:**
Services use tenacity for retry logic with exponential backoff:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
    reraise=True
)
```

**Prompt Loading Pattern:**
Services load prompts from external files using Template substitution:
```python
from pathlib import Path
from string import Template

def _load_prompt_template(self) -> Template:
    prompt_dir = Path(__file__).parent.parent.parent / "prompts"
    prompt_path = prompt_dir / "service_prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return Template(f.read())
```

**Language Support System:**
All services integrate with language utilities for consistent response language:
```python
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

prompt = prepare_prompt_with_language_instruction(base_prompt, query)
system_message = prepare_system_message_with_language(base_system, query)
```

**Current Data Flow for Medium Posts:**
1. **Map Phase:** Returns MEDIUM relevance posts with explanations
2. **Filter Phase:** Includes all MEDIUM posts in pipeline (no filtering)
3. **Resolve Phase:** Expands context for all HIGH+MEDIUM posts via author links
4. **Reduce Phase:** Synthesizes answer from all posts, sorted by relevance

**Integration Points for New Service:**
The Medium reranking service needs to integrate between Map and Resolve phases:
```python
# Current flow in simplified_query_endpoint.py:142-149
relevant_posts = map_results.get("relevant_posts", [])
filtered_posts = [p for p in relevant_posts if p.get("relevance") in ["HIGH", "MEDIUM"]]

# New flow needed:
high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

if medium_posts:
    # New Medium reranking service here
    scored_medium_posts = await medium_scoring_service.score_medium_posts(...)
    selected_medium_posts = [p for p in scored_medium_posts if p.get("score", 0) >= 0.7]
    filtered_posts = high_posts + selected_medium_posts
else:
    filtered_posts = high_posts
```

### For New Feature Implementation: Medium Posts Hybrid Reranking System

**Service Architecture Requirements:**
The new `MediumScoringService` must follow established patterns:

1. **Service Location:** `backend/src/services/medium_scoring_service.py`
2. **Model Integration:** Use GPT-4o-mini via OpenRouter (`openai/gpt-4o-mini`)
3. **Parallel Processing:** Process each expert independently during parallel expert pipeline
4. **Progress Tracking:** Implement consistent progress callbacks with expert_id
5. **Error Handling:** Use tenacity retry pattern for API reliability
6. **Language Support:** Integrate with language utilities for multilingual queries

**Integration Strategy:**
The service must integrate into the existing parallel multi-expert pipeline:

1. **Pipeline Position:** Between Map and Resolve phases in `process_expert_pipeline()`
2. **Expert Isolation:** Receive `expert_id` parameter and ensure MEDIUM posts are filtered by expert
3. **Parallel Execution:** Each expert's MEDIUM posts scored independently during parallel processing
4. **Fallback Logic:** Graceful degradation if scoring fails (use original MEDIUM posts)

**Database Considerations:**
- No new database tables required (pure LLM scoring)
- Uses existing Post model data from Map phase
- Maintains expert isolation through existing `expert_id` filtering

**Performance Requirements:**
- Cost-effective: GPT-4o-mini at $0.15/$0.60 per 1M tokens
- Parallel processing: All experts processed simultaneously
- Minimal overhead: +5-10 seconds total processing time

### Technical Reference Details

#### Component Interfaces & Signatures

**MapService Integration:**
```python
# Current Map phase output
map_results = await map_service.process(
    posts=posts,
    query=request.query,
    expert_id=expert_id,
    progress_callback=map_progress
)
relevant_posts = map_results.get("relevant_posts", [])
# relevant_posts structure: [{"telegram_message_id": int, "relevance": "HIGH|MEDIUM|LOW", "reason": str}]
```

**New MediumScoringService Interface:**
```python
class MediumScoringService:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = create_openrouter_client(api_key=api_key)
        self.model = convert_model_name(model)
        self._prompt_template = self._load_prompt_template()

    async def score_medium_posts(
        self,
        medium_posts: List[Dict[str, Any]],
        high_posts_context: str,
        query: str,
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Score MEDIUM posts 0.0-1.0 for relevance complementing HIGH posts"""

# Expected output format:
[
    {
        "telegram_message_id": 123,
        "relevance": "MEDIUM",  # Keep original classification
        "reason": "Original reason from Map phase",
        "score": 0.85,  # New LLM evaluation score
        "score_reason": "Why this post scored 0.85"
    },
    ...
]
```

**Integration in simplified_query_endpoint.py:**
```python
# Around line 145-149, replace current filtering logic:

# Separate HIGH and MEDIUM posts
high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

# NEW: Score MEDIUM posts
if medium_posts:
    scoring_service = MediumScoringService(api_key)

    async def scoring_progress(data: dict):
        if progress_callback:
            data['expert_id'] = expert_id
            await progress_callback(data)

    # Create context from HIGH posts
    high_context = json.dumps([
        {
            "telegram_message_id": p["telegram_message_id"],
            "content": p.get("content", ""),
            "reason": p.get("reason", "")
        }
        for p in high_posts
    ], ensure_ascii=False, indent=2)

    # Score MEDIUM posts
    scored_medium_posts = await scoring_service.score_medium_posts(
        medium_posts=medium_posts,
        high_posts_context=high_context,
        query=request.query,
        expert_id=expert_id,
        progress_callback=scoring_progress
    )

    # Filter by score threshold (0.7)
    selected_medium_posts = [
        p for p in scored_medium_posts
        if p.get("score", 0) >= 0.7
    ]

    # Combine HIGH + scored MEDIUM posts
    filtered_posts = high_posts + selected_medium_posts

    logger.info(f"[{expert_id}] Medium reranking: {len(medium_posts)} → {len(selected_medium_posts)} posts (score >= 0.7)")
else:
    filtered_posts = high_posts
```

#### Data Structures

**Input to MediumScoringService:**
```python
medium_posts = [
    {
        "telegram_message_id": int,
        "relevance": "MEDIUM",
        "reason": str,  # From Map phase
        "content": str,  # Post content
        "author": str,
        "created_at": str
    },
    ...
]

high_posts_context = json.dumps([
    {
        "telegram_message_id": int,
        "content": str,
        "reason": str
    }
    for high_post in high_posts])
```

**Output from MediumScoringService:**
```python
scored_posts = [
    {
        "telegram_message_id": int,
        "relevance": "MEDIUM",  # Preserved
        "reason": str,  # Preserved from Map
        "score": float,  # 0.0-1.0 from GPT-4o-mini
        "score_reason": str,  # Why this score
        "content": str,  # Preserved
        "author": str,  # Preserved
        "created_at": str  # Preserved
    },
    ...
]
```

#### Configuration Requirements

**Environment Variables:**
- `OPENAI_API_KEY`: OpenRouter API key (already required)
- No additional environment variables needed

**Model Configuration:**
```python
# GPT-4o-mini via OpenRouter
MODEL = "gpt-4o-mini"  # Converted to "openai/gpt-4o-mini"
COST_PER_1M_TOKENS = {"input": 0.15, "output": 0.60}
```

**Score Threshold:**
```python
SCORE_THRESHOLD = 0.7  # Select posts with score >= 0.7
```

#### File Locations

**Implementation Files:**
- Service: `backend/src/services/medium_scoring_service.py`
- Prompt: `backend/prompts/medium_scoring_prompt.txt`
- Integration: `backend/src/api/simplified_query_endpoint.py` (lines ~145-170)

**Prompt Template Structure:**
```
You are scoring MEDIUM-relevance posts to determine which ones should complement HIGH-relevance posts.

User query: {query}
HIGH posts summary: {high_posts_context}

MEDIUM posts to evaluate:
{medium_posts}

For each MEDIUM post, provide:
- score: 0.0-1.0 (how well it complements HIGH posts)
- reason: why this score

Return JSON format:
{
  "scored_posts": [
    {
      "telegram_message_id": <id>,
      "score": <0.0-1.0>,
      "reason": "<explanation>"
    }
  ]
}
```

**Error Handling Requirements:**
- Implement retry logic using tenacity (3 attempts)
- Graceful degradation: if scoring fails, use original MEDIUM posts
- JSON parsing error handling with repair attempts
- Progress callback error reporting

**Testing Strategy:**
- Test with various numbers of MEDIUM posts (1, 5, 15, 30)
- Validate score distribution (should be 0.0-1.0)
- Test parallel processing with multiple experts
- Verify fallback behavior when API fails
- Performance testing: < 10 seconds additional processing time

## User Notes
- Сразу внедряем гибридный вариант с порогом >= 0.7 (не MVP с жестким лимитом)
- Финальный файл должен называться `reranking_final.md` и быть в `sessions/tasks/`
- Использовать лучшие практики из обоих исходных файлов
- Обратить внимание на обработку ошибок и graceful degradation

## Work Log
<!-- Updated as work progresses -->
- [2025-10-22] Started task, analyzed existing task files and created unified task
- [2025-10-23] Context compaction protocol executed - consolidated work logs, no implementation work done yet
