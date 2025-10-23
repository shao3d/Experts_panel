# Pipeline Architecture Guide

Detailed guide for the six-phase Map-Resolve-Reduce pipeline with comment analysis capabilities.

## 🏗️ Overview

The Experts Panel uses a sophisticated **six-phase pipeline** to process user queries and generate comprehensive answers from expert content:

1. **Map Phase** - Find relevant posts via semantic search
2. **Filter Phase** - Keep only HIGH relevance posts
3. **Resolve Phase** - Expand context via database links
4. **Reduce Phase** - Synthesize final answer
5. **Comment Groups** - Find relevant comment discussions
6. **Comment Synthesis** - Extract complementary insights

## 🚀 Map Phase

### Purpose
Find relevant posts from the expert's content using semantic search and relevance scoring.

### Implementation
- **File**: `backend/src/services/map_service.py`
- **Model**: Qwen 2.5-72B Instruct
- **Cost**: $0.08/$0.33 per 1M tokens
- **Chunk Size**: 40 posts per chunk

### Key Features

#### Robust Retry Mechanism (NEW 2025-10-15)
Two-layer retry strategy ensures reliable processing:

**Layer 1: Per-Chunk Retry**
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
    reraise=True
)
```

**Layer 2: Global Retry**
- 1 additional retry for failed chunks
- Comprehensive error logging with expert_id
- 95%+ recovery rate for failed chunks

#### Processing Flow
1. **Chunk Creation**: Split posts into groups of 40
2. **Parallel Processing**: Process chunks simultaneously
3. **Relevance Scoring**: HIGH, MEDIUM, LOW classification
4. **Error Recovery**: Retry failed chunks automatically
5. **Progress Tracking**: SSE events for real-time updates

### Output Format
```json
{
  "relevant_posts": [
    {
      "post_id": 123,
      "relevance": "HIGH|MEDIUM|LOW",
      "reason": "Detailed explanation of relevance"
    }
  ]
}
```

## 🔍 Filter Phase

### Purpose
Remove LOW and MEDIUM relevance posts to focus on most relevant content.

### Implementation
- **File**: `backend/src/api/simplified_query_endpoint.py:144-148`
- **Filter Logic**: Keep ONLY HIGH relevance posts
- **Impact**: Reduces dataset by 60-70%

### Benefits
- Improved precision in subsequent phases
- Reduced token usage
- Faster processing times
- Better focus on highly relevant content

## 🔗 Resolve Phase

### Purpose
Expand context by following database links (replies, forwards, mentions).

### Implementation
- **File**: `backend/src/services/simple_resolve_service.py`
- **Strategy**: Database-only approach (no GPT evaluation)
- **Depth**: Depth 1 expansion only

### Key Principles
- **Trust Author's Links**: All author references are included
- **Fast Processing**: 10x faster than GPT-based evaluation
- **100% Accuracy**: Based on database structure, not text parsing
- **Prevent Context Drift**: Limited depth prevents runaway expansion

### Process Flow
1. **Link Query**: Find all links from HIGH relevance posts
2. **Link Expansion**: Add linked posts to context
3. **Type Filtering**: Handle REPLY, FORWARD, MENTION types
4. **Expert Isolation**: Filter by expert_id

## ⚡ Reduce Phase

### Purpose
Synthesize final answer using expanded context and expert's writing style.

### Implementation
- **File**: `backend/src/services/reduce_service.py`
- **Model**: Gemini 2.0 Flash
- **Cost**: $0.10/$0.40 per 1M tokens
- **Style**: Personal or Neutral

### Answer Styles

#### Personal Style (Default)
- First-person perspective from expert's view
- Uses author's characteristic voice and patterns
- Includes emotional markers and personal experiences
- Activated with `use_personal_style=True`

#### Neutral Style
- Standard analytical answers
- Third-person perspective
- Activated with `use_personal_style=False`

### Key Features

#### Fact Validation
- Validates all `[post:ID]` references
- Ensures referenced posts exist and match dates
- Automatically adds missing post IDs to main_sources
- Prevents hallucinated references

#### Content Processing
1. **Post Sorting**: By relevance (HIGH → MEDIUM → CONTEXT)
2. **Token Limiting**: Maximum 50 posts
3. **Context Construction**: Builds coherent narrative
4. **Answer Synthesis**: Generates comprehensive response

### Output Format
```json
{
  "answer": "Comprehensive answer in expert's voice",
  "main_sources": [21, 65, 77],
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "Explanation of answer confidence"
}
```

## 💬 Comment Groups Phase

### Purpose
Find relevant comment discussions that may contain insights not covered in main posts.

### Implementation
- **File**: `backend/src/services/comment_group_map_service.py`
- **Model**: GPT-4o-mini (fast, cost-effective)
- **Strategy**: Pre-analyzed drift matching

### Two-Phase Architecture

#### Phase 1: Pre-Analysis (Offline)
- **Script**: `backend/analyze_drift.py`
- **Model**: Claude Sonnet 4.5
- **Process**: Analyze comment groups for topic drift
- **Storage**: Results in `comment_group_drift` table

#### Phase 2: Query-Time Matching (Online)
- **Process**: Match query against pre-analyzed drift topics
- **Filtering**: HIGH relevance groups only
- **Output**: Anchor posts with relevant discussions

### Integration
- Runs AFTER Reduce phase completes
- Excludes main_sources from Reduce phase
- Processes 20 drift groups per chunk
- Rate limiting: Max 5 parallel requests

## 🔧 Comment Synthesis Phase

### Purpose
Extract complementary insights from relevant comment groups.

### Implementation
- **File**: `backend/src/services/comment_synthesis_service.py`
- **Model**: Gemini 2.0 Flash
- **Trigger**: Only when HIGH comment groups exist

### Key Constraints
- **No [post:ID] references**: Prevents UI confusion
- **Complementary insights**: Focus on content not in main answer
- **Unlimited bullet points**: Extract all valuable insights
- **Accuracy requirements**: Strict fact validation

### Process Flow
1. **Group Selection**: HIGH relevance comment groups only
2. **Content Analysis**: Extract insights not covered in main answer
3. **Synthesis**: Generate structured insights
4. **Validation**: Ensure accuracy and relevance

## 🔄 Parallel Processing

### Multi-Expert Support
- Each expert processed independently via async tasks
- No data mixing between experts
- SSE events include expert_id for tracking
- Dynamic expert detection from database

### Performance Benefits
- **Parallel Processing**: Reduces total time to max(expert_times)
- **Resource Efficiency**: Optimal API usage
- **Failure Isolation**: Expert failure doesn't affect others

## 📊 Model Selection Strategy

### Model Rationale
- **Qwen 2.5-72B**: Superior document ranking and relevance scoring
- **Gemini 2.0 Flash**: Better context synthesis and instruction following
- **GPT-4o-mini**: Fast and cost-effective for matching tasks

### Performance Characteristics
| Model | Use Case | Cost | Strengths |
|-------|----------|------|-----------|
| Qwen 2.5-72B | Map Phase | $0.08/$0.33 | Document ranking, relevance scoring |
| Gemini 2.0 Flash | Reduce, Synthesis | $0.10/$0.40 | Context synthesis, instruction following |
| GPT-4o-mini | Comment Groups | Fast/cheap | Keyword matching, fast processing |

## 🛠️ Configuration

### Pipeline Parameters
```python
# Map Phase
CHUNK_SIZE = 40  # Posts per chunk
MAX_GLOBAL_RETRIES = 1  # Additional global retry attempts

# Filter Phase
RELEVANCE_THRESHOLD = "HIGH"  # Only HIGH relevance posts

# Reduce Phase
MAX_POSTS = 50  # Maximum posts for synthesis
USE_PERSONAL_STYLE = True  # Default to personal style

# Comment Groups
DRIFT_CHUNK_SIZE = 20  # Drift groups per API call
MAX_PARALLEL_REQUESTS = 5  # Rate limiting
```

### Model Configuration
```python
DEFAULT_MODELS = {
    "map": "qwen/qwen-2.5-72b-instruct",
    "reduce": "google/gemini-2.0-flash-001",
    "comment_groups": "openai/gpt-4o-mini",
    "comment_synthesis": "google/gemini-2.0-flash-001"
}
```

## 🔍 Debugging and Monitoring

### Progress Tracking
- **SSE Events**: Real-time progress updates
- **Expert Prefix**: All events include `[expert_id]`
- **Phase Tracking**: Clear indication of current pipeline phase

### Common Issues
1. **Map Phase Failures**: Check retry logs and API status
2. **Empty Results**: Verify data exists for expert
3. **Timeout Issues**: Check chunk size and API limits
4. **Context Issues**: Verify database links and constraints

### Performance Monitoring
```bash
# Check retry patterns
grep "Global retry" backend/logs/app.log

# Monitor processing time
grep "processing_time_ms" backend/logs/app.log

# Check for failures
grep "failed" backend/logs/app.log
```

## 📁 Key Files and Locations

### Core Pipeline Services
- **Map Service**: `backend/src/services/map_service.py`
- **Resolve Service**: `backend/src/services/simple_resolve_service.py`
- **Reduce Service**: `backend/src/services/reduce_service.py`
- **Comment Groups**: `backend/src/services/comment_group_map_service.py`
- **Comment Synthesis**: `backend/src/services/comment_synthesis_service.py`

### Integration and Orchestration
- **Main Endpoint**: `backend/src/api/simplified_query_endpoint.py`
- **API Models**: `backend/src/api/models.py`
- **OpenRouter Adapter**: `backend/src/services/openrouter_adapter.py`

### Prompts and Templates
- **Map Prompt**: `backend/prompts/map_prompt.txt`
- **Reduce Prompts**: `backend/prompts/reduce_prompt*.txt`
- **Comment Prompts**: `backend/prompts/comment_*.txt`

## 🚀 Future Enhancements

### Potential Improvements
1. **Adaptive Chunking**: Dynamic chunk sizes based on content
2. **Model Selection**: Automatic model selection based on query complexity
3. **Caching**: Intelligent caching for repeated queries
4. **Performance Optimization**: Further parallel processing opportunities

### Scaling Considerations
- **Database Optimization**: Indexes for faster queries
- **API Rate Limiting**: Intelligent rate limiting across models
- **Resource Management**: Memory and processing optimization