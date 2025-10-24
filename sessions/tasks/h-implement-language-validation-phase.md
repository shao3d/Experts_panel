---
name: h-implement-language-validation-phase
branch: feature/h-implement-language-validation-phase
status: pending
created: 2025-01-25
---

# Language Validation Phase Implementation

## Problem/Goal
After the Reduce phase, expert responses should be validated for language consistency with the user query. Despite existing dual language instructions in Gemini and Qwen, models sometimes respond in Russian instead of English when they see Russian language content in posts.

This task implements a new Language Validation phase that:
1. Checks if response language matches query language using existing `detect_query_language()`
2. Translates Russian responses to English only when needed
3. Preserves all post links and formatting during translation
4. Runs parallel to Comment Groups phase with SSE progress tracking

## Success Criteria
- [ ] Language validation service implemented using `detect_query_language()`
- [ ] Russian → English translation via Qwen 2.5-72B only when mismatch detected
- [ ] Translation preserves all post links and formatting exactly
- [ ] Integrated into pipeline parallel to Comment Groups with proper SSE
- [ ] All experts processed independently with language validation
- [ ] Testing confirms English queries always return English responses

## Context Manifest

### How This Currently Works: Seven-Phase Pipeline Architecture

The Experts Panel implements a sophisticated **seven-phase pipeline** for processing user queries with multi-expert support and comprehensive content analysis. Here's how the current system works:

**Phase 1: Map Phase (Relevance Detection)**
- **Service**: `backend/src/services/map_service.py`
- **Model**: Qwen 2.5-72B Instruct via OpenRouter
- **Purpose**: Semantic search through expert posts to find relevant content
- **Flow**: The MapService processes posts in chunks of 40, classifying each as HIGH/MEDIUM/LOW relevance. It includes a robust two-layer retry mechanism with 95%+ recovery rate for failed chunks. The service uses `prepare_system_message_with_language()` from `language_utils.py` to enforce response language consistency with the query language.

**Phase 2: Medium Scoring Phase (Hybrid Reranking)**
- **Service**: `backend/src/services/medium_scoring_service.py`
- **Model**: Qwen 2.5-72B Instruct
- **Purpose**: Intelligent scoring and selection of Medium relevance posts
- **Flow**: Medium posts undergo hybrid reranking with two-stage selection: score ≥ 0.7 threshold, then top-5 selection by highest score. Maximum 50 Medium posts processed for memory efficiency.

**Phase 3: Differential Resolve Phase (Context Expansion)**
- **Service**: `backend/src/services/simple_resolve_service.py`
- **Strategy**: Database-only approach (no LLM evaluation)
- **Flow**: HIGH posts are processed through Resolve phase with linked posts (depth 1 expansion), while selected Medium posts bypass Resolve and go directly to Reduce phase. This differential processing optimizes both quality and efficiency.

**Phase 4: Reduce Phase (Answer Synthesis)**
- **Service**: `backend/src/services/reduce_service.py`
- **Model**: Gemini 2.0 Flash
- **Purpose**: Synthesize comprehensive answer using all selected content
- **Flow**: The ReduceService combines HIGH posts (with linked context) and selected Medium posts, limiting to maximum 50 posts. It uses `prepare_system_message_with_language()` and `prepare_prompt_with_language_instruction()` from language_utils.py for language enforcement. Includes fact validation via `FactValidator` to ensure referenced posts exist.

**Phase 5: Comment Groups Phase (Parallel Processing)**
- **Service**: `backend/src/services/comment_group_map_service.py`
- **Model**: GPT-4o-mini
- **Purpose**: Find relevant comment discussions using pre-analyzed drift matching
- **Flow**: Runs AFTER Reduce phase, excludes main_sources from Reduce phase, processes in parallel with other phases. Uses two-phase architecture: offline drift analysis (`analyze_drift.py`) and online query-time matching.

**Phase 6: Comment Synthesis Phase (Insight Extraction)**
- **Service**: `backend/src/services/comment_synthesis_service.py`
- **Model**: Gemini 2.0 Flash
- **Purpose**: Extract complementary insights from relevant comment groups
- **Flow**: Only triggers when HIGH comment groups exist, focuses on content not covered in main answer, prohibits `[post:ID]` references to prevent UI confusion.

**Phase 7: Response Building (Final Assembly)**
- **Service**: `backend/src/api/simplified_query_endpoint.py`
- **Purpose**: Assemble final multi-expert response with comprehensive metadata
- **Flow**: Combines outputs from Reduce and Comment Synthesis phases, includes processing stats, confidence scores, and source information.

### Multi-Expert Parallel Processing Architecture

The system processes all experts in parallel using async tasks with individual SSE progress tracking:

**Expert Pipeline Processing (`process_expert_pipeline` function)**
- Each expert gets isolated data via `expert_id` filtering
- All phases execute sequentially per expert, but experts run in parallel
- Progress callbacks include `expert_id` for tracking
- SSE events stream real-time progress via `event_generator_parallel`

**SSE Streaming Pattern**
- Progress events use `ProgressEvent` model from `api/models.py`
- Events include: `event_type`, `phase`, `status`, `message`, `data` with expert context
- Queue-based event management prevents memory leaks (maxsize=100)
- JSON sanitization via `sanitize_for_json()` prevents frontend parsing errors

### Language Detection and Enforcement System

**Language Detection (`backend/src/utils/language_utils.py`)**
- **`detect_query_language(query)`**: Analyzes character patterns (ASCII vs Cyrillic), counts words, defaults to Russian for ambiguous cases
- **`get_language_instruction(query)`**: Generates strict language enforcement instructions in English or Russian
- **`prepare_system_message_with_language()`**: Prepends language instruction to system messages
- **`prepare_prompt_with_language_instruction()`**: Prepends language instruction to prompts

**Integration Pattern Across Services**
All LLM services use language enforcement:
```python
from ..utils.language_utils import prepare_system_message_with_language, prepare_prompt_with_language_instruction

# System message approach (preferred)
enhanced_system = prepare_system_message_with_language(base_system, query)

# Prompt prepending approach (fallback)
enhanced_prompt = prepare_prompt_with_language_instruction(prompt_template, query)
```

### Translation Service Architecture

**TranslationService (`backend/src/services/translation_service.py`)**
- **Model**: Qwen 2.5-72B Instruct via OpenRouter
- **Prompt Template**: `backend/prompts/translation_prompt.txt`
- **Purpose**: Translate Russian posts to English for English queries
- **Features**: Preserves all links `[text](url)`, markdown formatting, technical terms, and tone

**Translation Flow**
1. **Language Check**: `should_translate(query)` uses `detect_query_language()` to check if translation needed
2. **Batch Processing**: `translate_posts_batch()` processes up to 5 posts in parallel with semaphore limiting
3. **Progress Tracking**: Optional progress callbacks for real-time updates
4. **Error Handling**: Graceful degradation with original text if translation fails

### Database and Models

**Database Configuration**
- **Engine**: SQLAlchemy 2.0 with SQLite (local) or PostgreSQL (production)
- **Session**: `SessionLocal` factory for database connections
- **Expert Isolation**: All tables have `expert_id` field for data separation

**Key Models (`backend/src/models/`)**
- **Post Model**: Core content storage with `telegram_message_id`, `expert_id`, `message_text`
- **Comment Model**: Comment responses with foreign key to posts
- **Link Model**: Post relationships (REPLY, FORWARD, MENTION types)

### API Response Models

**Response Structure (`backend/src/api/models.py`)**
- **`ExpertResponse`**: Single expert output with answer, sources, confidence, processing stats
- **`MultiExpertQueryResponse`**: Container for multiple expert responses
- **`ProgressEvent`**: SSE event model with event_type, phase, status, message, data
- **`QueryRequest`**: Input model with query, filters, and options

### For New Feature Implementation: Language Validation Phase Integration

Since we're implementing a new Language Validation phase, it will need to integrate with the existing seven-phase pipeline at these specific points:

**Pipeline Integration Point**
The new phase should be inserted **after Phase 4 (Reduce) and before Phase 5 (Comment Groups)**, running **parallel to Comment Groups phase** with proper SSE tracking.

**Integration Requirements:**

1. **Pipeline Orchestration (`simplified_query_endpoint.py`)**
   - Add new phase in `process_expert_pipeline()` after Reduce phase completion
   - Create parallel task structure similar to Comment Groups phase
   - Ensure proper progress callback with `expert_id` inclusion
   - Handle phase failure gracefully without breaking overall pipeline

2. **Service Structure (`backend/src/services/language_validation_service.py`)**
   - Create new service following established patterns
   - Use existing `detect_query_language()` function for language detection
   - Integrate with `TranslationService` for Russian→English translation
   - Implement progress tracking with callback support

3. **SSE Progress Tracking**
   - Add phase-specific events: "language_validation_start", "language_validation_progress", "language_validation_complete"
   - Follow existing naming pattern: `[expert_id] Phase status message`
   - Include validation results in event data: original_language, validation_result, translation_applied

4. **Translation Integration**
   - Leverage existing `TranslationService` infrastructure
   - Use same prompt template pattern as post translation
   - Apply link and formatting preservation requirements
   - Handle translation errors with fallback to original text

5. **Response Model Updates**
   - No changes needed to existing models if phase runs transparently
   - Response language should be validated and potentially modified before comment groups processing
   - Maintain compatibility with existing frontend SSE parsing

**Critical Integration Points:**

- **Language Detection**: Must reuse existing `detect_query_language()` - no duplicate implementation
- **Translation**: Must use existing `TranslationService.translate_single_post()` method
- **Progress Events**: Must follow existing SSE structure with expert_id context
- **Error Handling**: Must not break pipeline - graceful degradation if validation/translation fails
- **Parallel Processing**: Must run concurrently with Comment Groups to avoid performance impact

**Architectural Constraints:**
- Must maintain expert isolation via `expert_id` filtering
- Must preserve all post links and formatting during translation
- Must only translate Russian → English when mismatch detected (no other language combinations)
- Must use Qwen 2.5-72B for translation consistency with existing services
- Must provide real-time progress updates via SSE with proper expert context

### Technical Reference Details

#### Component Interfaces & Signatures

**Language Detection Functions**
```python
def detect_query_language(query: str) -> str:
    """Returns 'English' or 'Russian' based on character/word analysis"""

def get_language_instruction(query: str) -> str:
    """Returns strict language enforcement instructions"""
```

**Translation Service Interface**
```python
class TranslationService:
    def __init__(self, api_key: str, model: str = "qwen-2.5-72b")

    async def translate_single_post(self, post_text: str, author_name: str = "Unknown") -> str:
        """Translate Russian post text to English preserving formatting"""

    def should_translate(self, query: Optional[str]) -> bool:
        """Check if posts should be translated based on query language"""
```

**Pipeline Progress Callback Pattern**
```python
async def progress_callback(data: dict):
    """Standard pattern used by all services"""
    # data contains: phase, status, message, expert_id, processing details
```

**Service Class Structure Template**
```python
class LanguageValidationService:
    def __init__(self, api_key: str):
        self.client = create_openrouter_client(api_key=api_key)
        self.model = convert_model_name("qwen-2.5-72b")

    async def process(
        self,
        answer: str,
        query: str,
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Main processing method following established patterns"""
```

#### Data Structures

**Progress Event Format**
```json
{
    "event_type": "progress|phase_start|phase_complete|error",
    "phase": "language_validation",
    "status": "starting|processing|completed|error",
    "message": "[expert_id] Language validation status message",
    "data": {
        "expert_id": "expert_name",
        "original_language": "Russian",
        "validation_result": "mismatch_detected",
        "translation_applied": true,
        "original_answer": "...",
        "validated_answer": "..."
    }
}
```

**Service Response Format**
```python
{
    "answer": "validated/translated answer",
    "original_answer": "original answer before validation",
    "language": "English",
    "validation_applied": True,
    "translation_applied": True,
    "original_detected_language": "Russian"
}
```

#### Configuration Requirements

**Environment Variables**
- `OPENAI_API_KEY`: Required for OpenRouter access
- `MEDIUM_SCORE_THRESHOLD`: Current threshold for Medium posts (0.7) - might need language-specific tuning

**Model Configuration**
- **Language Detection**: No additional models (uses existing `language_utils.py`)
- **Translation**: Qwen 2.5-72B via OpenRouter (same as Map and Medium Scoring)
- **Prompt**: May need dedicated language validation prompt template

#### File Locations

**Service Implementation**
- **Main Service**: `backend/src/services/language_validation_service.py`
- **Integration**: `backend/src/api/simplified_query_endpoint.py` (around line 280-300 after Reduce phase)

**Configuration and Prompts**
- **Prompt Template**: `backend/prompts/language_validation_prompt.txt` (if needed)
- **Language Utils**: `backend/src/utils/language_utils.py` (existing)

**Test Infrastructure**
- **Unit Tests**: `backend/tests/test_language_validation_service.py` (optional)
- **Integration**: Test via existing query endpoint with SSE observation

**Database Considerations**
- No new database tables required
- Language validation is in-memory operation
- Could store validation metrics in existing log tables (future enhancement)

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
