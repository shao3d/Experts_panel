---
name: drift_on_synced
description: Drift analysis agent for newly synced pending groups
---

# Drift-on-Synced Agent

**Purpose**: Analyze drift for pending comment groups that were just created/reset during /sync-all operation.

## When to Use

- **Automatic**: Triggered by /sync-all command after successful sync
- **Manual**: After sync when you want to analyze new pending drift groups
- **Target**: Only works with `comment_group_drift.analyzed_by = 'pending'` records

## Agent Workflow

### Step 1: Identify Pending Groups
- Query `comment_group_drift` table for `analyzed_by = 'pending'`
- Filter by expert_id if needed (auto-detect all)
- Show count of pending groups by expert

### Step 2: Analyze Each Pending Group
For each pending group:
1. Load all comments for the post
2. Analyze topic drift from original post
3. Extract drift topics: topic, keywords, key_phrases, context
4. Determine if meaningful drift exists
5. Update `comment_group_drift` record

### Step 3: Database Operations
- **No drift**: `has_drift = 0`, analyzed_by = 'drift-on-synced', keep drift_topics = NULL
- **Has drift**: `has_drift = 1`, analyzed_by = 'drift-on-synced', populate drift_topics JSON
- Update `analyzed_at` timestamp

## 🚨 КРИТИЧЕСКИ ВАЖНО: Правильная структура drift_topics

**ОБЯЗАТЕЛЬНЫЙ формат JSON в базе данных:**
```json
{
  "has_drift": true,
  "drift_topics": [
    {
      "topic": "Описание темы дрифта",
      "keywords": ["ключевое", "слово", "фразы"],
      "key_phrases": ["точные", "фразы", "из комментариев"],
      "context": "Контекст из обсуждения"
    }
  ]
}
```

**❌ НЕПРАВИЛЬНЫЙ формат (массив напрямую):**
```json
[
  {
    "topic": "Описание темы",
    "keywords": ["..."],
    "key_phrases": ["..."],
    "context": "..."
  }
]
```

**Правило:**
- Всегда сохраняй JSON объект с полями `has_drift` и `drift_topics` (массив)
- `drift_topics` должен быть именно массив объектов, а не массив напрямую
- Это соответствует формату CommentGroupMapService при загрузке drift тем

## Technical Implementation

### SQL Queries

```sql
-- Find pending groups
SELECT post_id, expert_id
FROM comment_group_drift
WHERE analyzed_by = 'pending';

-- Get comments for analysis
SELECT comment_id, comment_text, author_name, created_at
FROM comments
WHERE post_id = ?
ORDER BY created_at;

-- Update drift analysis result
UPDATE comment_group_drift
SET has_drift = ?,
    drift_topics = ?,
    analyzed_by = 'drift-on-synced',
    analyzed_at = datetime('now')
WHERE post_id = ?;

-- IMPORTANT: drift_topics parameter must be JSON object with format:
-- {"has_drift": true, "drift_topics": [{topic, keywords, key_phrases, context}]}
-- NOT just the array of topics directly!
```

### Analysis Logic

**Same prompt as drift_extraction agent**:
- Compare post topic vs comment discussions
- Identify topic shifts, expansions, tangents
- Extract structured drift topics
- Determine if comments add meaningful context beyond original post

### Output Format

```json
{
  "total_pending_groups": 25,
  "groups_processed": 25,
  "by_expert": {
    "ai_architect": {"processed": 6, "with_drift": 3, "without_drift": 3},
    "neuraldeep": {"processed": 10, "with_drift": 7, "without_drift": 3},
    "refat": {"processed": 9, "with_drift": 5, "without_drift": 4}
  },
  "drift_summary": {
    "total_with_drift": 15,
    "total_without_drift": 10,
    "success_rate": "100%"
  }
}
```

## Integration with /sync-all

### Auto-trigger Logic
```python
# After successful sync
if result['success'] and result['total_pending_drift'] > 0:
    print(f"🎯 Found {result['total_pending_drift']} pending drift groups")
    print("🔄 Starting drift analysis for synced data...")
    # Trigger drift-on-synced agent
    drift_result = run_drift_on_synced_agent()
    print(f"✅ Drift analysis complete: {drift_result['groups_processed']} groups processed")
```

### Prerequisites
- Database: `data/experts.db` with pending drift records
- Models: Access to `comment_group_drift`, `comments`, `posts` tables
- Claude Sonnet 4.5 for analysis (high accuracy for drift detection)

## Error Handling

- **No pending groups**: Early exit with success message
- **Database errors**: Rollback and report specific errors
- **API errors**: Retry logic with exponential backoff
- **Validation**: Ensure drift_topics JSON format is valid

## Performance Considerations

- **Batch processing**: 5-10 groups per API call
- **Rate limiting**: Respect Claude API limits
- **Efficient queries**: Use indexed columns (post_id, expert_id)
- **Connection pooling**: Reuse database connections

## Monitoring

Track metrics:
- Pending groups count before/after
- Processing time per group
- Success/failure rates
- Drift detection ratio (with_drift vs without_drift)

## Usage Examples

### Automatic (from /sync-all):
```bash
/sync-all
# → Sync completes → Auto-triggers drift-on-synced → Shows combined results
```

### Manual:
```bash
# Check pending groups first
sqlite3 data/experts.db "SELECT COUNT(*) FROM comment_group_drift WHERE analyzed_by = 'pending';"

# Run agent
/claude/run-agent drift_on_synced
```

## Differences from drift_extraction

| Feature | drift_extraction | drift_on_synced |
|---------|------------------|------------------|
| **Scope** | All comment groups | Only pending groups |
| **Trigger** | Manual command | Auto after sync |
| **Performance** | Slower (all groups) | Fast (targeted) |
| **Use case** | Full analysis | Incremental updates |
| **analyzed_by** | 'drift-agent' | 'drift-on-synced' |

## Benefits

1. **Immediate analysis**: No waiting for separate drift analysis
2. **Targeted processing**: Only groups that need analysis
3. **Workflow integration**: Single command pipeline
4. **Efficiency**: Faster than full drift analysis
5. **Fresh data**: Analysis happens immediately after sync