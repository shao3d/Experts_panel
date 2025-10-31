---
name: m-refactor-qwen-32b-cost-optimization
branch: feature/m-refactor-qwen-32b-cost-optimization
status: pending
created: 2025-10-31
---

# Refactor Map and Medium Scoring to Qwen 32B for Cost Optimization

## Problem/Goal
Reduce operational costs by migrating Map Phase and Medium Scoring Phase from Qwen 2.5-72B to Qwen 2.5-32B while maintaining quality and implementing flexible model configuration through environment variables.

## Success Criteria
- [ ] Map Phase successfully uses Qwen 2.5-32B with environment variable MODEL_ANALYSIS
- [ ] Medium Scoring Phase successfully uses Qwen 2.5-32B with environment variable MODEL_ANALYSIS
- [ ] Environment variable configuration allows quick switching between 32B and 72B models
- [ ] All existing prompts for Qwen 72B are compatible with 32B model
- [ ] Response format consistency maintained between 32B and 72B models
- [ ] System provides 75% cost reduction on targeted phases while maintaining quality
- [ ] Quick rollback mechanism available through single environment variable change

## Context Manifest

### How Current Model Configuration Works: Map and Medium Scoring Phases

The system currently uses Qwen 2.5-72B for both Map Phase and Medium Scoring Phase through hardcoded DEFAULT_MODEL constants in each service. The Map Service (`backend/src/services/map_service.py:31`) defines `DEFAULT_MODEL = "qwen-2.5-72b"` and the Medium Scoring Service (`backend/src/services/medium_scoring_service.py:28`) uses the same default. These services are instantiated in the main query pipeline (`backend/src/api/simplified_query_endpoint.py:132,160`) without passing model parameters, so they always use the hardcoded 72B models.

The OpenRouter adapter (`backend/src/services/openrouter_adapter.py:49-50`) already supports both models in its mapping:
```python
"qwen-2.5-72b": "qwen/qwen-2.5-72b-instruct",  # $0.08/$0.33 per 1M
"qwen-2.5-32b": "qwen/qwen-2.5-32b-instruct",  # Smaller, faster variant
```

The environment configuration (`.env.example:92-93`) already defines separate model variables:
```
MODEL_MAP=qwen/qwen-2.5-72b-instruct
MODEL_MEDIUM_SCORING=qwen/qwen-2.5-72b-instruct
```

However, these environment variables are not currently read by the services - they only use hardcoded defaults.

### Prompt Compatibility Analysis: 32B vs 72B

Both services use prompts that should be fully compatible with Qwen 2.5-32B:

**Map Phase Prompt** (`backend/prompts/map_prompt.txt`): Uses structured JSON output format with clear instructions for relevance classification (HIGH/MEDIUM/LOW). The prompt is model-agnostic and relies on standard instruction following capabilities that both 32B and 72B models support equally well.

**Medium Scoring Prompt** (`backend/prompts/medium_scoring_prompt.txt`): Uses markdown format output with specific scoring instructions. The prompt mentions "You are an expert content analyst working with Qwen2.5-72B" in line 1, which should be updated to be model-agnostic. The scoring logic (0.0-1.0 scale, complementarity assessment) is fundamental reasoning that works across model sizes.

Both prompts use the language preparation utilities (`backend/src/utils/language_utils.py`) which automatically detect query language and add appropriate language instructions. This infrastructure is model-agnostic and will work seamlessly with 32B models.

### Current Model Configuration Patterns in Codebase

The system uses multiple model configuration patterns:

1. **Hardcoded DEFAULT_MODEL constants** (current pattern for Map/Medium services)
2. **Environment variable reading** (used by MediumScoringService for thresholds: `MEDIUM_SCORE_THRESHOLD`, `MEDIUM_MAX_SELECTED_POSTS`)
3. **Constructor parameter injection** (all services accept optional `model` parameter)

Other services already use environment variables for model configuration:
- Reduce Service uses `gemini-2.0-flash`
- Comment Groups use `gpt-4o-mini`
- Comment Synthesis uses `gemini-2.0-flash`
- Language Validation uses `qwen-2.5-72b`

The OpenRouter adapter handles model name conversion transparently, so changing from 72B to 32B requires only updating the model name string.

### Service Integration Points and Dependencies

**Map Phase Integration**:
- Called from `process_expert_pipeline()` in `simplified_query_endpoint.py:132`
- Only dependency is the OpenRouter client via `create_openrouter_client()`
- Response format is strict JSON with `relevant_posts` array
- No other services depend on Map's internal model choice

**Medium Scoring Integration**:
- Called conditionally based on MEDIUM posts from Map phase (line 158)
- Uses same OpenRouter client pattern
- Response parsing in `_parse_text_response()` expects markdown format with ID/Score/Reason sections
- Selected posts bypass Resolve phase and go directly to Reduce phase

**Cascade Effects**:
- Both services are independent - changing their models doesn't affect other pipeline phases
- The existing retry mechanisms, error handling, and progress tracking are model-agnostic
- Response format expectations remain the same for both 32B and 72B models

### Environment Variable Usage Patterns

The MediumScoringService demonstrates the proper pattern:
```python
SCORE_THRESHOLD = float(os.getenv("MEDIUM_SCORE_THRESHOLD", "0.7"))
MAX_SELECTED_POSTS = int(os.getenv("MEDIUM_MAX_SELECTED_POSTS", "5"))
```

For model configuration, the pattern should be:
```python
DEFAULT_MODEL = os.getenv("MODEL_ANALYSIS", "qwen-2.5-72b")
```

The main environment file (`.env.example:92-96`) already includes comprehensive model configuration options that just need to be wired into the services.

### Implementation Requirements for Cost Optimization

**Minimal Changes Needed**:
1. Update `MapService.__init__()` to read from `MODEL_ANALYSIS` environment variable
2. Update `MediumScoringService.__init__()` to read from same `MODEL_ANALYSIS` variable
3. Update Medium Scoring prompt to remove model-specific reference
4. Update service instantiation in pipeline to pass model parameter

**Rollback Mechanism**: Single environment variable change `MODEL_ANALYSIS=qwen-2.5-72b` immediately restores 72B models without code changes.

**Cost Impact**: Qwen 2.5-32B costs approximately 75% less than 72B while maintaining similar quality for document ranking and scoring tasks.

### Technical Reference Details

#### Service Interfaces & Signatures

**MapService Constructor** (`backend/src/services/map_service.py:33-38`):
```python
def __init__(
    self,
    api_key: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    model: str = DEFAULT_MODEL,  # Currently hardcoded
    max_parallel: int = None
):
```

**MediumScoringService Constructor** (`backend/src/services/medium_scoring_service.py:34`):
```python
def __init__(self, api_key: str, model: str = DEFAULT_MODEL):  # Currently hardcoded
```

**Current Instantiation Pattern** (`simplified_query_endpoint.py`):
```python
map_service = MapService(api_key=api_key, max_parallel=5)  # No model passed
scoring_service = MediumScoringService(api_key)  # No model passed
```

#### Data Structures

**Map Phase Response Format**:
```json
{
  "relevant_posts": [
    {
      "telegram_message_id": <integer>,
      "relevance": "<HIGH|MEDIUM|LOW>",
      "reason": "<explanation>"
    }
  ],
  "chunk_summary": "<description>"
}
```

**Medium Scoring Response Format**:
```markdown
=== POST X ===
ID: <telegram_message_id>
Score: <0.0-1.0>
Reason: <explanation>
```

#### Configuration Requirements

**New Environment Variable**:
```bash
# Analysis models (Map + Medium Scoring phases)
MODEL_ANALYSIS=qwen/qwen-2.5-32b-instruct  # Target: 32B for cost optimization
# MODEL_ANALYSIS=qwen/qwen-2.5-72b-instruct  # Rollback: 72B if quality issues
```

**Existing Compatible Variables**:
```bash
MEDIUM_SCORE_THRESHOLD=0.7
MEDIUM_MAX_SELECTED_POSTS=5
MEDIUM_MAX_POSTS=50
```

#### File Locations

- **Map Service**: `backend/src/services/map_service.py:31` (DEFAULT_MODEL constant)
- **Medium Scoring Service**: `backend/src/services/medium_scoring_service.py:28` (DEFAULT_MODEL constant)
- **Pipeline Integration**: `backend/src/api/simplified_query_endpoint.py:132,160` (service instantiation)
- **Medium Scoring Prompt**: `backend/prompts/medium_scoring_prompt.txt:1` (model reference to update)
- **Environment Configuration**: `.env.example:92-96` (model variables already defined)
- **OpenRouter Mapping**: `backend/src/services/openrouter_adapter.py:49-50` (both models supported)

## User Notes
Key requirements from developer:
- Implement convenient mechanism for quick model switching in configuration
- Ensure all prompts for Qwen 72B are compatible with 32B model
- Maintain response format consistency between 32B and 72B models
- Target 75% cost reduction on Map and Medium Scoring phases
- Provide quick rollback capability if quality issues arise

## Work Log
<!-- Updated as work progresses -->
- [2025-10-31] Task created, initial analysis completed
