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
- **Model**: Qwen 2.5-72B/32B Instruct (configurable via MODEL_ANALYSIS environment variable)
- **Cost**: $0.08/$0.33 per 1M tokens (72B) or ~75% cost reduction with 32B
- **Chunk Size**: 40 posts per chunk

### Key Features

#### Robust Retry Mechanism (NEW 2025-10-15)
Two-layer retry strategy ensures reliable processing:

The retry mechanism is defined using a `@retry` decorator directly in the `map_service.py` file. See the implementation for specific parameters.

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

The service returns a dictionary containing a list of relevant posts, each with a `post_id`, `relevance` level, and a `reason`. The specific implementation can be found in the `process` method of `backend/src/services/map_service.py`.

## 🎯 Medium Scoring Phase

### Purpose
Intelligently score and select Medium relevance posts using hybrid reranking to identify valuable content that might be missed by simple HIGH/LOW filtering.

### Implementation
- **File**: `backend/src/services/medium_scoring_service.py`
- **Model**: Qwen 2.5-72B/32B Instruct (configurable via MODEL_ANALYSIS environment variable)
- **Strategy**: Hybrid threshold + top-K selection
- **Memory Management**: Maximum 50 Medium posts processed

### Hybrid Reranking Algorithm

#### Two-Stage Selection Process
1. **Threshold Filtering**: Score ≥ 0.7 passes first filter
2. **Top-K Selection**: From filtered posts, select top-5 by highest score

These parameters are defined as environment variables with defaults. See `MEDIUM_SCORE_THRESHOLD` (default: 0.7), `MEDIUM_MAX_SELECTED_POSTS` (default: 5), and `MEDIUM_MAX_POSTS` (default: 50) in `backend/src/services/medium_scoring_service.py` for implementation details.

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

The service returns a list of selected medium posts, each represented as a dictionary containing the original post data along with a `score` and `score_reason`. For the exact structure, see the implementation of the `score_medium_posts` method in `backend/src/services/medium_scoring_service.py`.

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

The service's output is incorporated into the `ExpertResponse` Pydantic model (`backend/src/api/models.py`), which includes the `answer`, a list of `main_sources`, and a `confidence` level.

## 🌐 Language Validation Phase

### Purpose
Validate language consistency between user query and expert response, translating Russian responses to English when language mismatch is detected.

### Implementation
- **File**: `backend/src/services/language_validation_service.py`
- **Model**: Qwen 2.5-72B/32B Instruct (configurable via MODEL_ANALYSIS environment variable)
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

The service returns a dictionary containing the validated `answer` and several metadata fields, such as `translation_applied` and `original_detected_language`. For the exact structure, see the `process` method in `backend/src/services/language_validation_service.py`.

### Integration Points
- **Position**: Phase 5, after Reduce phase completion
- **Input**: Expert response from Reduce phase
- **Output**: Validated (and possibly translated) response to Comment Groups phase
- **Parallel Execution**: Runs independently while Comment Groups phase starts

### Configuration
- **Model**: `qwen-2.5-72b` (configurable via MODEL_ANALYSIS environment variable)
- **Cost Optimization**: Use `qwen-2.5-32b` for 60-70% cost reduction
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

The final SSE 'complete' event contains the response payload. The structure of this payload is defined by the `MultiExpertQueryResponse` Pydantic model located in `backend/src/api/models.py`. This model contains a list of `ExpertResponse` objects, one for each expert.

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
- **Qwen 2.5-72B/32B**: Superior document ranking, relevance scoring, Medium post evaluation, and language validation (configurable via MODEL_ANALYSIS)
  - **Cost Optimization**: 32B model provides 60-70% cost reduction with <2% quality loss
  - **Maximum Quality**: 72B model for highest accuracy requirements
- **Gemini 2.0 Flash**: Better context synthesis and instruction following
- **GPT-4o-mini**: Fast and cost-effective for matching tasks

### Performance Characteristics
| Model | Use Case | Cost | Strengths |
|-------|----------|------|-----------|
| Qwen 2.5-72B/32B | Map Phase, Medium Scoring, Translation, Language Validation | $0.08/$0.33 (72B) or ~75% reduction (32B) | Document ranking, relevance scoring, fine-grained evaluation, translation |
| Gemini 2.0 Flash | Reduce, Comment Synthesis | $0.10/$0.40 | Context synthesis, instruction following |
| GPT-4o-mini | Comment Groups | Fast/cheap | Keyword matching, fast processing |

## 🛠️ Configuration

### Pipeline Parameters
Parameters such as chunk sizes, thresholds, and limits are defined as constants within their respective service files in `backend/src/services/`. For example, `MEDIUM_SCORE_THRESHOLD` is defined in `medium_scoring_service.py`.

### Model Configuration
Default models for each pipeline phase are configured using environment variables. The primary source for this configuration is `backend/src/config.py`, which defines variables such as `MODEL_MAP_PRIMARY`, `MODEL_SYNTHESIS_PRIMARY`, etc.

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

The application logs provide valuable debugging information. To monitor performance and errors, check the log files (defined in `config.py` as `BACKEND_LOG_FILE`) for messages containing terms like 'Global retry', 'processing_time_ms', and 'failed'.

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