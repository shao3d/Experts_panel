# Task: Fix Comment Groups Security & Quality Issues

**Priority**: HIGH
**Status**: Completed
**Branch**: feature/simplified-architecture (continue on same branch)
**Created**: 2025-10-05
**Completed**: 2025-10-06
**Estimated**: 3-4 hours
**Actual**: 3 hours

## Context

Code review of `telegram-comments-integration` implementation found:
- **2 CRITICAL security issues** (SQL injection risk, prompt injection)
- **3 HIGH priority bugs** (session leaks, duplicate comments, inconsistency)
- **7 MEDIUM issues** (performance, type safety, config)
- **5 LOW issues** (code quality)

Full review in work log below.

## Success Criteria

### CRITICAL Fixes (MUST DO):
- [x] Fix SQL injection risk in `comment_group_map_service.py:92` - validate `exclude_post_ids` ✅
- [x] Fix prompt injection risk in `comment_group_map_service.py:54-64` - validate path & permissions ✅

### HIGH Fixes (MUST DO):
- [x] Document session lifecycle in `CommentGroupMapService.process()` ✅
- [x] Add UNIQUE constraint on `telegram_comment_id` in Comment model ✅
- [x] Align `include_comment_groups` default (backend=false, frontend=false for MVP) ✅

### MEDIUM Fixes (SHOULD DO):
- [x] Add `channel_username` to AnchorPost response (remove hardcode) ✅
- [x] Add compound index on `(telegram_comment_id, post_id)` ✅
- [x] Fix progress event schema - add `event_type` field ✅
- [x] Set `DEFAULT_MAX_PARALLEL = 5` for comment groups service ✅
- [x] Use ISO format for dates in anchor post (`isoformat()`) ✅
- [x] Add validation for `anchor_post` field from GPT response ✅
- [x] Fix frontend date parsing to handle ISO format ✅

### LOW Fixes (NICE TO HAVE):
- [x] Use stable React keys in CommentGroupsList ✅
- [ ] Improve exception handling in `telegram_comments_fetcher.py` (deferred)
- [ ] Document chunk size rationale (20 vs 40) (deferred)
- [ ] Add model name to log messages (deferred)

## Testing Checklist

After fixes, test:
- [x] Query with 0 relevant posts → Pipeline B shouldn't crash ✅
- [x] Query with ALL posts relevant → empty exclude list works ✅
- [x] Malformed GPT response → graceful error handling ✅
- [x] Run import twice → no duplicate comments (unique constraint) ✅
- [x] Check Telegram links → work with real channel username ✅

## Files to Modify

1. `backend/src/services/comment_group_map_service.py` - security, validation, defaults
2. `backend/src/models/comment.py` - add unique constraint
3. `backend/src/api/models.py` - add channel_username to AnchorPost
4. `backend/src/api/simplified_query_endpoint.py` - validation, defaults
5. `backend/src/data/telegram_comments_fetcher.py` - exception handling
6. `frontend/src/App.tsx` - align defaults
7. `frontend/src/components/CommentGroupsList.tsx` - React keys, date parsing

## Code Review Findings

### CRITICAL Issues

#### 1. SQL Injection Risk (comment_group_map_service.py:92)
```python
# BEFORE (UNSAFE):
if exclude_post_ids:
    query = query.filter(
        Post.telegram_message_id.notin_(exclude_post_ids)
    )

# AFTER (SAFE):
if exclude_post_ids:
    validated_ids = []
    for post_id in exclude_post_ids:
        if not isinstance(post_id, int) or post_id <= 0:
            logger.warning(f"Invalid post_id: {post_id}")
            continue
        validated_ids.append(post_id)

    if validated_ids:
        query = query.filter(
            Post.telegram_message_id.notin_(validated_ids)
        )
```

#### 2. Prompt Injection Risk (comment_group_map_service.py:54-64)
```python
# Add validation:
def _load_prompt_template(self) -> Template:
    try:
        prompt_dir = Path(__file__).parent.parent.parent / "prompts"
        prompt_path = prompt_dir / "comment_group_map_prompt.txt"

        # Prevent path traversal
        if not prompt_path.resolve().is_relative_to(prompt_dir.resolve()):
            raise ValueError(f"Invalid prompt path: {prompt_path}")

        # Check permissions (not world-writable)
        if prompt_path.stat().st_mode & 0o002:
            logger.error(f"Prompt file is world-writable: {prompt_path}")
            raise PermissionError("Unsafe prompt file permissions")

        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Validate required placeholders
        if "$query" not in content or "$groups" not in content:
            raise ValueError("Prompt template missing required placeholders")

        return Template(content)
```

### HIGH Issues

#### 3. Session Lifecycle Documentation
Add to docstring:
```python
async def process(
    self,
    query: str,
    db: Session,  # NOTE: Caller MUST manage session lifecycle
    exclude_post_ids: Optional[List[int]] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """Process all comment groups to find relevant ones.

    IMPORTANT: This method does NOT close the db session. The caller
    is responsible for session lifecycle management.
```

#### 4. Unique Constraint on telegram_comment_id
```python
# In Comment model:
__table_args__ = (
    Index('idx_post_created', 'post_id', 'created_at'),
    Index('idx_telegram_comment_unique',
          'telegram_comment_id',
          unique=True,
          postgresql_where=text("telegram_comment_id IS NOT NULL"))
)
```

#### 5. Align Defaults
Backend already has `include_comment_groups: Optional[bool] = Field(default=False)`

Frontend should match:
```typescript
// In App.tsx:
{ query, stream_progress: true, include_comments: true, include_comment_groups: false }
```

### MEDIUM Issues

#### 6. Channel Username (Remove Hardcode)
Add to AnchorPost model:
```python
class AnchorPost(BaseModel):
    telegram_message_id: int
    message_text: str
    created_at: str
    author_name: str
    channel_username: str  # NEW
```

Populate in service:
```python
"channel_username": post.channel_name  # Or use mapping logic
```

#### 7. Compound Index
```python
Index('idx_telegram_comments', 'telegram_comment_id', 'post_id')
```

#### 8. Progress Event Schema
```python
await progress_callback({
    "event_type": "progress",  # ADD THIS
    "phase": "comment_groups",
    "status": "processing",
    "message": f"...",
    "data": {"chunk": chunk_index}
})
```

#### 9. Rate Limiting
```python
DEFAULT_MAX_PARALLEL = 5  # Add class constant

def __init__(self, ..., max_parallel: int = DEFAULT_MAX_PARALLEL):
```

#### 10. ISO Date Format
```python
"created_at": post.created_at.isoformat(),  # Not strftime
```

#### 11. Validate anchor_post
```python
anchor_post_data = group.get("anchor_post")
if not anchor_post_data:
    logger.error(f"Group missing anchor_post: {group}")
    continue
```

#### 12. Frontend Date Parsing
Already handles ISO format: `new Date(group.anchor_post.created_at)`

### LOW Issues

#### 13-17. See code review output above

## Notes

- **MVP Philosophy**: Fix security & critical bugs. MEDIUM/LOW can wait.
- **Consistency**: Match patterns from `map_service.py`, `reduce_service.py`
- **No Over-Engineering**: Simple validation, clear error messages
- **Test After Each Fix**: Don't break existing functionality

## References

- Code review output: See work log below
- Existing patterns: `backend/src/services/map_service.py`
- Error handling: `backend/src/api/simplified_query_endpoint.py`

---

## Work Log

### Code Review Findings (2025-10-05)

**Files Reviewed**: 9 (6 backend, 3 frontend)
- backend/src/services/comment_group_map_service.py
- backend/prompts/comment_group_map_prompt.txt
- backend/src/api/models.py
- backend/src/api/simplified_query_endpoint.py
- backend/src/models/comment.py
- backend/src/data/telegram_comments_fetcher.py
- frontend/src/types/api.ts
- frontend/src/components/CommentGroupsList.tsx
- frontend/src/App.tsx

**Summary**: Implementation is functional but has security & quality issues that must be addressed before production.

**Severity Breakdown**:
- CRITICAL: 2 (SQL injection, prompt injection)
- HIGH: 3 (session leaks, duplicates, defaults)
- MEDIUM: 7 (performance, type safety)
- LOW: 5 (code quality)

### Implementation (2025-10-06)

**All CRITICAL and HIGH issues fixed:**
- ✅ SQL injection protection with input validation (comment_group_map_service.py:106-118)
- ✅ Prompt injection protection with path/permission checks (comment_group_map_service.py:61-75)
- ✅ Session lifecycle properly documented (comment_group_map_service.py:263-273)
- ✅ UNIQUE constraint on telegram_comment_id (comment.py:43)
- ✅ Defaults aligned: include_comment_groups=false (models.py:44-47)

**All MEDIUM issues fixed:**
- ✅ AnchorPost.channel_username added (models.py:103-106, removes hardcode)
- ✅ Compound index idx_telegram_comments (comment.py:44)
- ✅ ProgressEvent.event_type field added (models.py:194)
- ✅ DEFAULT_MAX_PARALLEL = 5 set (comment_group_map_service.py:32)
- ✅ ISO date format for API responses (comment_group_map_service.py:130)
- ✅ anchor_post validation in aggregation (comment_group_map_service.py:336-342)
- ✅ Frontend handles ISO dates correctly (CommentGroupsList.tsx:153)

**LOW priority items:**
- ✅ Stable React keys (parent_telegram_message_id) (CommentGroupsList.tsx:142)
- ⏸️ Exception handling improvements (deferred to future)
- ⏸️ Chunk size documentation (deferred to future)
- ⏸️ Model name in logs (deferred to future)

**Files Modified**: 9
- backend/src/services/comment_group_map_service.py
- backend/src/models/comment.py
- backend/src/api/models.py
- backend/src/api/simplified_query_endpoint.py
- frontend/src/components/CommentGroupsList.tsx
- frontend/src/App.tsx
- backend/pyproject.toml (dependencies)
- backend/uv.lock (lock file)
- CLAUDE.md (documentation)

**Testing**: All test scenarios passed
- Empty comment groups handled gracefully
- Empty exclude_post_ids works correctly
- Malformed responses caught with validation
- Duplicate prevention via unique constraint
- Telegram links work with real channel usernames

**Result**: Production-ready implementation with all security issues resolved.
