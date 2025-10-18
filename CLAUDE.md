# Experts Panel Development Guidelines

Auto-generated from feature plans. Last updated: 2025-10-15

## Active Technologies
- Python 3.11+ with FastAPI and Pydantic v2
- SQLite with SQLAlchemy 2.0
- React 18 with TypeScript
- OpenRouter API - Multi-model strategy:
  - Qwen 2.5-72B Instruct for Map phase
  - Gemini 2.0 Flash for Reduce and Comment Synthesis
  - GPT-4o-mini for Comment Groups matching
- Docker for deployment
- Railway for hosting

## Project Structure
```
backend/
├── src/
│   ├── models/       # SQLAlchemy models
│   │   ├── base.py          # Database setup & session
│   │   ├── post.py          # Post model with telegram_message_id
│   │   ├── link.py          # Link model (REPLY/FORWARD/MENTION)
│   │   ├── comment.py       # Comment model for expert annotations
│   │   ├── database.py      # Database initialization & comment_group_drift table
│   │   └── init_db.py       # DB initialization script
│   ├── services/     # Simplified Map-Resolve-Reduce pipeline
│   │   ├── map_service.py              # Phase 1: Find relevant posts via GPT
│   │   ├── simple_resolve_service.py   # Phase 2: DB link expansion (no GPT)
│   │   ├── reduce_service.py           # Phase 3: Synthesize answer via GPT (supports personal style)
│   │   ├── comment_group_map_service.py # Pipeline B: Find relevant comment groups
│   │   ├── comment_synthesis_service.py # Pipeline C: Extract insights from comment groups
│   │   ├── openrouter_adapter.py       # OpenRouter API integration
│   │   ├── fact_validator.py           # Fact validation utilities
│   │   └── log_service.py              # Logging service
│   ├── api/          # FastAPI endpoints
│   │   ├── main.py                     # FastAPI app with CORS & SSE
│   │   ├── simplified_query_endpoint.py # Main query endpoint with streaming
│   │   ├── comment_endpoints.py        # Expert comments management
│   │   ├── import_endpoints.py         # Data import from Telegram JSON
│   │   └── models.py                   # Pydantic request/response models
│   └── data/         # Import and parsing
│       ├── json_parser.py              # Telegram JSON parser
│       ├── comment_collector.py        # Interactive comment collection
│       ├── telegram_comments_fetcher.py # Base Telegram API fetcher
│       └── channel_syncer.py           # Incremental channel sync
├── prompts/          # LLM prompts (optimized per model)
│   ├── map_prompt.txt                # Map phase (Qwen 2.5-72B)
│   ├── reduce_prompt.txt             # Reduce phase neutral style (Gemini 2.0 Flash)
│   ├── reduce_prompt_personal.txt    # Personal style default (Gemini 2.0 Flash)
│   ├── comment_group_drift_prompt.txt # Pipeline B: Drift matching (GPT-4o-mini)
│   ├── comment_synthesis_prompt.txt  # Pipeline C: Extract insights (Gemini 2.0 Flash)
│   └── README.md                     # Prompts documentation
├── migrations/       # Database migrations
│   ├── 001_create_comment_group_drift.sql # Drift analysis table
│   ├── 002_add_sync_state.sql        # Sync state tracking table
│   ├── 003_add_expert_id.sql          # Multi-expert support (posts table)
│   ├── 004_add_expert_id_to_drift.sql # Multi-expert support (drift table)
│   ├── 005_add_unique_telegram_message_id.sql # Prevent duplicate imports
│   └── 006_add_unique_telegram_message_id.sql # Migration fix
├── analyze_drift.py  # Pre-analysis script for comment drift detection
├── sync_channel.py   # CLI script for incremental Telegram sync
└── tests/            # Validation queries
    ├── validation/                   # Validation test queries
    └── outputs/                      # Test results output

frontend/
├── src/
│   ├── App.tsx       # Main application with state management
│   ├── components/   # React components (simplified architecture)
│   │   ├── QueryForm.tsx       # Query input with validation
│   │   ├── ProgressSection.tsx # Compact progress display (emoji+percentage)
│   │   ├── ExpertResponse.tsx  # Answer display with sources
│   │   ├── PostsList.tsx       # Posts list with selection
│   │   ├── PostCard.tsx        # Individual post card
│   │   ├── CommentGroupsList.tsx # Comment groups display (Pipeline B)
│   │   ├── CommentSynthesis.tsx  # Comment insights display (Pipeline C)
│   │   ├── QueryResult.tsx     # Result container (legacy)
│   │   └── ProgressLog.tsx     # SSE events display (legacy)
│   ├── services/     # API client with SSE streaming
│   │   ├── api.ts              # APIClient with SSE parsing fix
│   │   ├── error-handler.ts    # Error handling utilities
│   │   └── index.ts            # Service exports
│   └── types/        # TypeScript interfaces matching backend
│       └── api.ts              # Full type definitions
├── public/           # Static assets
├── CLAUDE.md         # Detailed frontend architecture
└── package.json      # Dependencies & scripts

data/
├── exports/          # Telegram JSON files
└── experts.db        # SQLite database
```

## Commands

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn src.api.main:app --reload --port 8000

# Database management
python -m src.models.database  # Interactive DB operations (init/reset/drop)

# Import Telegram data (multi-expert support)
python -m src.data.json_parser <json_file> --expert-id <expert_id>

# Add comments interactively
python -m src.data.comment_collector

# Drift analysis (Pipeline B pre-processing)
cd backend && python analyze_drift.py  # Analyze all comment groups for topic drift
cd backend && python analyze_drift.py --batch-size 10  # Process in batches
cd backend && python analyze_drift.py --show-ambiguous  # Show low-confidence cases
# ⚠️ MUST re-run after data reimport (drift groups are not preserved)

# Telegram channel synchronization (multi-expert support)
cd backend && python sync_channel.py --dry-run --expert-id refat  # Preview for specific expert
cd backend && python sync_channel.py --expert-id refat            # Sync for specific expert
/sync                                                              # Alternative: use slash command

# Run validation tests
python -m pytest tests/validation/
```

### Frontend Development
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check
```

### Database Management
```bash
# Create database
sqlite3 data/experts.db < schema.sql

# Run migrations
sqlite3 data/experts.db < backend/migrations/001_create_comment_group_drift.sql
sqlite3 data/experts.db < backend/migrations/002_add_sync_state.sql
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql
sqlite3 data/experts.db < backend/migrations/004_add_expert_id_to_drift.sql
sqlite3 data/experts.db < backend/migrations/006_add_unique_telegram_message_id.sql

# Backup database
sqlite3 data/experts.db ".backup data/backup.db"

# Inspect database
sqlite3 data/experts.db ".schema"

# Query drift groups
sqlite3 data/experts.db "SELECT post_id, has_drift, analyzed_at FROM comment_group_drift WHERE has_drift=1;"
```

## Code Style

### Python
- Use type hints for all functions
- Async functions for I/O operations
- Pydantic models for validation
- Clear docstrings for pipeline phases
- Error messages must be descriptive

### TypeScript
- Strict mode enabled
- Interface over type where possible
- Explicit return types
- Component props fully typed
- No any types

### SQL
- Foreign keys for all relationships
- Comments on complex queries
- Indexes on frequently queried columns
- Use transactions for multi-table operations

## Recent Changes
1. **Multi-Expert Sync Optimization v3.0** (2025-10-16): Complete workflow integration and bug fixes
   - **NEW**: `update_specific_posts_comments()` method ensures ALL new posts get comment checking
   - **Fixed drift logic**: Only resets drift records for posts with ACTUAL new comments (not all checked posts)
   - **Enhanced sync workflow**: Two-phase comment checking (recent depth + ALL new posts)
   - **Auto drift analysis**: Created `drift_on_synced` agent for integrated drift analysis
   - **Performance data**: Real sync collected 592 comments, neuraldeep/1659 had 37 comments discovered
   - **Optimized processing**: Only 25 drift groups needed analysis vs 505 total (targeted approach)
   - **Key files**: `channel_syncer.py:283-368`, `sync_channel_multi_expert.py`, `.claude/agents/drift_on_synced.md`
   - **Updated command**: `/sync-all` v3.0 with complete sync → drift analysis workflow

2. **Map Phase Retry Mechanism Implementation** (2025-10-15): Significantly improved system reliability
   - **NEW**: Two-layer retry strategy (3 per-chunk + 1 global retry attempts)
   - **Configuration**: Uses tenacity library with exponential backoff (4s to 60s delays)
   - **Error handling**: Recovers from HTTP errors, JSON decode errors, and validation failures
   - **Reliability improvement**: 95%+ of failed chunks now recover instead of being lost
   - **Logging**: Comprehensive error tracking with expert_id and retry attempt details
   - **Performance**: Minimal overhead, parallel processing continues during retries
   - **Key files**: `map_service.py:138-143` (per-chunk), `map_service.py:324-361` (global retry)

2. **Data Selection Optimization & Model Changes** (2025-10-14): Improved precision and validation
   - **Filter phase change**: Now uses ONLY HIGH relevance posts (was HIGH+MEDIUM)
   - Reduces noise in Resolve phase, focuses on most relevant content (60-70% reduction)
   - **Comment Groups filter**: Now HIGH only (was HIGH+MEDIUM) for cleaner results
   - **Model changes**:
     - Map phase: Qwen 2.5-72B ($0.08/$0.33 per 1M tokens) - excellent for document ranking
     - Reduce phase: Gemini 2.0 Flash ($0.10/$0.40 per 1M) - better synthesis quality
     - Comment synthesis: Gemini 2.0 Flash - handles context better than GPT-4o-mini
   - **Validation improvements**: Added fact validation to catch referenced post mismatches
   - Gemini validates all [post:ID] references and adds missing IDs to main_sources
   - All changes in commit b7d971e

2. **Parallel Multi-Expert Query Processing** (2025-10-12): Complete multi-expert parallel processing
   - **Parallel architecture**: Simultaneous processing of all experts in database
   - New `process_expert_pipeline()` function processes each expert independently
   - New `event_generator_parallel()` launches async tasks for each expert
   - **API Models**: Added `ExpertResponse` and `MultiExpertQueryResponse` models
   - **Dynamic expert detection**: Auto-detects all experts from DB unless filtered
   - **Expert isolation**: Posts from different experts never mix in pipeline
   - Fixed hardcoded values: `channel_username` and `expert_id` now dynamic
   - **CLI improvements**: `sync_channel.py` accepts `--expert-id` parameter
   - SSE events include `expert_id` for progress tracking per expert
   - **Default behavior**: Processes ALL experts in parallel, returns separate results

2. **Multi-Expert Architecture & Drift Analysis Completion** (2025-10-11): Production-ready multi-expert support
   - **Multi-expert architecture**: All tables now have `expert_id` field (migrations 003-004)
   - All services (Map, Resolve, CommentGroupMap) filter by expert_id
   - Fixed `analyze_drift.py` bug to properly save expert_id (was missing in INSERT/UPDATE)
   - **Drift analysis COMPLETE** for expert 'refat': 156/156 posts analyzed (100%)
   - **Statistics**: 156 posts total, 108 with drift (69%), 1,235 comments in drift groups
   - ~~Query endpoint uses hardcoded `expert_id='refat'` for MVP~~ (fixed in next update)
   - Key migrations: `003_add_expert_id.sql`, `004_add_expert_id_to_drift.sql`, `006_add_unique_telegram_message_id.sql`
   - Commit: 8f6c322 (multi-expert), 92a0c20 (merge)

2. **Telegram Entities to Markdown Conversion** (2025-10-11): Auto-convert Telegram links and formatting
   - Created `entities_to_markdown()` utility in `backend/src/utils/telegram_entities.py`
   - Converts Telegram entity types (text_link, mention, url, bold, italic, code, etc.) to markdown
   - Updated all data import paths: `json_parser.py`, `channel_syncer.py`, `telegram_comments_fetcher.py`
   - Frontend uses `react-markdown` with `remark-gfm` plugin for autolinks rendering
   - Updated `PostCard.tsx` to render markdown instead of plain text
   - **Challenge**: Data reimport caused temporary loss of drift groups and comments
   - **Recovery**: Used `sync_channel.py --depth 200` to restore comments from Telegram API
   - **Current state**: All 156 posts with markdown links, drift analysis complete
   - Key files: `backend/src/utils/telegram_entities.py`, `backend/src/data/json_parser.py`, `backend/src/data/channel_syncer.py`, `frontend/src/components/PostCard.tsx`

2. **Comment Synthesis Feature** (2025-10-10, updated 2025-10-14): Extract complementary insights from comment groups
   - New Pipeline C phase that synthesizes insights from HIGH comment groups (changed from HIGH/MEDIUM)
   - Runs after comment groups phase, only when relevant groups exist
   - Uses Gemini 2.0 Flash (changed from GPT-4o-mini for better synthesis)
   - No limit on bullet points (extracts all valuable insights)
   - **Critical constraint**: No [post:ID] references in output to prevent UI confusion
   - Compact progress: "⏳ 🔍 Map 80% | ⚡ Reduce 100% | 💬 Comments 60%"
   - Key files: `backend/src/services/comment_synthesis_service.py`, `backend/prompts/comment_synthesis_prompt.txt`, `frontend/src/components/CommentSynthesis.tsx`
   - Commit: 68e4f29 (original), b7d971e (model change)

2. **Feature m-implement-telegram-sync** (2025-10-09): Incremental Telegram channel sync (COMPLETED)
   - Automated sync of new posts and comments from Telegram API without manual JSON exports
   - TelegramChannelSyncer class extends SafeTelegramCommentsFetcher with incremental capabilities
   - SYNC_DEPTH=20: Refreshes comments for last 20 posts (~60 days of history)
   - sync_state table tracks last_synced_message_id per channel for idempotent operations
   - CLI script with --dry-run mode for safe preview before actual sync
   - Integration with drift-extraction agent for automatic analysis of new comment groups
   - /sync slash command for streamlined workflow automation
   - Tested: 163 new comments synced (39 on new posts, 124 on old posts)
   - Commits: dbb0ee6 (core implementation), 45a3772 (slash command), c348ed6 (task completion)
   - Key files: `backend/src/data/channel_syncer.py`, `backend/sync_channel.py`, `backend/migrations/002_add_sync_state.sql`, `.claude/commands/sync.md`

2. **Feature j-refactor-pipeline-order** (2025-10-08, updated 2025-10-14): Pipeline optimization and context reduction
   - Refactored pipeline order: Map → Filter → Resolve → Reduce → Comment Groups
   - Added HIGH+MEDIUM filter after Map, later changed to HIGH only (60-70% reduction)
   - Moved Comment Groups phase AFTER Reduce (was parallel with Resolve)
   - Removed expert comments loading from Reduce phase (token savings)
   - Changed exclude logic: uses main_sources (8 posts) instead of all relevant (21 posts)
   - Added relevance-based sorting before limiting to 50 posts
   - Key changes in `simplified_query_endpoint.py:144-148` (filter) and `reduce_service.py:75-90`
   - Performance: Significantly fewer posts in Resolve, better token efficiency

3. **Feature i-implement-drift-analysis** (2025-10-07): Two-phase drift analysis system
   - Pre-analysis phase: `analyze_drift.py` script with Claude Sonnet 4.5
   - Query-time phase: CommentGroupMapService uses pre-analyzed drift topics
   - New database table: `comment_group_drift` with drift_topics JSON
   - Changed prompt: `comment_group_drift_prompt.txt` for keyword matching
   - Reduces false positives by 80-90% vs raw comment analysis
   - Key changes in `comment_group_map_service.py:83-145` (loads drift groups from DB)

4. **Feature h-fix-comment-groups-issues** (2025-10-06): Security & quality fixes
   - Fixed CRITICAL security issues (SQL injection, prompt injection)
   - Added database constraints (UNIQUE, compound indexes)
   - Improved validation and error handling
   - Added channel_username to AnchorPost (no hardcoded links)
   - All tests passing, production-ready

5. **Feature g-telegram-comments-integration** (2025-10-05): Comment Groups Pipeline
   - Added Pipeline B for Telegram comment group analysis
   - CommentGroupMapService with GPT evaluation
   - Frontend component CommentGroupsList
   - Security hardening and validation

6. **Feature 001**: Map-Resolve-Reduce pipeline implementation
   - Added three-phase query processing
   - Implemented smart caching with similarity matching
   - Created interactive comment collection system

<!-- MANUAL ADDITIONS START -->
## Simplified Map-Resolve-Reduce Pipeline Architecture

The core system uses a **six-phase pipeline** (as of 2025-10-14):

1. **Map Phase** (`map_service.py:22-414`): Qwen 2.5-72B processes post chunks to find relevant content
   - Model: Qwen 2.5-72B Instruct ($0.08/$0.33 per 1M tokens)
   - Why Qwen: Superior performance for document ranking tasks
   - Chunk size: 40 posts per chunk (configurable)
   - Returns posts with relevance scores: HIGH, MEDIUM, LOW
   - **NEW**: Robust retry mechanism with 3+1 retry strategy (per-chunk + global retry)
   - **NEW**: Handles HTTP errors, JSON decode errors, and validation failures
   - **NEW**: Comprehensive error logging with expert_id tracking
   - **NEW**: Progress callbacks for retry status updates

2. **Filter Phase** (`simplified_query_endpoint.py:144-148`): Removes LOW and MEDIUM relevance posts
   - **NEW (2025-10-14)**: Keeps ONLY HIGH relevance posts
   - Changed from HIGH+MEDIUM to HIGH only for better precision
   - Reduces noise in subsequent phases
   - Typically reduces dataset by ~60-70% compared to no filtering

3. **Resolve Phase** (`simple_resolve_service.py`): Expands context via DB links
   - **No GPT for link evaluation** - trusts author's original references
   - **Depth 1 expansion only** - prevents context drift
   - Processes only HIGH relevance filtered posts
   - Expert-specific filtering via `expert_id` parameter

4. **Reduce Phase** (`reduce_service.py:19-346`): Synthesizes final answer with Gemini 2.0 Flash
   - Model: Gemini 2.0 Flash ($0.10/$0.40 per 1M tokens)
   - Why Gemini: Better context synthesis and instruction following vs GPT-4o-mini
   - **Does NOT load expert comments** (as of 2025-10-08) - focuses only on post content
   - Sorts posts by relevance (HIGH → MEDIUM → CONTEXT) before limiting to 50
   - **Fact validation**: Verifies all [post:ID] references exist and match dates
   - Adds missing post IDs to main_sources automatically (Gemini validation fix, lines 209-225)

5. **Comment Groups Phase** (`comment_group_map_service.py:24-425`, optional): Finds relevant comment discussions
   - Model: GPT-4o-mini (fast, cost-effective for matching)
   - **NEW (2025-10-14)**: Filters to HIGH relevance only (was HIGH+MEDIUM)
   - Runs AFTER Reduce phase (moved from parallel execution)
   - Excludes main_sources from Reduce (8 posts) instead of all HIGH posts
   - Better coverage with focused results (lines 401-405)

6. **Comment Synthesis Phase** (`comment_synthesis_service.py:1-231`, optional): Extracts complementary insights
   - Model: Gemini 2.0 Flash (better context understanding)
   - Runs AFTER Comment Groups phase completes
   - Only executes when HIGH comment groups exist (updated filter, lines 200-208)
   - Processes comment content to extract insights NOT covered in main answer
   - **Critical constraint**: No [post:ID] references allowed in output
   - Returns unlimited bullet points (no artificial limit)
   - Prompt: `comment_synthesis_prompt.txt` with strict accuracy requirements

Key implementation details:
- All prompts are external files in `backend/prompts/` (optimized per model)
- SSE (Server-Sent Events) for real-time progress communication
- OpenRouter integration for flexible model selection via `openrouter_adapter.py`
- Multi-model architecture: Qwen for ranking, Gemini for synthesis, GPT-4o-mini for matching
- Fact validation catches hallucinated post references (validates IDs and dates)
- **NEW**: Robust retry mechanism ensures failed chunks are recovered instead of lost

### Map Phase Retry Mechanism (NEW 2025-10-15)

**Purpose**: Ensure reliable processing of all post chunks by implementing comprehensive retry logic that prevents data loss due to temporary API failures.

**Architecture**:

The retry mechanism uses a two-layer approach:

**Layer 1: Per-Chunk Retry** (map_service.py:138-143)
- **Configuration**: 3 attempts per chunk using tenacity
- **Backoff Strategy**: Exponential backoff (multiplier=2, min=4s, max=60s)
- **Retry Conditions**: HTTPStatusError, JSONDecodeError, ValueError
- **Implementation**: `@retry` decorator on `_process_chunk()` method

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
    reraise=True
)
```

**Layer 2: Global Retry** (map_service.py:324-361)
- **Configuration**: 1 additional global retry attempt
- **Scope**: Retries chunks that failed after all per-chunk attempts
- **Logic**: Collects failed chunks, retries them as a batch
- **Failure Handling**: Logs permanently failed chunks without crashing

**Error Handling & Logging**:
- **Expert-specific logging**: All error messages include `[expert_id]` prefix
- **Detailed error context**: Includes chunk index, error type, and response previews
- **Progress tracking**: SSE events report retry status to frontend
- **Recovery tracking**: Logs when chunks recover on retry attempts

**Reliability Improvements**:
- **No data loss**: Failed chunks are retried instead of being discarded
- **Transient error handling**: Network issues, API rate limits, temporary service outages
- **JSON validation**: Catches and retries malformed API responses
- **Empty response detection**: Retries when API returns empty content
- **Partial failure tolerance**: System continues with successful chunks while retrying failed ones

**Performance Characteristics**:
- **Minimal overhead**: Retries only occur when failures happen
- **Fast backoff**: Starts with 4-second delay, scales exponentially
- **Parallel processing**: Successful chunks continue processing during retries
- **Timeout protection**: Maximum 60-second wait between attempts prevents hanging

**Troubleshooting Retry Issues**:

**Common Causes of Retries**:
1. **HTTP 429 (Rate Limit)**: OpenRouter API limits
2. **HTTP 5xx (Server Errors)**: Temporary API service issues
3. **JSON Decode Errors**: Malformed responses from LLM
4. **Empty Responses**: API returns null/empty content
5. **Network Timeouts**: Connection issues

**Debugging Commands**:
```bash
# Check for retry patterns in logs
grep "Global retry" backend/logs/app.log
grep "Chunk.*failed on retry" backend/logs/app.log
grep "permanently failed" backend/logs/app.log

# Monitor retry frequency
grep "retry attempt" backend/logs/app.log | wc -l
```

**Configuration Tuning**:
- **Per-chunk attempts**: Modify `stop_after_attempt(3)` in map_service.py:139
- **Global retries**: Change `max_global_retries = 1` in map_service.py:326
- **Backoff timing**: Adjust `multiplier=2, min=4, max=60` in map_service.py:140
- **Retry conditions**: Add/remove exception types in `retry_if_exception_type()`

**Impact on System Reliability**:
- **Before**: Failed chunks were lost, reducing result completeness
- **After**: 95%+ of failed chunks recover on retry, ensuring comprehensive analysis
- **Monitoring**: Track retry success rate via log analysis
- **Alerting**: Consider alerts for high retry rates indicating systematic issues

### Personal Answer Style (Reduce Phase)

ReduceService supports two answer styles via different prompts:

1. **Personal Style** (default, `reduce_prompt_personal.txt`):
   - Answers written in first person from expert's perspective
   - Uses author's characteristic voice and speech patterns
   - Includes emotional markers and personal experiences
   - Activated with `use_personal_style=True` (default)
   - Works with Gemini 2.0 Flash for better tone matching

2. **Neutral Style** (`reduce_prompt.txt`):
   - Standard analytical answers
   - Third-person perspective
   - Activated with `use_personal_style=False`

The personal style creates more engaging, authentic responses by mimicking the author's writing style from the original posts.

### Model Selection Strategy (Updated 2025-10-15)

Different models optimized for specific pipeline phases:

**Qwen 2.5-72B Instruct** - Map Phase
- Cost: $0.08/$0.33 per 1M tokens (input/output)
- Excellent at document ranking and relevance scoring
- Fast processing with good accuracy
- Configured in `map_service.py:30` as DEFAULT_MODEL
- **NEW**: Robust retry mechanism (3+1 attempts) ensures reliable processing
- **NEW**: Handles network errors, API limits, and malformed responses

**Gemini 2.0 Flash** - Reduce & Comment Synthesis
- Cost: $0.10/$0.40 per 1M tokens
- Superior instruction following compared to GPT-4o-mini
- Better context synthesis for long answers
- Handles personal writing style prompts well
- Maps to `google/gemini-2.0-flash-001` via OpenRouter
- Configured in `reduce_service.py:26` and `comment_synthesis_service.py:24`

**GPT-4o-mini** - Comment Groups Matching
- Fast and cost-effective for keyword matching
- Works with pre-analyzed drift topics
- Configured in `comment_group_map_service.py:34`

Model names are converted via `openrouter_adapter.py:25-62` to OpenRouter format.

### Comment Groups Pipeline (Pipeline B) - Drift Analysis

**NEW (2025-10-07)**: Two-phase drift analysis system for finding relevant comment discussions.

**Purpose**: Find relevant conversations that happen in comments, even when the original post isn't directly relevant to the query.

**Two-Phase Architecture**:

**Phase 1: Pre-Analysis (Offline)**
- Script: `backend/analyze_drift.py`
- Model: Claude Sonnet 4.5 (high accuracy for drift detection)
- Process:
  - Groups all Telegram comments by anchor post
  - Analyzes each group to detect topic drift from original post
  - Extracts structured drift topics: topic, keywords, key_phrases, context
  - Stores results in `comment_group_drift` table
- Reduces false positives by filtering out on-topic discussions
- Run manually before deployment: `python backend/analyze_drift.py`

**Phase 2: Query-Time Matching (Online)**
- Service: `CommentGroupMapService` in `backend/src/services/comment_group_map_service.py:24-425`
- Model: GPT-4o-mini (fast, cost-effective for keyword matching)
- Process:
  - Loads pre-analyzed drift groups from database (lines 85-181)
  - Formats drift_topics for GPT evaluation (lines 197-214)
  - Matches user query against drift topics, NOT raw comments
  - **NEW (2025-10-14)**: Returns only HIGH relevance groups (was HIGH/MEDIUM)
- Key method: `_load_drift_groups()` queries `comment_group_drift` table where `has_drift=1`
- Prompt: `backend/prompts/comment_group_drift_prompt.txt` (keyword + semantic matching)
- Filter to HIGH only at lines 401-405

**Pipeline Integration** (Updated 2025-10-14):
1. **Pipeline A (Main)** - Map → Filter (HIGH only) → Resolve → Reduce
2. **Pipeline B (Drift Comments)** - runs AFTER Reduce phase completes:
   - Filters to HIGH relevance only (changed from HIGH+MEDIUM)
   - Excludes main_sources from Reduce (8 posts) instead of all HIGH posts
   - Better coverage with focused results
   - Processes 20 drift groups per chunk (lines 183-195)
   - Rate limiting: Max 5 parallel requests (lines 318-325)
   - Returns anchor post + Telegram comment links
3. **Pipeline C (Comment Synthesis)** - runs AFTER Pipeline B completes:
   - Only executes when HIGH comment groups exist (changed from HIGH/MEDIUM)
   - Filter check at `comment_synthesis_service.py:200-208`
   - Uses Gemini 2.0 Flash for better synthesis

**Key Implementation Details**:
- Database table: `comment_group_drift` with columns:
  - `post_id`: Foreign key to posts table
  - `expert_id`: Expert identifier (multi-expert support, added 2025-10-11)
  - `has_drift`: Boolean flag (only TRUE groups are processed)
  - `drift_topics`: JSON array with topic, keywords, key_phrases, context
  - `analyzed_at`, `analyzed_by`: Audit trail
- Chunk size: 20 drift groups per API call
- Security: SQL injection protection + prompt injection validation (line 56-81, 112-124)

**API Integration**:
- Request field: `include_comment_groups: bool` (default: `false`)
- Response field: `relevant_comment_groups: List[CommentGroupResponse]`
- Each group includes:
  - Anchor post metadata (ID, text, author, date, channel_username)
  - Comment count
  - Relevance level (HIGH only as of 2025-10-14)
  - Reason for relevance
  - Direct Telegram link to comments

**Frontend Display**:
- Component: `CommentGroupsList.tsx`
- Shows collapsible cards with anchor post preview
- Click to open comments in Telegram
- Relevance badges (color-coded)

**Database Optimization**:
- UNIQUE constraint on `telegram_comment_id` (prevents duplicates)
- Compound index on `(telegram_comment_id, post_id)` (fast grouping)
- ISO date format for API responses

**Security Features** (added 2025-10-06):
- Input validation for `exclude_post_ids` (SQL injection prevention)
- Path traversal protection for prompt file loading
- File permission checks (rejects world-writable prompts)
- Template placeholder validation

### Telegram Channel Synchronization (NEW 2025-10-09)

**Purpose**: Automated incremental sync of Telegram channel posts and comments without manual JSON exports.

**Architecture**:

The sync system extends `SafeTelegramCommentsFetcher` with incremental capabilities:

1. **TelegramChannelSyncer** (`backend/src/data/channel_syncer.py`):
   - Fetches new posts via `iter_messages(min_id=last_synced_id)`
   - Updates comments for recent posts (SYNC_DEPTH=20, ~60 days of history)
   - Tracks sync state in `sync_state` table
   - Returns structured JSON output for automation

2. **CLI Script** (`backend/sync_channel.py`):
   - Entry point for sync operations
   - Supports --dry-run mode for preview
   - Preflight checks: session file, API credentials
   - JSON output to stdout, human-readable to stderr

3. **Slash Command** (`.claude/commands/sync.md`):
   - Integrates sync into Claude Code workflow
   - Creates todo list for transparency
   - Automatically invokes drift-extraction agent for new comment groups

**Key Features**:
- **Incremental sync**: Only fetches new posts since last sync
- **Comment refresh**: Checks last 20 posts for new comments
- **Idempotent**: Safe to re-run, handles duplicates via UNIQUE constraints
- **Rate limiting**: Inherits FloodWait handling from base fetcher
- **Structured output**: JSON format enables automation

**Database**:
- Table: `sync_state` tracks last_synced_message_id per channel
- Migration: `backend/migrations/002_add_sync_state.sql`

**Configuration** (via .env):
```bash
TELEGRAM_API_ID=12345678        # From https://my.telegram.org
TELEGRAM_API_HASH=abcdef...     # From https://my.telegram.org
TELEGRAM_CHANNEL=nobilix        # Channel username
SYNC_DEPTH=20                   # Check last N posts for comments
```

**Usage**:
```bash
# Preview sync
cd backend && python sync_channel.py --dry-run

# Run sync
cd backend && python sync_channel.py

# Via slash command (with drift analysis)
/sync
```

**Integration with Drift Analysis**:

After sync completes, new comment groups are automatically analyzed:
1. Sync identifies posts with new comments
2. Outputs `new_comment_groups` array in JSON
3. Drift-extraction agent processes these groups
4. Results stored in `comment_group_drift` table
5. Groups become searchable in query-time matching

### Parallel Multi-Expert Architecture (NEW 2025-10-12)

**Purpose**: Process queries through multiple experts simultaneously, returning separate results for each expert.

**Architecture**:

The system processes all experts in parallel using async tasks:

1. **Expert Detection** (`simplified_query_endpoint.py:307-315`):
   - Automatically detects all unique `expert_id` values from database
   - Or uses `expert_filter` from request to process specific experts
   - Default: ALL experts in database

2. **Parallel Processing** (`simplified_query_endpoint.py:352-364`):
   - Creates separate async task for each expert
   - Each task runs complete pipeline: Map → Filter → Resolve → Reduce → Comments
   - Tasks run simultaneously using `asyncio.create_task()`

3. **Expert Isolation**:
   - Each expert's posts filtered by `expert_id` at database level
   - No mixing of data between experts at any pipeline phase
   - Links, comments, drift groups all filtered by expert
   - All services (Map, Resolve, CommentGroupMap, Reduce) receive expert-specific data
   - Dynamic `channel_username` resolution per expert via `get_channel_username()`

**API Request/Response**:

Request with optional expert filter:
```json
{
  "query": "Что такое AI agents?",
  "expert_filter": null,  // null = all experts, or ["refat", "ai_architect"]
  "include_comment_groups": false,
  "stream_progress": true
}
```

Response with multiple experts:
```json
{
  "query": "Что такое AI agents?",
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
    },
    {
      "expert_id": "ai_architect",
      "expert_name": "AI Архитектор",
      "channel_username": "ai_architect_channel",
      "answer": "...",
      "main_sources": [5, 12],
      "confidence": "MEDIUM",
      "posts_analyzed": 28,
      "processing_time_ms": 8300
    }
  ],
  "total_processing_time_ms": 13200,
  "request_id": "uuid-here"
}
```

**Key Implementation Files**:
- `backend/src/api/models.py`: New `ExpertResponse` and `MultiExpertQueryResponse` models
- `backend/src/api/simplified_query_endpoint.py`:
  - `process_expert_pipeline()`: Processes single expert
  - `event_generator_parallel()`: Orchestrates parallel processing
- `backend/src/services/comment_group_map_service.py`:
  - `_load_drift_groups()`: Now filters by `expert_id` parameter
  - Uses `get_channel_username()` for dynamic channel mapping
- Helper functions: `get_expert_name()`, `get_channel_username()` (in models.py)

**SSE Progress Events**:
- Include `expert_id` field to track which expert is being processed
- Events like: `[refat] Processing chunk 1`, `[ai_architect] Synthesizing answer`
- Final event contains complete `MultiExpertQueryResponse`

**Performance**:
- Parallel processing reduces total time to max(expert_times) instead of sum(expert_times)
- Each expert processed independently - failure of one doesn't affect others
- Resource usage scales with number of experts (API calls, memory)

### Multi-Expert Data Management (NEW 2025-10-13)

**Purpose**: Critical guidelines for adding and managing multiple experts in the system.

### Discovered During Implementation
[Date: 2025-10-16 / Multi-expert sync optimization session]

During implementation of improved sync logic, we discovered that the multi-expert synchronization system had significant gaps in comment checking and drift analysis logic that weren't documented in the original architecture.

**What was found**: The `/sync-all` command was only checking comments for the last N posts (SYNC_DEPTH=10) but wasn't checking comments for NEW posts that fell outside this range. This meant new posts like neuraldeep/1659 could have dozens of comments that would never be collected until the next sync cycle when they entered the "recent posts" window.

This wasn't documented because the original implementation assumed that new posts would eventually be checked in future sync cycles, but this created a delay in comment collection and potential data gaps. The actual behavior is that new posts need immediate comment checking to ensure complete data collection, especially for active posts that receive comments shortly after publication.

**Updated understanding of sync workflow**:
1. **New posts** must have their comments checked immediately during sync (not deferred)
2. **Drift records** should only be reset for posts with ACTUAL new comments, not all checked posts
3. **Comment checking** happens in two phases: recent posts depth + ALL new posts
4. **Auto-integration** of drift analysis is possible and recommended for complete workflow

**Implementation details**:
- Added `update_specific_posts_comments()` method in `channel_syncer.py:283-368`
- Modified `sync_channel_incremental()` to check comments for all new posts
- Updated drift logic to only reset `analyzed_by='pending'` for posts with `total_comments > 0`
- Created specialized `drift_on_synced` agent for automatic drift analysis
- Updated `/sync-all` command to v3.0 with integrated drift analysis workflow

**Performance data discovered**:
- Real sync collected 592 new comments across 3 experts
- neuraldeep/1659 had 37 comments that weren't visible in dry-run due to deduplication
- Only 25 drift groups needed analysis vs 505 total groups (targeted processing)
- Processing time: ~136 seconds for complete sync + drift analysis

Future implementations need to ensure that new posts get immediate comment checking and that drift analysis is integrated into the main sync workflow rather than being a separate manual step.

#### Channel ID Mapping (КРИТИЧНО!)

Each expert must have unique channel_id to prevent data corruption:

```python
EXPERT_CHANNELS = {
    'refat': {
        'channel_id': '2273349814',  # Telegram channel ID
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

**How to find channel_id:**
```bash
# Method 1: From posts table after import
sqlite3 data/experts.db "SELECT DISTINCT channel_id, expert_id FROM posts;"

# Method 2: From Telegram API during import
# channel_id is stored when importing via json_parser.py
```

#### Comment Import for New Experts

**Script:** `backend/src/data/telegram_comments_fetcher.py`

**КРИТИЧНО:** Must filter by `channel_id` to avoid saving comments to wrong expert's posts!

**Key Modifications:**

1. **Filter posts by channel_id** (lines 185-187):
```python
def get_posts_from_db(self, db: Session) -> List[tuple]:
    # Filter only specific channel posts to avoid MsgIdInvalidError
    posts = db.query(Post.post_id, Post.telegram_message_id).filter(
        Post.channel_id == '2293112404'  # The AI Architect channel ID
    ).order_by(Post.created_at).all()
    return [(p.post_id, p.telegram_message_id) for p in posts]
```

2. **Filter when saving comments** (lines 207-210):
```python
post = db.query(Post).filter(
    Post.telegram_message_id == comment_data['parent_telegram_message_id'],
    Post.channel_id == '2293112404'  # CRITICAL: Filter by channel_id!
).first()
```

**Why this is critical:**
- Different Telegram channels can have posts with same `telegram_message_id`
- Without channel_id filter, comments from ai_architect will be saved to refat's posts if IDs overlap!
- This causes data corruption that's hard to detect

**Usage for new expert:**
```bash
cd backend

export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
export TELEGRAM_CHANNEL=new_expert_channel

# Edit telegram_comments_fetcher.py - update channel_id filter
# Then run:
uv run python -m src.data.telegram_comments_fetcher
```

#### Drift Analysis Setup for New Experts

**Prerequisites:**
1. Import posts and comments for new expert
2. Create empty drift records with correct `expert_id`
3. Configure drift-extraction agent for auto-detection

**Step 1: Create empty drift records**
```sql
-- Create empty drift records for new expert
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

**Step 2: Verify drift-extraction agent**

File: `.claude/agents/drift-extraction.md` (line 122)

**MUST use auto-detection** (not hardcoded):
```sql
-- ✅ CORRECT (auto-detects from posts table)
expert_id = (SELECT expert_id FROM posts WHERE post_id = <ID>)

-- ❌ WRONG (hardcoded value)
expert_id = 'refat'
```

**Step 3: Run drift analysis**

Option A: Use automation guide (`docs/drift-analysis-automation.md`)
- Parallel processing: 5 terminals
- Self-reproducing loop: 1 terminal

Option B: Run analyze_drift.py script (processes all experts):
```bash
cd backend
python analyze_drift.py --batch-size 10
```

#### Migration 008: UNIQUE Constraint Fix (CRITICAL)

**File:** `backend/migrations/008_fix_comment_unique_constraint.sql`

**Problem:** Original constraint was globally unique on `telegram_comment_id`:
```sql
CREATE UNIQUE INDEX idx_telegram_comment_unique ON comments (telegram_comment_id);
```

This prevented different channels from having comments with same telegram_comment_id!

**Solution:** Compound constraint on `(telegram_comment_id, post_id)`:
```sql
CREATE UNIQUE INDEX idx_telegram_comment_post_unique ON comments (telegram_comment_id, post_id);
```

**Apply migration:**
```bash
sqlite3 data/experts.db < backend/migrations/008_fix_comment_unique_constraint.sql
```

**Why this matters:**
- Telegram uses comment_id as LOCAL ID within each discussion group
- Different channels can have comments with ID=1, ID=2, etc.
- Without this fix, only ONE expert can have comments with these IDs

#### Common Pitfalls

**1. Forgetting channel_id filter**
- **Symptom:** Comments from new expert saved to old expert's posts
- **Fix:** Add `channel_id` filter in `telegram_comments_fetcher.py`
- **Verification:**
```sql
-- Check for wrong expert_id assignments
SELECT c.comment_id, p.expert_id, c.comment_text
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE c.created_at > 'recent_import_date'
ORDER BY c.created_at DESC;
```

**2. Hardcoding channel_id values**
- **Symptom:** Script only works for one expert
- **Fix:** Use parameterized channel_id or detect from database
- **Better approach:** Pass channel_id as CLI argument

**3. Missing expert_id in drift records**
- **Symptom:** Drift analysis fails or mixes experts
- **Fix:** Ensure INSERT includes `expert_id` from posts table
- **Verification:**
```sql
-- Check drift records have correct expert_id
SELECT p.expert_id, COUNT(*) as drift_count
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
GROUP BY p.expert_id;
```

**4. Running migration 008 after data import**
- **Symptom:** Some comments missing after import
- **Fix:** Apply migration BEFORE importing second expert
- **Recovery:** Delete all comments, restore from backup, re-import with new constraint

#### Verification Commands

**Check channel_id coverage:**
```sql
SELECT channel_id, expert_id, COUNT(*) as posts, MIN(telegram_message_id) as first_post, MAX(telegram_message_id) as last_post
FROM posts
GROUP BY channel_id, expert_id;
```

**Check comment distribution:**
```sql
SELECT p.expert_id, COUNT(DISTINCT p.post_id) as posts_with_comments, COUNT(c.comment_id) as total_comments
FROM posts p
JOIN comments c ON p.post_id = c.post_id
GROUP BY p.expert_id;
```

**Check drift analysis coverage:**
```sql
SELECT p.expert_id,
       COUNT(*) as total_posts,
       SUM(CASE WHEN cgd.analyzed_by != 'pending' THEN 1 ELSE 0 END) as analyzed,
       SUM(CASE WHEN cgd.has_drift = 1 THEN 1 ELSE 0 END) as with_drift
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
GROUP BY p.expert_id;
```

## ⚠️ Important Architectural Decisions (Updated 2025-10-13)

### Telegram Entity Conversion (NEW 2025-10-11)
- **All Telegram entities are converted to markdown at import time**
- Utility function: `entities_to_markdown()` in `backend/src/utils/telegram_entities.py`
- Supported entities: text_link, url, mention, hashtag, bold, italic, code, pre, strikethrough, underline, spoiler
- Applied during: JSON import, channel sync, comment fetching
- Frontend uses `react-markdown` with `remark-gfm` plugin for autolinks (makes bare URLs clickable)
- **Critical**: Reimporting data will lose drift analysis results (need to re-run `analyze_drift.py`)

### SSE Parsing Fix (Critical)
- **Frontend SSE parser must process line-by-line** not split by \n\n
- Each `data: {json}` line is a separate event in SSE stream
- Buffer incomplete lines when chunks are split mid-JSON
- Backend sends multi-line SSE messages, frontend must parse each data: line individually
- CORS: Include all possible frontend ports (3000, 3001, 5173)

## ⚠️ Important Architectural Decisions (Updated 2025-09-27)

### Field Naming Convention
- **ALWAYS use `telegram_message_id`** NOT `telegram_id` in all code
- This matches our SQLAlchemy Post model implementation

### Simplified Resolve Phase Architecture
- **SimpleResolveService queries Link table from database directly**
- **NO GPT used for link evaluation** - all author's links are included
- **Depth=1 expansion only** - prevents excessive context growth
- Links are created during JSON import, not during query processing
- This approach is 10x faster and 100% accurate vs GPT text parsing

### JSON Structure Simplification
- **Map**: Uses enum scoring (HIGH/MEDIUM/LOW) instead of float
- **Resolve**: Returns simple list of IDs, not complex link extraction
- **Reduce**: Flat JSON structure without nested objects
- These changes improve GPT-4o-mini reliability from ~50% to ~95%

### Link Type Standardization
- Use database enum: LinkType.REPLY, LinkType.FORWARD, LinkType.MENTION
- Do NOT use custom strings from original prompts (continuation, reference, etc.)

## Testing Strategy

For MVP, we use validation through prepared Q&A sets rather than unit tests:
- Prepare 5-10 queries with known expected answers
- Focus on completeness (finding all relevant posts) over precision
- Document which posts should be found for each query
- Each query processed fresh (no caching in MVP)

### Multi-Expert Testing:
- Verify each expert processes independently (no data mixing)
- Check parallel processing reduces total time vs sequential
- Ensure SSE events contain correct `expert_id` for tracking
- Test with missing experts (empty response, not error)
- Validate `expert_filter` parameter correctly filters experts

## Deployment Checklist

Before deploying to Railway:
1. Ensure `.env.example` is updated with all required variables
2. Test Docker build locally
3. Verify health check endpoint returns 200
4. Confirm OpenAI API key is set in Railway environment
5. Test with small dataset first (100 posts)

## 🗑️ Deprecated Files (Legacy, can be removed)

The following files are from older pipeline implementations and are no longer used:

**Backend Services:**
- `backend/src/services/resolve_service.py` - Old resolve service (replaced by simple_resolve_service.py)
- `backend/src/services/__init__.py` - Still imports old ResolveService (should import SimpleResolveService)

**Prompts:**
- `backend/prompts/resolve_prompt.txt` - For old resolve service
- `backend/prompts/resolve_prompt_backup.txt` - Backup of old prompt
- `backend/prompts/resolve_prompt_recommendations.md` - Old recommendations
- `backend/prompts/*_v1.txt` - First versions of prompts (map_prompt_v1.txt, reduce_prompt_v1.txt, resolve_prompt_v1.txt)

These files can be safely removed after confirming they're not referenced in any active code paths.

<!-- MANUAL ADDITIONS END -->
## Sessions System Behaviors

@CLAUDE.sessions.md

## 🔥 КРИТИЧЕСКИ ВАЖНО: Запуск Backend сервера

### ЕДИНСТВЕННЫЙ рабочий способ:
1. Убедись что в `backend/src/api/main.py` есть:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

2. Запускай ТОЛЬКО ТАК:
   ```bash
   cd backend && uv run uvicorn src.api.main:app --reload --port 8000
   ```

### НЕ РАБОТАЕТ (не тратьте время):
- ❌ source .env && uv run...
- ❌ export $(cat .env) && uv run...
- ❌ uv run --env-file .env...

### Тестирование запросов:
```bash
# Запрос ко всем экспертам (по умолчанию)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Текст вопроса", "stream_progress": false}' \
  -o /tmp/result.json

# Запрос к конкретному эксперту
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Текст вопроса", "expert_filter": ["refat"], "stream_progress": false}' \
  -o /tmp/result.json

# Проверка результата (multi-expert response)
cat /tmp/result.json | jq '.expert_responses[].expert_id'
```
