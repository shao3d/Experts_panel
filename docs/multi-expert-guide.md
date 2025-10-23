# Multi-Expert Setup and Management Guide

Complete guide for setting up and managing multiple experts in the Experts Panel system.

## Overview

The multi-expert architecture allows processing queries through multiple experts simultaneously, with complete data isolation between experts.

## 🏗️ Architecture

### Parallel Processing
- Each expert processed independently via async tasks
- No data mixing between experts at any pipeline phase
- Dynamic expert detection from database
- SSE events include `expert_id` for tracking

### Data Isolation
- All tables have `expert_id` field (migrations 003-004)
- Complete separation of posts, comments, drift groups
- Channel-specific filtering prevents data corruption

## 🚨 Critical: Channel ID Mapping

Each expert MUST have unique `channel_id` to prevent data corruption:

```python
EXPERT_CHANNELS = {
    'refat': {
        'channel_id': '2273349814',
        'channel_username': 'nobilix',
        'telegram_channel': 'nobilix'
    },
    'ai_architect': {
        'channel_id': '2293112404',
        'channel_username': 'the_ai_architect',
        'telegram_channel': 'the_ai_architect'
    }
}
```

### Finding Channel IDs

**Method 1: From posts table**
```sql
SELECT DISTINCT channel_id, expert_id FROM posts;
```

**Method 2: During import**
```bash
python -m src.data.json_parser export.json --expert-id new_expert
# channel_id is automatically stored
```

## 📝 Adding New Experts

### Step 1: Import Posts and Comments

```bash
cd backend
python -m src.data.json_parser export.json --expert-id new_expert_id
```

### Step 2: Import Comments (CRITICAL)

**⚠️ MUST modify `telegram_comments_fetcher.py` for each new expert:**

1. **Filter posts by channel_id** (lines 185-187):
```python
def get_posts_from_db(self, db: Session) -> List[tuple]:
    posts = db.query(Post.post_id, Post.telegram_message_id).filter(
        Post.channel_id == 'NEW_EXPERT_CHANNEL_ID'  # UPDATE THIS
    ).order_by(Post.created_at).all()
    return [(p.post_id, p.telegram_message_id) for p in posts]
```

2. **Filter when saving comments** (lines 207-210):
```python
post = db.query(Post).filter(
    Post.telegram_message_id == comment_data['parent_telegram_message_id'],
    Post.channel_id == 'NEW_EXPERT_CHANNEL_ID'  # CRITICAL: UPDATE THIS
).first()
```

3. **Run comment import:**
```bash
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
export TELEGRAM_CHANNEL=new_expert_channel
uv run python -m src.data.telegram_comments_fetcher
```

### Step 3: Setup Drift Analysis

Create empty drift records:
```sql
INSERT INTO comment_group_drift (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
SELECT
    p.post_id,
    0 as has_drift,
    NULL as drift_topics,
    datetime('now') as analyzed_at,
    'pending' as analyzed_by,
    p.expert_id
FROM posts p
WHERE p.post_id IN (
    SELECT DISTINCT c.post_id
    FROM comments c
    JOIN posts p2 ON c.post_id = p2.post_id
    WHERE p2.expert_id = 'new_expert_id'
)
AND p.post_id NOT IN (SELECT post_id FROM comment_group_drift);
```

### Step 4: Run Drift Analysis

```bash
cd backend
python analyze_drift.py --batch-size 10
```

## 🔧 Verification Commands

### Check Channel ID Coverage
```sql
SELECT channel_id, expert_id, COUNT(*) as posts,
       MIN(telegram_message_id) as first_post,
       MAX(telegram_message_id) as last_post
FROM posts
GROUP BY channel_id, expert_id;
```

### Check Comment Distribution
```sql
SELECT p.expert_id,
       COUNT(DISTINCT p.post_id) as posts_with_comments,
       COUNT(c.comment_id) as total_comments
FROM posts p
JOIN comments c ON p.post_id = c.post_id
GROUP BY p.expert_id;
```

### Check Drift Analysis Coverage
```sql
SELECT p.expert_id,
       COUNT(*) as total_posts,
       SUM(CASE WHEN cgd.analyzed_by != 'pending' THEN 1 ELSE 0 END) as analyzed,
       SUM(CASE WHEN cgd.has_drift = 1 THEN 1 ELSE 0 END) as with_drift
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
GROUP BY p.expert_id;
```

## ⚠️ Common Pitfalls

### 1. Forgetting channel_id filter
- **Symptom**: Comments from new expert saved to old expert's posts
- **Fix**: Add `channel_id` filter in `telegram_comments_fetcher.py`

### 2. Hardcoding channel_id values
- **Symptom**: Script only works for one expert
- **Fix**: Use parameterized channel_id or detect from database

### 3. Missing expert_id in drift records
- **Symptom**: Drift analysis fails or mixes experts
- **Fix**: Ensure INSERT includes `expert_id` from posts table

### 4. Running migration 008 after data import
- **Symptom**: Some comments missing after import
- **Fix**: Apply migration BEFORE importing second expert

## 🔄 Database Migrations

### Required Migrations for Multi-Expert Support
```bash
# Apply in order
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql
sqlite3 data/experts.db < backend/migrations/004_add_expert_id_to_drift.sql
sqlite3 data/experts.db < backend/migrations/006_add_unique_telegram_message_id.sql
sqlite3 data/experts.db < backend/migrations/008_fix_comment_unique_constraint.sql
```

### Migration 008: Critical Fix
**Problem**: Original constraint prevented different channels from having comments with same `telegram_comment_id`.

**Solution**: Compound constraint on `(telegram_comment_id, post_id)`:
```sql
CREATE UNIQUE INDEX idx_telegram_comment_post_unique ON comments (telegram_comment_id, post_id);
```

## 🧪 Testing Multi-Expert Setup

### API Testing
```bash
# Test all experts
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query", "stream_progress": false}'

# Test specific expert
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query", "expert_filter": ["refat"], "stream_progress": false}'
```

### Expected Response Structure
```json
{
  "query": "Test query",
  "expert_responses": [
    {
      "expert_id": "refat",
      "expert_name": "Refat (Tech & AI)",
      "channel_username": "nobilix",
      "answer": "...",
      "main_sources": [21, 65, 77],
      "confidence": "HIGH",
      "posts_analyzed": 46,
      "processing_time_ms": 12500
    }
  ],
  "total_processing_time_ms": 13200,
  "request_id": "uuid-here"
}
```

## 🚀 Performance Considerations

- **Parallel Processing**: Reduces total time to `max(expert_times)` instead of `sum(expert_times)`
- **Resource Usage**: Scales with number of experts (API calls, memory)
- **Failure Isolation**: Expert failure doesn't affect other experts

## 🔍 Debugging Multi-Expert Issues

### Check Data Mixing
```sql
-- Verify no data mixing between experts
SELECT expert_id, COUNT(*) FROM posts GROUP BY expert_id;
SELECT p.expert_id, c.comment_id FROM posts p JOIN comments c ON p.post_id = c.post_id LIMIT 10;
```

### Check Pipeline Processing
- Monitor SSE events for correct `expert_id` prefixes
- Verify each expert processes independently
- Check logs for expert-specific processing

## 📚 Key Files for Multi-Expert

- **API Models**: `backend/src/api/models.py` - `ExpertResponse`, `MultiExpertQueryResponse`
- **Query Endpoint**: `backend/src/api/simplified_query_endpoint.py` - `process_expert_pipeline()`
- **Comment Groups**: `backend/src/services/comment_group_map_service.py` - `_load_drift_groups()`
- **Helper Functions**: `backend/src/models.py` - `get_expert_name()`, `get_channel_username()`