---
name: m-implement-english-translation-for-posts
branch: feature/english-translation-for-posts
status: pending
created: 2025-01-24
submodules: []
---

# Implement English Translation for Original Posts

## Problem/Goal
Add English translation functionality for original posts in the right column when queries are made in English. Currently, the system translates expert answers to English but the original posts remain in their source language, creating an inconsistent user experience for English-speaking users.

## Success Criteria
- [ ] English-speaking users can view translated versions of original posts when making English queries
- [ ] Translation works consistently across all experts and posts
- [ ] Original language is preserved and accessible (toggle between original/translated)
- [ ] Translation quality is high and maintains technical accuracy
- [ ] Performance impact is minimal (translations cached when possible)
- [ ] Integration follows existing multilingual architecture patterns

## Context Manifest

### How This Currently Works: Multilingual Architecture & Post Rendering System

**Current Language Detection and Translation System:**

The system already has a sophisticated multilingual architecture built around `language_utils.py` that detects query language and enforces response language consistency across all LLM calls. Here's how it works:

1. **Language Detection** (`language_utils.py:10-60`): Uses character pattern analysis (ASCII vs Cyrillic) and word counting to detect whether queries are in English or Russian. Defaults to Russian for ambiguous cases with sensitive detection thresholds.

2. **Language Enforcement** (`language_utils.py:62-172`): Generates strict language instructions that are prepended to all LLM prompts. When an English query is detected, the system forces English responses regardless of source content language: "USER ASKED IN ENGLISH → YOU MUST RESPOND IN ENGLISH. IGNORE ALL RUSSIAN CONTENT IN SOURCE MATERIALS."

3. **Integration Pattern**: All LLM services use `prepare_prompt_with_language_instruction()` and `prepare_system_message_with_language()` to enforce language consistency:
   - Map Service (Qwen 2.5-72B) - uses `prepare_system_message_with_language()`
   - Reduce Service (Gemini 2.0 Flash) - uses both system message and prompt preparation
   - Comment services also integrate language instructions

**Current Post Rendering System:**

Posts are displayed in the right column of the ExpertAccordion component through this flow:

1. **Post Storage** (`models/post.py`): Posts are stored with `message_text` field containing original content (mostly Russian). The Post model has no translation fields - translations would need to be computed dynamically.

2. **Post Retrieval** (`api/simplified_query_endpoint.py:638-694`): The `/posts/{post_id}` endpoint returns `SimplifiedPostDetailResponse` with `message_text` field. Expert data isolation is enforced through `expert_id` filtering.

3. **Post Display** (`components/PostCard.tsx:178-192`): Posts render using ReactMarkdown with remarkGfm plugin. The `message_text` is displayed directly: `{post.message_text || ''}` within a `<ReactMarkdown>` component.

4. **Post Loading** (`components/ExpertAccordion.tsx:36-67`): When an expert accordion is expanded, posts are fetched via `apiClient.getPostsByIds(expert.main_sources, expert.expert_id)` and stored in local state.

**Model Integration Patterns:**

The system uses a multi-model strategy via OpenRouter:

- **Qwen 2.5-72B** (`map_service.py:31`) - Used in Map phase for document ranking, costs $0.08/$0.33 per 1M tokens. This is the model specified for translation use.
- **Gemini 2.0 Flash** (`reduce_service.py:27`) - Used for answer synthesis
- Model conversion happens via `openrouter_adapter.py:25-62` which maps model names to OpenRouter format

**API Structure for Translation Integration:**

The current API has these relevant endpoints:
- `POST /api/v1/query` - Main query processing pipeline with SSE streaming
- `GET /api/v1/posts/{post_id}` - Individual post retrieval with expert filtering
- Posts are returned through `SimplifiedPostDetailResponse` in `models.py:303-333`

**Frontend State Management:**

Current post state flow:
1. ExpertAccordion maintains `posts: PostWithRelevance[]` state
2. Posts are loaded once when accordion expands via `useEffect`
3. Each post is rendered by PostCard with `telegram_message_id` and `expertId` for DOM element identification
4. No translation state currently exists - this would need to be added

### For New Feature Implementation: English Translation for Original Posts

Since we're implementing English translation functionality for original posts, it will need to integrate with the existing system at these points:

**Translation Service Integration:**
The translation functionality should use Qwen 2.5-72B (already used in Map phase) for consistency and cost-effectiveness. A new translation service should be created following the same patterns as `map_service.py` and `reduce_service.py`, using:
- `create_openrouter_client(api_key)` for OpenRouter API access
- `prepare_system_message_with_language()` for language instruction
- The same retry and error handling patterns

**Query Language Detection Integration:**
The existing `detect_query_language()` function from `language_utils.py` should be used to determine when translation is needed. When English queries are detected:
1. The system should flag that translations are needed for posts
2. Translation requests should be batched for efficiency
3. Results should be cached to optimize performance

**Post Rendering Integration:**
PostCard component (`PostCard.tsx:178-192`) needs modification to:
1. Add toggle functionality between original/translated versions
2. Store translation state alongside original text
3. Maintain the same ReactMarkdown rendering for both versions
4. Preserve DOM ID generation for post reference clicking

**API Enhancement:**
The post retrieval system needs enhancement:
1. `SimplifiedPostDetailResponse` should gain optional `message_text_translated` field
2. `/posts/{post_id}` endpoint should accept optional `translate=true` parameter
3. Batch translation endpoint for processing multiple posts efficiently
4. Integration with existing expert filtering to maintain data isolation

**Caching Strategy:**
Translations should be cached to optimize performance:
1. Consider in-memory caching for frequently accessed translations
2. Database storage option: Add `message_text_en` column to Post model for persistent caching
3. Cache key strategy: `post_id + target_language + content_hash` for cache invalidation
4. Lazy loading: Only translate when posts are actually displayed and translation is requested

**Frontend State Management:**
The translation toggle state needs to be managed:
1. Add `showTranslations: boolean` state to ExpertAccordion or PostCard level
2. Persist translation preference per query session
3. Handle loading states for translation requests
4. Graceful fallback to original text if translation fails

**Performance Considerations:**
1. Batch translate multiple posts simultaneously rather than one-by-one
2. Only translate posts that are actually displayed (right column visible posts)
3. Implement translation debouncing to avoid redundant requests
4. Consider translation priority for HIGH relevance posts first

### Technical Reference Details

#### Component Interfaces & Signatures

**New Translation Service Interface:**
```python
class TranslationService:
    def __init__(self, api_key: str, model: str = "qwen-2.5-72b")

    async def translate_posts(
        self,
        posts: List[Dict[str, Any]],
        target_language: str = "English",
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]

    async def translate_single_post(
        self,
        post_text: str,
        target_language: str = "English"
    ) -> str
```

**Enhanced API Endpoints:**
```python
@router.get("/posts/{post_id}")
async def get_post_detail(
    post_id: int,
    expert_id: Optional[str] = None,
    translate: bool = False,  # New parameter
    db: Session = Depends(get_db)
) -> SimplifiedPostDetailResponse

@router.post("/posts/translate")
async def translate_posts_batch(
    request: TranslatePostsRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_openai_key)
) -> TranslatePostsResponse
```

**Enhanced Pydantic Models:**
```python
class SimplifiedPostDetailResponse(BaseModel):
    # ... existing fields ...
    message_text_translated: Optional[str] = Field(
        default=None,
        description="English translation of the post content"
    )
    translation_available: bool = Field(
        default=False,
        description="Whether translation is available for this post"
    )

class TranslatePostsRequest(BaseModel):
    post_ids: List[int]
    expert_id: str
    target_language: str = "English"

class TranslatePostsResponse(BaseModel):
    translations: Dict[int, str]  # post_id -> translated_text
    failed_posts: List[int]
```

#### Frontend Component Enhancements

**PostCard Props Enhancement:**
```typescript
interface PostCardProps {
  post: PostWithRelevance;
  isExpanded: boolean;
  onToggleComments: () => void;
  isSelected?: boolean;
  expertId?: string;
  showTranslation?: boolean;  // New prop
  translation?: string;       // New prop
  onToggleTranslation?: () => void;  # New callback
}
```

**PostCard State Addition:**
```typescript
const PostCard: React.FC<PostCardProps> = ({
  post, isExpanded, onToggleComments, isSelected = false, expertId,
  showTranslation = false, translation, onToggleTranslation
}) => {
  const displayText = showTranslation && translation ? translation : post.message_text;

  return (
    <div>
      {/* Translation toggle button */}
      <button onClick={onToggleTranslation}>
        {showTranslation ? 'Show Original' : 'Show English'}
      </button>

      {/* Content rendering */}
      <ReactMarkdown>
        {displayText || ''}
      </ReactMarkdown>
    </div>
  );
};
```

#### Data Structures

**Translation Cache Key Pattern:**
```
translation_cache_key = f"post_{post_id}_en_{content_hash[:8]}"
```

**Batch Translation Request Structure:**
```python
translation_batch = {
    "posts": [
        {
            "telegram_message_id": 12345,
            "message_text": "Russian text content",
            "author": "Author name"
        }
        # ... more posts
    ],
    "target_language": "English",
    "context": "User query context for better translation"
}
```

#### Configuration Requirements

**Environment Variables:**
```bash
# Translation-specific settings (can reuse existing)
TRANSLATION_MODEL="qwen-2.5-72b"  # Same as map phase model
TRANSLATION_CACHE_SIZE=1000       # In-memory cache limit
TRANSLATION_BATCH_SIZE=10         # Posts per translation request
```

**Translation Prompt Template:**
```
Translate the following Russian Telegram post to natural English.

Context: This post is relevant to the user's query: "{user_query}"

Post:
{post_text}

Author: {author_name}

Requirements:
1. Translate accurately while preserving technical meaning
2. Keep the original tone and style
3. Preserve any formatting (lists, bold, code blocks)
4. Handle technical terms appropriately
5. If the post contains mixed languages, translate only Russian parts
```

#### File Locations

- **Translation Service**: `backend/src/services/translation_service.py`
- **Translation Prompt**: `backend/prompts/translation_prompt.txt`
- **Enhanced API Models**: `backend/src/api/models.py` (extend existing)
- **Enhanced Post Endpoint**: `backend/src/api/simplified_query_endpoint.py`
- **Frontend PostCard Enhancement**: `frontend/src/components/PostCard.tsx`
- **Frontend ExpertAccordion Enhancement**: `frontend/src/components/ExpertAccordion.tsx`
- **Frontend API Client Enhancement**: `frontend/src/services/api.ts`
- **Frontend Types Enhancement**: `frontend/src/types/api.ts`
- **Database Migration (optional)**: `backend/migrations/009_add_post_translation.sql`

## User Notes
<!-- Any specific notes or requirements from the developer -->
- Use Qwen 2.5-72B (already used in Map phase) for consistency and cost-effectiveness
- Should integrate with existing English query detection system
- Posts are displayed in right column alongside expert responses
- Decision: Use Qwen over GPT-4o-mini for translation

## Work Log
<!-- Updated as work progresses -->
- [2025-01-24] Started task, initial research
