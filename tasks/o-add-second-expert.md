# Task: Add Second Expert (AI Architect)

**Created:** 2025-10-10
**Status:** pending
**Branch:** feature/add-ai-architect
**Priority:** HIGH
**Depends on:** n-refactor-for-multi-expert.md (MUST be completed first)

## Objective

Add AI Architect as the second expert to the multi-expert panel system. Import channel data, comments, configure pipeline to run parallel queries, and implement accordion UI.

## Prerequisites

**CRITICAL:** Task `n-refactor-for-multi-expert.md` MUST be completed and tested!

Verify before starting:
```bash
# Check expert_id column exists
sqlite3 data/experts.db "PRAGMA table_info(posts);" | grep expert_id
# Expected: 15|expert_id|VARCHAR(50)|0||0

# Check all Refat posts have expert_id
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id='refat';"
# Expected: 156
```

## Phase 1: Import AI Architect Channel Data

### Step 1.1: Receive Data from User
**User must provide:**
- Path to JSON export file from AI Architect Telegram channel
- Channel username (e.g., `@ai_architect_channel` or just channel name)
- Confirm expert_id to use: `ai_architect`

### Step 1.2: Validate JSON Before Import
```bash
# Check file exists
ls -lh PATH_TO_JSON

# Check JSON is valid
python3 -c "import json; data=json.load(open('PATH_TO_JSON')); print(f'✅ Valid JSON: {len(data.get(\"messages\", []))} messages')"

# Check channel info
python3 -c "import json; data=json.load(open('PATH_TO_JSON')); print(f'Channel: {data.get(\"name\", data.get(\"title\"))}'); print(f'Type: {data.get(\"type\")}'); print(f'ID: {data.get(\"id\")}')"
```

### Step 1.3: Dry Run Import
```bash
cd backend

# Dry run first (no database changes)
python -m src.data.json_parser PATH_TO_JSON --expert-id ai_architect --dry-run

# Review output carefully
# Expected: Posts imported: X, Messages skipped: Y, Errors: 0
```

### Step 1.4: Real Import
```bash
cd backend

# Real import
python -m src.data.json_parser PATH_TO_JSON --expert-id ai_architect
```

**Expected output:**
```
Parsing file: PATH_TO_JSON
Found X messages to import
Progress: X/X (100.0%)
✅ Import completed successfully!

Import Statistics:
  Posts imported: X
  Links created: Y
  Messages skipped: Z
  Errors: 0
```

### Step 1.5: Verify Import Success
```bash
# Check both experts exist
sqlite3 data/experts.db "SELECT expert_id, COUNT(*) as posts FROM posts GROUP BY expert_id;"
# Expected:
# refat|156
# ai_architect|X

# Check channel_id is different for each expert
sqlite3 data/experts.db "SELECT expert_id, channel_id, channel_name FROM posts GROUP BY expert_id;"

# Check date range for AI Architect posts
sqlite3 data/experts.db "SELECT expert_id, MIN(created_at) as first_post, MAX(created_at) as last_post FROM posts GROUP BY expert_id;"

# Check for any NULL expert_ids (should be NONE)
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id IS NULL;"
# Expected: 0
```

### Step 1.6: Sanitization Verification
```bash
# Check for problematic escape sequences
sqlite3 data/experts.db "SELECT telegram_message_id, SUBSTR(message_text, 1, 100) FROM posts WHERE expert_id='ai_architect' AND message_text LIKE '%\\\\%' LIMIT 3;"

# Should show only valid JSON escapes or be empty
```

## Phase 2: Import AI Architect Comments

### Step 2.1: Verify Telegram API Configuration
```bash
# Check credentials exist
grep -E "TELEGRAM_API_ID|TELEGRAM_API_HASH|TELEGRAM_CHANNEL" backend/.env

# Should show valid values (not empty)
```

### Step 2.2: Interactive Sync (Recommended Method)
```bash
cd backend

# Run channel syncer
TELEGRAM_CHANNEL=ai_architect_username python sync_channel.py --dry-run

# Review output, then real sync
TELEGRAM_CHANNEL=ai_architect_username python sync_channel.py
```

**Alternative: Use comment collector**
```bash
cd backend
python -m src.data.comment_collector

# Interactively select AI Architect posts to fetch comments for
```

### Step 2.3: Verify Comments Import
```bash
# Count comments per expert
sqlite3 data/experts.db "
SELECT p.expert_id, COUNT(c.comment_id) as total_comments
FROM posts p
LEFT JOIN comments c ON p.post_id = c.post_id
GROUP BY p.expert_id;
"

# Expected to see comments for both experts
```

### Step 2.4: Run Drift Analysis
```bash
cd backend

# Analyze drift topics for all AI Architect comment groups
python analyze_drift.py

# Check drift groups created
sqlite3 data/experts.db "
SELECT p.expert_id, COUNT(*) as drift_groups_count
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE cgd.has_drift = 1
GROUP BY p.expert_id;
"
```

## Phase 3: Backend - Parallel Expert Pipelines

### Step 3.1: Update Query Endpoint for Multi-Expert
**File:** `backend/src/api/simplified_query_endpoint.py`

**Current (from task n):**
```python
# Line 114
expert_id = 'refat'  # Hardcoded
posts = db.query(Post).filter(Post.expert_id == expert_id).all()
```

**New approach - Run separate pipeline per expert:**

Replace event_generator function to support multiple experts:

```python
async def event_generator_multi_expert(
    request: QueryRequest,
    db: Session,
    api_key: str,
    request_id: str
) -> AsyncGenerator[str, None]:
    """Generate SSE events for multi-expert query processing."""
    start_time = time.time()

    expert_ids = ['refat', 'ai_architect']  # TODO: make configurable
    expert_results = []

    for expert_id in expert_ids:
        # Run full pipeline for this expert
        expert_result = await process_expert_pipeline(
            expert_id=expert_id,
            request=request,
            db=db,
            api_key=api_key,
            request_id=request_id
        )
        expert_results.append(expert_result)

        # Yield progress event
        yield f"data: {json.dumps({...})}\n\n"

    # Send final combined result
    response = MultiExpertQueryResponse(
        query=request.query,
        expert_responses=expert_results,
        total_processing_time_ms=...,
        request_id=request_id
    )

    yield f"data: {json.dumps({...})}\n\n"
```

**Create helper function:**
```python
async def process_expert_pipeline(
    expert_id: str,
    request: QueryRequest,
    db: Session,
    api_key: str,
    request_id: str
) -> Dict[str, Any]:
    """Process full pipeline for one expert."""

    # Get posts for this expert only
    posts = db.query(Post).filter(
        Post.expert_id == expert_id
    ).order_by(Post.created_at.desc()).all()

    # Map phase
    map_service = MapService(api_key=api_key)
    map_results = await map_service.process(posts=posts, query=request.query)

    # Filter HIGH+MEDIUM
    filtered = [p for p in map_results['relevant_posts'] if p['relevance'] in ['HIGH', 'MEDIUM']]

    # Resolve phase (with expert_id filtering)
    resolve_service = SimpleResolveService()
    resolve_results = await resolve_service.process(
        relevant_posts=filtered,
        query=request.query,
        expert_id=expert_id  # CRITICAL
    )

    # Reduce phase
    reduce_service = ReduceService(api_key=api_key)
    reduce_results = await reduce_service.process(
        enriched_posts=resolve_results['enriched_posts'],
        query=request.query
    )

    # Comment Groups (with expert_id filtering)
    if request.include_comment_groups:
        cg_service = CommentGroupMapService(api_key=api_key)
        comment_groups = await cg_service.process(
            query=request.query,
            db=db,
            expert_id=expert_id,  # CRITICAL
            exclude_post_ids=reduce_results['main_sources']
        )

    # Comment Synthesis
    synthesis = None
    if comment_groups:
        synthesis_service = CommentSynthesisService(api_key=api_key)
        synthesis = await synthesis_service.process(...)

    return {
        'expert_id': expert_id,
        'expert_name': get_expert_name(expert_id),
        'channel_username': get_channel_username(expert_id),
        'answer': reduce_results['answer'],
        'main_sources': reduce_results['main_sources'],
        ...
    }
```

### Step 3.2: Create Response Models
**File:** `backend/src/api/models.py`

```python
class ExpertResponse(BaseModel):
    """Response from a single expert."""
    expert_id: str = Field(..., description="Expert identifier")
    expert_name: str = Field(..., description="Human-readable expert name")
    channel_username: str = Field(..., description="Telegram channel username")
    answer: str
    main_sources: List[int]
    confidence: ConfidenceLevel
    posts_analyzed: int
    processing_time_ms: int
    relevant_comment_groups: Optional[List[CommentGroupResponse]] = []
    comment_groups_synthesis: Optional[str] = None

class MultiExpertQueryResponse(BaseModel):
    """Response containing results from multiple experts."""
    query: str
    expert_responses: List[ExpertResponse]
    total_processing_time_ms: int
    request_id: str
```

**Add helper functions:**
```python
def get_expert_name(expert_id: str) -> str:
    """Get display name for expert."""
    names = {
        'refat': 'Refat (Tech & AI)',
        'ai_architect': 'AI Архитектор'
    }
    return names.get(expert_id, expert_id)

def get_channel_username(expert_id: str) -> str:
    """Get Telegram channel username for expert."""
    channels = {
        'refat': 'nobilix',
        'ai_architect': 'ai_architect_channel'  # UPDATE with real username
    }
    return channels.get(expert_id, expert_id)
```

### Step 3.3: Fix Hardcoded channel_username in Comment Groups Service
**File:** `backend/src/services/comment_group_map_service.py`

**CRITICAL FIX from audit:** Remove hardcoded "nobilix"

**Find the code around line 168 where anchor_post dict is created:**
```python
# BEFORE (hardcoded):
"channel_username": "nobilix"

# AFTER (dynamic):
"channel_username": get_channel_username(expert_id)
```

**Full context (approximate line 160-175):**
```python
anchor_post = {
    "post_id": post_id,
    "telegram_message_id": telegram_message_id,
    "message_text": message_text[:200] + ("..." if len(message_text) > 200 else ""),
    "created_at": created_at.isoformat() if created_at else None,
    "author_name": author_name or "Unknown",
    "channel_username": get_channel_username(expert_id)  # FIXED - was hardcoded "nobilix"
}
```

**Note:** Import get_channel_username at top of file:
```python
from ..api.models import get_channel_username  # Add this import
```

## Phase 4: Frontend - Accordion UI

### Step 4.1: Create ExpertAccordion Component
**File:** `frontend/src/components/ExpertAccordion.tsx`

```typescript
import React, { useState } from 'react';
import ExpertResponse from './ExpertResponse';
import PostsList from './PostsList';
import CommentGroupsList from './CommentGroupsList';
import CommentSynthesis from './CommentSynthesis';
import { ExpertResponse as ExpertResponseType, PostDetailResponse } from '../types/api';

interface ExpertAccordionProps {
  expertResponse: ExpertResponseType;
  isExpanded: boolean;
  onToggle: () => void;
}

const ExpertAccordion: React.FC<ExpertAccordionProps> = ({
  expertResponse,
  isExpanded,
  onToggle
}) => {
  const [posts, setPosts] = useState<PostDetailResponse[]>([]);
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);

  // Load posts when expanded
  React.useEffect(() => {
    if (isExpanded && expertResponse.main_sources.length > 0) {
      // Load posts logic here
    }
  }, [isExpanded, expertResponse.main_sources]);

  return (
    <div style={styles.accordion}>
      {/* Header - always visible */}
      <div style={styles.header} onClick={onToggle}>
        <span style={styles.icon}>{isExpanded ? '▼' : '▶'}</span>
        <span style={styles.expertName}>{expertResponse.expert_name}</span>
        <span style={styles.channelName}>@{expertResponse.channel_username}</span>
        <span style={styles.stats}>
          {expertResponse.posts_analyzed} постов, {(expertResponse.processing_time_ms / 1000).toFixed(1)}с
        </span>
      </div>

      {/* Body - only when expanded */}
      {isExpanded && (
        <div style={styles.body}>
          <div style={styles.leftColumn}>
            <ExpertResponse
              answer={expertResponse.answer}
              sources={expertResponse.main_sources}
              onPostClick={setSelectedPostId}
            />
            {expertResponse.comment_groups_synthesis && (
              <CommentSynthesis synthesis={expertResponse.comment_groups_synthesis} />
            )}
          </div>

          <div style={styles.rightColumn}>
            <PostsList posts={posts} selectedPostId={selectedPostId} />
            {expertResponse.relevant_comment_groups && expertResponse.relevant_comment_groups.length > 0 && (
              <CommentGroupsList
                commentGroups={expertResponse.relevant_comment_groups}
                channelUsername={expertResponse.channel_username}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const styles = {
  accordion: {
    marginBottom: '10px',
    backgroundColor: 'white',
    borderRadius: '8px',
    border: '1px solid #dee2e6'
  },
  header: {
    padding: '15px 20px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px',
    transition: 'background-color 0.2s'
  } as const,
  icon: {
    fontSize: '14px',
    color: '#6c757d'
  },
  expertName: {
    fontSize: '16px',
    fontWeight: '600' as const,
    color: '#212529'
  },
  channelName: {
    fontSize: '14px',
    color: '#6c757d'
  },
  stats: {
    fontSize: '13px',
    color: '#6c757d',
    marginLeft: 'auto'
  },
  body: {
    display: 'flex',
    gap: '20px',
    padding: '20px'
  },
  leftColumn: {
    flex: 1
  },
  rightColumn: {
    flex: 1
  }
};

export default ExpertAccordion;
```

### Step 4.2: Update App.tsx
**File:** `frontend/src/App.tsx`

```typescript
import ExpertAccordion from './components/ExpertAccordion';
import { ExpertResponse } from './types/api';

// Replace result state with expertResults
const [expertResults, setExpertResults] = useState<ExpertResponse[]>([]);
const [expandedExperts, setExpandedExperts] = useState<Set<string>>(new Set(['refat']));

const handleToggleExpert = (expertId: string) => {
  setExpandedExperts(prev => {
    const newSet = new Set(prev);
    if (newSet.has(expertId)) {
      newSet.delete(expertId);
    } else {
      newSet.add(expertId);
    }
    return newSet;
  });
};

// In handleQuerySubmit - update to receive multi-expert response
const response = await apiClient.submitQuery(...);
setExpertResults(response.expert_responses);

// In render - replace single ExpertResponse with accordion list
{expertResults.map(expertResult => (
  <ExpertAccordion
    key={expertResult.expert_id}
    expertResponse={expertResult}
    isExpanded={expandedExperts.has(expertResult.expert_id)}
    onToggle={() => handleToggleExpert(expertResult.expert_id)}
  />
))}
```

### Step 4.3: Update API Types
**File:** `frontend/src/types/api.ts`

```typescript
export interface ExpertResponse {
  expert_id: string;
  expert_name: string;
  channel_username: string;
  answer: string;
  main_sources: number[];
  confidence: ConfidenceLevel;
  posts_analyzed: number;
  processing_time_ms: number;
  relevant_comment_groups?: CommentGroupResponse[];
  comment_groups_synthesis?: string;
}

export interface MultiExpertQueryResponse {
  query: string;
  expert_responses: ExpertResponse[];
  total_processing_time_ms: number;
  request_id: string;
}
```

## Testing Requirements

### Test 1: Data Import Verification
All checks from Phase 1 & 2 should pass

### Test 2: Multi-Expert Query
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое AI agents?", "stream_progress": false}' \
  | jq '{experts: .expert_responses | length, expert_ids: [.expert_responses[].expert_id]}'

# Expected: {"experts": 2, "expert_ids": ["refat", "ai_architect"]}
```

### Test 3: No Mixing Verification
```bash
# Query logs should show separate processing
tail -100 backend/logs/*.log | grep "Processing.*expert"

# Should see separate lines for each expert
```

### Test 4: UI Accordion
1. Open http://localhost:3000/
2. Submit query
3. Verify:
   - Two accordion headers visible
   - Refat expanded by default, AI Architect collapsed
   - Click AI Architect → expands smoothly
   - Both show complete response (answer + posts + comments)
   - Posts NOT mixed between experts

## Success Criteria

1. ✅ AI Architect data imported (posts + comments + drift analysis)
2. ✅ Backend returns 2 expert responses per query
3. ✅ Frontend shows 2 accordions
4. ✅ Each expert shows isolated results (no mixing)
5. ✅ All tests pass

## Rollback Plan

```bash
# Remove AI Architect data
sqlite3 data/experts.db "DELETE FROM posts WHERE expert_id='ai_architect';"

# Revert code
git checkout main -- backend/src/api/simplified_query_endpoint.py frontend/src/
```

## Next Steps

After completion: Add expert selector (checkboxes to choose which experts to query)
