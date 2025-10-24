# Pipeline Architecture Guide

Detailed guide for the **eight-phase** Map-Resolve-Reduce pipeline with Medium Posts Hybrid Reranking, Language Validation, and comment analysis capabilities.

## 🏗️ Overview

The Experts Panel uses a sophisticated **eight-phase pipeline** to process user queries and generate comprehensive answers from expert content:

1. **Map Phase** - Find relevant posts via semantic search
2. **Medium Scoring Phase** - Score and select Medium posts with hybrid reranking
3. **Differential Resolve Phase** - Expand context for HIGH posts only
4. **Reduce Phase** - Synthesize final answer with all selected posts
5. **Language Validation Phase** - Validate response language consistency and translate if needed
6. **Comment Groups** - Find relevant comment discussions
7. **Comment Synthesis** - Extract complementary insights
8. **Response Building** - Assemble final multi-expert response

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

## 🎯 Medium Scoring Phase

### Purpose
Intelligently score and select Medium relevance posts using hybrid reranking to identify valuable content that might be missed by simple HIGH/LOW filtering.

### Implementation
- **File**: `backend/src/services/medium_scoring_service.py`
- **Model**: Qwen 2.5-72B Instruct
- **Strategy**: Hybrid threshold + top-K selection
- **Memory Management**: Maximum 50 Medium posts processed

### Hybrid Reranking Algorithm

#### Two-Stage Selection Process
1. **Threshold Filtering**: Score ≥ 0.7 passes first filter
2. **Top-K Selection**: From filtered posts, select top-5 by highest score

#### Configuration Parameters
```python
MEDIUM_SCORE_THRESHOLD = 0.7      # Minimum score threshold
MEDIUM_MAX_SELECTED_POSTS = 5     # Maximum posts to select
MEDIUM_MAX_POSTS = 50           # Memory limit for processing
```

### Key Features

#### Intelligent Scoring
- **Contextual Evaluation**: Posts scored within query context
- **Relevance Granulation**: Fine-grained scoring vs binary HIGH/LOW
- **Content Quality Assessment**: Evaluates substance and insight value

#### Memory Efficiency
- **Chunked Processing**: Processes Medium posts in manageable batches
- **Progressive Filtering**: Applies thresholds early to reduce load
- **Resource Limits**: Hard caps prevent memory overflow

### Process Flow
1. **Collection**: Gather all MEDIUM relevance posts from Map phase
2. **Scoring**: Rate each post on 0.0-1.0 scale for query relevance
3. **Threshold Filter**: Keep posts scoring ≥ 0.7
4. **Top-K Selection**: Select top-5 highest scoring posts
5. **Output**: Pass selected posts to Reduce phase

### Output Format
```json
{
  "selected_medium_posts": [
    {
      "post_id": 456,
      "score": 0.85,
      "reason": "Directly addresses user's question with technical details"
    }
  ],
  "total_medium_processed": 23,
  "threshold_passed": 8,
  "final_selected": 5
}
```

## 🔍 Filter Phase

### Purpose
Remove LOW relevance posts while keeping HIGH and selected Medium posts for comprehensive coverage.

### Implementation
- **File**: `backend/src/api/simplified_query_endpoint.py:144-148`
- **Filter Logic**: Keep HIGH relevance posts + selected Medium posts
- **Impact**: Reduces dataset by 40-50% while preserving valuable content

### Benefits
- **Improved Precision**: Focuses on most relevant content
- **Reduced Token Usage**: Optimizes processing efficiency
- **Enhanced Coverage**: Medium scoring rescues valuable content
- **Faster Processing**: Smaller, higher quality dataset

## 🔗 Differential Resolve Phase

### Purpose
Expand context by following database links for HIGH relevance posts only, while selected Medium posts bypass this phase and go directly to Reduce.

### Implementation
- **File**: `backend/src/services/simple_resolve_service.py`
- **Strategy**: Database-only approach (no GPT evaluation)
- **Depth**: Depth 1 expansion only
- **Differential Processing**: HIGH posts → Resolve, Medium posts → bypass

### Differential Processing Logic
1. **HIGH Posts**: Processed through Resolve phase with linked posts
2. **Selected Medium Posts**: Skip Resolve phase, go directly to Reduce
3. **Efficiency**: Reduces processing time while maintaining quality

### Key Principles
- **Trust Author's Links**: All author references from HIGH posts are included
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
Synthesize final answer using HIGH posts with expanded context and selected Medium posts from hybrid reranking.

### Implementation
- **File**: `backend/src/services/reduce_service.py`
- **Model**: Gemini 2.0 Flash
- **Cost**: $0.10/$0.40 per 1M tokens
- **Style**: Personal or Neutral
- **Input**: HIGH posts (with linked content) + selected Medium posts

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
1. **Post Sorting**: HIGH posts (with linked content) → selected Medium posts → remaining context
2. **Token Limiting**: Maximum 50 posts total
3. **Priority Handling**: HIGH posts get priority, Medium posts supplement gaps
4. **Context Construction**: Builds coherent narrative from diverse sources
5. **Answer Synthesis**: Generates comprehensive response utilizing all selected content

### Output Format
```json
{
  "answer": "Comprehensive answer in expert's voice",
  "main_sources": [21, 65, 77],
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "Explanation of answer confidence"
}
```

## 🌐 Language Validation Phase

### Purpose
Validate language consistency between user query and expert response, translating Russian responses to English when language mismatch is detected.

### Implementation
- **File**: `backend/src/services/language_validation_service.py`
- **Model**: Qwen 2.5-72B Instruct (same as translation service)
- **Translation**: Uses existing TranslationService for consistency
- **Error Handling**: Graceful degradation with fallback to original text

### Key Features

#### Language Detection
- **Query Language Detection**: Uses existing `detect_query_language()` function
- **Response Language Analysis**: Detects language of synthesized expert response
- **Mismatch Detection**: Identifies Russian responses to English queries

#### Translation Process
- **Trigger Condition**: English query + Russian response
- **Translation Service**: Leverages existing TranslationService infrastructure
- **Format Preservation**: Maintains all post links and formatting during translation
- **Quality Assurance**: Uses proven translation pipeline with retry mechanisms

#### Multi-Expert Support
- **Expert Isolation**: Each expert's response validated independently
- **Parallel Processing**: Runs concurrently with other pipeline phases
- **SSE Integration**: Real-time progress updates with expert_id context

### Process Flow
1. **Language Detection**: Analyze query and response languages
2. **Mismatch Check**: Determine if translation is needed (Russian → English)
3. **Translation**: Apply translation service when mismatch detected
4. **Validation**: Ensure translation preserves meaning and formatting
5. **Progress Reporting**: SSE events for validation status updates

### Output Format
```json
{
  "answer": "Translated or original response",
  "original_answer": "Original response before validation",
  "language": "English|Russian|Unknown",
  "validation_applied": true,
  "translation_applied": true,
  "original_detected_language": "Russian"
}
```

### Integration Points
- **Position**: Phase 5, after Reduce phase completion
- **Input**: Expert response from Reduce phase
- **Output**: Validated (and possibly translated) response to Comment Groups phase
- **Parallel Execution**: Runs independently while Comment Groups phase starts

### Configuration
- **Model**: `qwen-2.5-72b` (configurable via environment)
- **Retry Strategy**: 3 attempts with exponential backoff
- **Timeout**: Integrated with existing request timeout settings
- **Error Handling**: Returns original text if translation fails

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

## 🏗️ Response Building Phase

### Purpose
Assemble the final multi-expert response combining main answer, comment insights, and comprehensive metadata.

### Implementation
- **File**: `backend/src/api/simplified_query_endpoint.py`
- **Integration**: Combines outputs from Reduce and Comment Synthesis phases
- **Multi-Expert Support**: Processes responses from all experts

### Process Flow
1. **Collection**: Gather outputs from Reduce phase for all experts
2. **Comment Integration**: Add comment synthesis insights if available
3. **Metadata Assembly**: Include source posts, confidence scores, processing stats
4. **Response Formatting**: Structure final multi-expert response
5. **SSE Transmission**: Stream complete response to client

### Output Format
```json
{
  "experts": [
    {
      "expert_id": "expert_name",
      "answer": "Main synthesized answer",
      "main_sources": [21, 65, 77],
      "confidence": "HIGH",
      "comment_insights": [
        {
          "insight": "Additional perspective from comments",
          "comment_sources": ["post:123|group:456"]
        }
      ],
      "processing_stats": {
        "total_posts_processed": 156,
        "high_posts": 12,
        "medium_posts_selected": 5,
        "processing_time_ms": 4500
      }
    }
  ],
  "query_metadata": {
    "query": "User's original query",
    "total_experts_processed": 3,
    "total_processing_time_ms": 12000
  }
}
```

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
- **Qwen 2.5-72B**: Superior document ranking, relevance scoring, Medium post evaluation, and language validation
- **Gemini 2.0 Flash**: Better context synthesis and instruction following
- **GPT-4o-mini**: Fast and cost-effective for matching tasks

### Performance Characteristics
| Model | Use Case | Cost | Strengths |
|-------|----------|------|-----------|
| Qwen 2.5-72B | Map Phase, Medium Scoring, Language Validation | $0.08/$0.33 | Document ranking, relevance scoring, fine-grained evaluation, translation |
| Gemini 2.0 Flash | Reduce, Comment Synthesis | $0.10/$0.40 | Context synthesis, instruction following |
| GPT-4o-mini | Comment Groups | Fast/cheap | Keyword matching, fast processing |

## 🛠️ Configuration

### Pipeline Parameters
```python
# Map Phase
CHUNK_SIZE = 40  # Posts per chunk
MAX_GLOBAL_RETRIES = 1  # Additional global retry attempts

# Medium Scoring Phase
MEDIUM_SCORE_THRESHOLD = 0.7  # Minimum score threshold
MEDIUM_MAX_SELECTED_POSTS = 5  # Maximum posts to select
MEDIUM_MAX_POSTS = 50  # Memory limit for processing

# Filter Phase
RELEVANCE_THRESHOLD = "HIGH"  # Keep HIGH + selected Medium posts

# Reduce Phase
MAX_POSTS = 50  # Maximum posts for synthesis
USE_PERSONAL_STYLE = True  # Default to personal style

# Comment Groups
DRIFT_CHUNK_SIZE = 20  # Drift groups per API call
MAX_PARALLEL_REQUESTS = 5  # Rate limiting

# Language Validation
LANGUAGE_VALIDATION_MODEL = "qwen-2.5-72b"  # Model for language validation
TRANSLATION_RETRY_ATTEMPTS = 3  # Retry attempts for translation
```

### Model Configuration
```python
DEFAULT_MODELS = {
    "map": "qwen/qwen-2.5-72b-instruct",
    "medium_scoring": "qwen/qwen-2.5-72b-instruct",
    "reduce": "google/gemini-2.0-flash-001",
    "language_validation": "qwen/qwen-2.5-72b-instruct",
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
- **Medium Scoring Service**: `backend/src/services/medium_scoring_service.py`
- **Resolve Service**: `backend/src/services/simple_resolve_service.py`
- **Reduce Service**: `backend/src/services/reduce_service.py`
- **Language Validation Service**: `backend/src/services/language_validation_service.py`
- **Comment Groups**: `backend/src/services/comment_group_map_service.py`
- **Comment Synthesis**: `backend/src/services/comment_synthesis_service.py`

### Integration and Orchestration
- **Main Endpoint**: `backend/src/api/simplified_query_endpoint.py`
- **API Models**: `backend/src/api/models.py`
- **OpenRouter Adapter**: `backend/src/services/openrouter_adapter.py`

### Prompts and Templates
- **Map Prompt**: `backend/prompts/map_prompt.txt`
- **Medium Scoring Prompt**: `backend/prompts/medium_scoring_prompt.txt`
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