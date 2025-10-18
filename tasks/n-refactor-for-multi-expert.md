# Task: Refactor Pipeline for Multi-Expert Architecture

**Created:** 2025-10-10
**Status:** pending
**Branch:** feature/multi-expert-refactor
**Priority:** CRITICAL

## Objective

Refactor the existing Refat pipeline to properly support multi-expert architecture by adding `expert_id` filtering at all critical points. Ensure NO mixing of posts between different experts.

## Background

Current system loads ALL posts from database without filtering by expert. This will cause posts from multiple experts to be mixed together when we add the second expert (AI Architect).

**Critical Issue:** Without expert_id filtering, the Map phase will analyze posts from ALL experts together, Resolve will add linked posts from other experts, and Comment Groups will analyze comments from all channels.

## Audit Findings

Full system audit completed on 2025-10-10. Key findings:

**Components that DON'T need changes:**
- ✅ Map Service - works with data passed to it
- ✅ Reduce Service - works with enriched data
- ✅ Comment Synthesis Service - works with filtered groups

**Components that NEED changes:**
- 🚨 Query Endpoint (lines 114, 566) - entry point, loads ALL posts
- 🚨 Resolve Service (lines 43, 70, 102) - can add posts from other experts via links
- 🚨 Comment Groups Service (line 99) - analyzes ALL comment groups
- 🔧 Import scripts - need to set expert_id on new data

## Requirements

### 1. Database Changes
**File:** `backend/migrations/003_add_expert_id.sql`

```sql
-- Migration 003: Add expert_id field to posts table
ALTER TABLE posts ADD COLUMN expert_id VARCHAR(50);
CREATE INDEX idx_posts_expert_id ON posts(expert_id);
UPDATE posts SET expert_id = 'refat' WHERE channel_id = '2273349814';

-- Verify
SELECT 'Migration 003 completed' as status,
    COUNT(*) as total_posts,
    COUNT(CASE WHEN expert_id IS NOT NULL THEN 1 END) as posts_with_expert_id,
    COUNT(CASE WHEN expert_id = 'refat' THEN 1 END) as refat_posts
FROM posts;
```

**File:** `backend/src/models/post.py`

Add after line 22 (after channel_name):
```python
# Expert identification
expert_id = Column(String(50), nullable=True, index=True)
```

### 2. Query Endpoint (CRITICAL - Entry Point)
**File:** `backend/src/api/simplified_query_endpoint.py`

**Line 114 (SSE path):**
```python
# BEFORE:
query = db.query(Post).order_by(Post.created_at.desc())

# AFTER:
expert_id = 'refat'  # Hardcode for now, will parameterize in task o-add-second-expert
query = db.query(Post).filter(Post.expert_id == expert_id).order_by(Post.created_at.desc())
```

**Line 566 (non-SSE path):** Same change as above

**Pass expert_id to services:**
```python
# Line 215 - Resolve service
resolve_results = await resolve_service.process(
    relevant_posts=filtered_posts,
    query=request.query,
    expert_id=expert_id,  # NEW
    progress_callback=resolve_progress_callback
)

# Line 137 - Comment Groups service
comment_group_results = await comment_group_service.process(
    query=request.query,
    db=db,
    expert_id=expert_id,  # NEW
    exclude_post_ids=main_sources,
    progress_callback=comment_group_progress_callback
)
```

### 3. Resolve Service (CRITICAL - Link Expansion)
**File:** `backend/src/services/simple_resolve_service.py`

**Method signature (line 116):**
```python
async def process(
    self,
    relevant_posts: List[Dict[str, Any]],
    query: str,
    expert_id: str,  # NEW parameter
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
```

**Add expert_id filtering to 3 DB queries:**

Line 43-45:
```python
posts = db.query(Post).filter(
    Post.telegram_message_id.in_(telegram_message_ids),
    Post.expert_id == expert_id  # NEW
).all()
```

Line 70-72:
```python
posts = db.query(Post).filter(
    Post.telegram_message_id.in_(initial_post_ids),
    Post.expert_id == expert_id  # NEW
).all()
```

Line 102-104:
```python
linked_posts = db.query(Post).filter(
    Post.post_id.in_(linked_db_ids),
    Post.expert_id == expert_id  # NEW
).all()
```

**Pass expert_id through the chain:**
```python
# Line 156 - Pass to _get_linked_posts
all_post_ids = self._get_linked_posts(
    db,
    set(relevant_ids),
    expert_id  # NEW
)

# Update _get_linked_posts signature (line 49):
def _get_linked_posts(
    self,
    db: Session,
    initial_post_ids: Set[int],
    expert_id: str  # NEW
) -> Set[int]:
```

### 4. Comment Groups Service (CRITICAL - Comment Analysis)
**File:** `backend/src/services/comment_group_map_service.py`

**Method signature (line 230):**
```python
async def process(
    self,
    query: str,
    db: Session,
    expert_id: str,  # NEW parameter
    exclude_post_ids: Optional[List[int]] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
```

**Pass to _load_drift_groups (line 252):**
```python
all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids)
```

**Update _load_drift_groups signature (line 84):**
```python
def _load_drift_groups(
    self,
    db: Session,
    expert_id: str,  # NEW parameter
    exclude_post_ids: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
```

**Add filter (line 99-110):**
```python
query = db.query(
    comment_group_drift.c.post_id,
    comment_group_drift.c.drift_topics,
    Post.telegram_message_id,
    Post.message_text,
    Post.created_at,
    Post.author_name
).join(
    Post, comment_group_drift.c.post_id == Post.post_id
).filter(
    comment_group_drift.c.has_drift == True,
    Post.expert_id == expert_id  # NEW
)
```

### 5. Import Scripts Updates

**File:** `backend/src/data/json_parser.py`

Add CLI argument (after line 277):
```python
parser.add_argument('--expert-id', required=True,
                   help='Expert identifier (e.g., refat, ai_architect)')
```

Set expert_id in Post creation (line 124):
```python
post = Post(
    channel_id=channel_info['channel_id'],
    channel_name=channel_info['channel_name'],
    telegram_message_id=msg.get('id'),
    expert_id=args.expert_id,  # NEW
    message_text=text,
    ...
)
```

**File:** `backend/src/data/channel_syncer.py`

Update method signature (line 61):
```python
async def sync_channel_incremental(
    self,
    channel_username: str,
    expert_id: str,  # NEW
    dry_run: bool = False
) -> Dict[str, Any]:
```

Set expert_id in Post creation (line 367):
```python
post = Post(
    channel_id=str(channel.id),
    channel_name=channel.title,
    telegram_message_id=post_data['telegram_message_id'],
    expert_id=expert_id,  # NEW
    ...
)
```

## Testing Requirements

### Test 1: Database Migration
```bash
# Run migration
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql

# Verify column exists
sqlite3 data/experts.db "PRAGMA table_info(posts);" | grep expert_id
# Expected: 15|expert_id|VARCHAR(50)|0||0

# Verify all 156 Refat posts updated
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id='refat';"
# Expected: 156

# Verify no NULL expert_ids
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id IS NULL;"
# Expected: 0
```

### Test 2: Pipeline Still Works After Refactoring
```bash
# Start backend
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# In another terminal, test query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое AI agents?", "stream_progress": false}' \
  -o /tmp/test_result.json

# Check response
cat /tmp/test_result.json | jq '{sources: .main_sources | length, confidence: .confidence, posts_analyzed: .posts_analyzed}'

# Should return similar results as before refactoring
```

### Test 3: Verify Filtering in Logs
```bash
# Check that expert_id filter is applied
grep "expert_id" backend/logs/*.log

# Should see SQL queries with expert_id filters
```

### Test 4: Import Scripts
```bash
# Test json_parser requires --expert-id
python -m src.data.json_parser test.json
# Should error: "argument --expert-id is required"

# Test with expert-id
python -m src.data.json_parser test.json --expert-id test_expert --dry-run
# Should work
```

## Implementation Checklist

- [ ] Create migration file `003_add_expert_id.sql`
- [ ] Run migration on database
- [ ] Update Post model - add expert_id field
- [ ] Update Query Endpoint - add expert_id filter (2 places)
- [ ] Update Query Endpoint - pass expert_id to Resolve service
- [ ] Update Query Endpoint - pass expert_id to Comment Groups service
- [ ] Update Resolve Service - add expert_id parameter
- [ ] Update Resolve Service - add filters to 3 DB queries
- [ ] Update Comment Groups Service - add expert_id parameter
- [ ] Update Comment Groups Service - add filter to drift query
- [ ] Update json_parser.py - add --expert-id CLI argument
- [ ] Update json_parser.py - set expert_id in Post creation
- [ ] Update channel_syncer.py - add expert_id parameter
- [ ] Update channel_syncer.py - set expert_id in Post creation
- [ ] Run Test 1: Database Migration
- [ ] Run Test 2: Pipeline Functionality
- [ ] Run Test 3: Verify Filtering
- [ ] Run Test 4: Import Scripts
- [ ] Update CLAUDE.md with changes

## Success Criteria

1. ✅ All 156 Refat posts have `expert_id='refat'`
2. ✅ Test query returns same results as before refactoring
3. ✅ All critical DB queries include `Post.expert_id` filter
4. ✅ Import scripts require and set expert_id
5. ✅ No posts from other experts can leak into Refat's results

## Risks & Mitigation

**Risk:** Breaking existing Refat pipeline
**Mitigation:** Comprehensive testing after each change, easy rollback via git

**Risk:** NULL expert_ids causing query failures
**Mitigation:** Migration sets expert_id for all existing posts

**Risk:** Missing expert_id filter in some query
**Mitigation:** Full audit completed, all queries identified

## Next Task

After successful completion → `tasks/o-add-second-expert.md`
