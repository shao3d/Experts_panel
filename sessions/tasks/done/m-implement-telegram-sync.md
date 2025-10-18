---
task: m-implement-telegram-sync
branch: feature/telegram-sync
status: completed
created: 2025-10-08
completed: 2025-10-09
modules: ["telegram_sync", "channel_syncer", "drift_analysis", "cli"]
---

# Implement Telegram Channel Sync with Drift Analysis

## Problem/Goal

Создать автоматическую систему синхронизации канала Telegram Рефата с локальной БД:
- Incremental sync новых постов и комментариев
- Обновление комментариев на последние 3 поста (для новых комментов к старым постам)
- Автоматический запуск drift analysis на новые comment groups
- Управление через todo workflow в Claude Code

## Success Criteria (MVP)

- [x] `sync_state` table создана в БД
- [x] `TelegramChannelSyncer` класс реализован (incremental sync + depth=3 для комментариев)
- [x] `sync_channel.py` CLI скрипт работает с `--dry-run` режимом
- [x] JSON output: `{new_posts, new_comment_groups, stats}`
- [x] `/sync` слэш-команда запускает скрипт через todo workflow
- [x] Можно передать `new_comment_groups` в drift-extraction agent
- [x] End-to-end работает: sync → drift agent → БД обновлена

## Architectural Design

### Workflow
```
User: /sync (или "синхронизируй канал")
  ↓
Claude Code creates todo list:
1. ☐ Preflight checks (session, API keys, DB)
2. ☐ Запустить sync_channel.py --dry-run (preview)
3. ☐ Спросить подтверждение пользователя
4. ☐ Запустить sync_channel.py (real sync)
5. ☐ Парсить JSON output → получить new_comment_groups
6. ☐ Запустить drift-extraction agent с new_comment_groups
7. ☐ Показать summary результата
```

### Files Structure (MVP)
```
backend/
├── sync_channel.py            # CLI entry point
├── src/data/
│   └── channel_syncer.py      # TelegramChannelSyncer класс
└── migrations/
    └── 002_add_sync_state.sql # sync_state table

.claude/commands/
└── sync.md                     # /sync команда (опционально)
```

### Configuration (from .env)
```bash
# Добавить в .env:
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef...
TELEGRAM_CHANNEL=nobilix
SYNC_DEPTH=3
```

### JSON Output Format
```json
{
  "success": true,
  "new_posts": [134, 135, 136],
  "updated_posts": [131, 132, 133],
  "new_comment_groups": [134, 135],
  "stats": {
    "total_posts": 3,
    "total_comments": 47,
    "groups_need_drift": 2,
    "duration_seconds": 323
  }
}
```

### Preflight Checks (MVP - только 2)
```python
✓ Telegram session file exists (.session)
✓ API credentials in .env (TELEGRAM_API_ID, TELEGRAM_API_HASH)
```

## Context Manifest

### How the Current Telegram Import System Works

**Entry Point: Manual JSON Export + Comments Fetching**

The current system operates in two completely separate workflows that have never been unified into a single synchronization process:

**Workflow 1: Post Import (Manual JSON Export)**
When the user wants to add posts to the database, they manually export channel data from Telegram Desktop as a JSON file. This JSON file contains the complete message history including text, metadata, media info, and reply relationships. The `json_parser.py` script (lines 1-317) then processes this export:

1. User exports channel via Telegram Desktop → saves `result.json`
2. Run: `python -m src.data.json_parser /path/to/result.json`
3. Parser reads messages array and creates Post records (lines 85-141)
4. For each message, extracts: telegram_message_id, message_text, author info, timestamps, view_count, media_metadata
5. Builds `post_id_map` dictionary mapping telegram_message_id → database post_id (line 96)
6. After all posts imported, creates Link records for replies and text_link mentions (lines 198-242)
7. Commits everything to SQLite database at `data/experts.db`

Critical limitation: This workflow requires manual Telegram Desktop export every time. There's no incremental sync - you must export the entire channel history.

**Workflow 2: Comments Fetching (Live Telegram API)**
After posts are imported, comments must be fetched separately using the Telegram API via the `SafeTelegramCommentsFetcher` class (backend/src/data/telegram_comments_fetcher.py, lines 29-310):

1. Initialize with Telegram API credentials (api_id, api_hash from my.telegram.org)
2. Authenticate via Telethon library, creates session file: `telegram_fetcher.session` (already exists: 49KB file dated Oct 8)
3. For each post in database, calls `get_discussion_replies()` method (lines 86-151)
4. Uses `client.iter_messages(channel, reply_to=post_id)` to fetch all comments (lines 114-137)
5. Extracts comment_text, author_name, author_id, telegram_comment_id, created_at
6. Saves Comment records with foreign key to post_id
7. Rate limiting: 2 second delay between posts (DELAY_BETWEEN_POSTS constant, line 35)
8. FloodWait handling: If Telegram rate limits, waits requested seconds + 10 buffer (lines 73-77)
9. Batch commits every 50 comments for performance (BATCH_COMMIT_SIZE, line 37)

Current stats from database:
- Total posts: 164 (max telegram_message_id: 164)
- Posts with comments: 134
- Drift-analyzed groups: 139
- Session file exists and is authorized

**Why These Workflows Are Separate:**

The JSON export workflow was designed for bulk initial import. It gives you complete post history but requires Telegram Desktop and manual export steps. The comments fetcher uses live API because Telegram Desktop exports don't include comment discussion groups - those only exist via the live API through the replies mechanism.

**The Missing Piece: Incremental Sync**

Neither workflow supports incremental updates. To get new posts, you must re-export the entire channel JSON. To get new comments, you must re-fetch all posts (even those already processed). There's no tracking of "last_synced_message_id" or "which posts had comments updated recently."

This is what we're building: A unified `TelegramChannelSyncer` that can:
1. Fetch NEW posts directly via Telegram API (no JSON export needed) using `iter_messages(min_id=last_synced_id)`
2. Update comments for recent posts only (depth=3 posts back)
3. Track sync state in database so it's idempotent and resumable

### Database Schema and State Management

**Current Tables (data/experts.db):**

```sql
posts (
  post_id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  channel_name TEXT,
  telegram_message_id INTEGER,  -- Telegram's original message ID
  message_text TEXT,
  author_name TEXT,
  author_id TEXT,
  created_at DATETIME NOT NULL,
  edited_at DATETIME,
  view_count INTEGER DEFAULT 0,
  forward_count INTEGER DEFAULT 0,
  reply_count INTEGER DEFAULT 0,
  media_metadata JSON,
  is_forwarded INTEGER DEFAULT 0,
  forward_from_channel TEXT
)
-- Indexes: idx_channel_created, idx_text_search
```

```sql
comments (
  comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,  -- FK to posts.post_id
  comment_text TEXT NOT NULL,
  author_name TEXT NOT NULL,
  author_id TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  telegram_comment_id INTEGER,  -- Telegram's comment ID
  parent_telegram_message_id INTEGER  -- Telegram post ID
)
-- Indexes: idx_post_created, idx_telegram_comment_unique (UNIQUE), idx_telegram_comments
-- Constraint: UNIQUE on telegram_comment_id prevents duplicate imports
```

```sql
links (
  link_id INTEGER PRIMARY KEY,
  source_post_id INTEGER NOT NULL,  -- FK to posts
  target_post_id INTEGER NOT NULL,  -- FK to posts
  link_type TEXT NOT NULL,  -- 'REPLY', 'FORWARD', 'MENTION'
  created_at DATETIME
)
-- Created during JSON import when parsing reply_to_message_id and text_link elements
```

```sql
comment_group_drift (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL UNIQUE,  -- FK to posts.post_id
  has_drift BOOLEAN NOT NULL DEFAULT FALSE,
  drift_topics TEXT,  -- JSON array of {topic, keywords, key_phrases, context}
  analyzed_at TIMESTAMP NOT NULL,
  analyzed_by TEXT NOT NULL  -- e.g., 'sonnet-4.5', 'drift-agent'
)
-- Indexes: idx_drift_has_drift, idx_drift_analyzed_at
-- Migration: backend/migrations/001_create_comment_group_drift.sql
```

**Missing Table (Need to Create):**

```sql
sync_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_username TEXT UNIQUE NOT NULL,  -- e.g., 'nobilix'
  last_synced_message_id INTEGER,  -- Last telegram_message_id we processed
  last_synced_at TIMESTAMP,
  total_posts_synced INTEGER DEFAULT 0,
  total_comments_synced INTEGER DEFAULT 0
)
```

This table will track incremental sync progress. When sync runs:
1. Query: `SELECT last_synced_message_id FROM sync_state WHERE channel_username='nobilix'`
2. Use that ID in `iter_messages(min_id=last_synced_message_id)` to fetch only NEW posts
3. After processing, update: `UPDATE sync_state SET last_synced_message_id=MAX(new_ids), last_synced_at=NOW()`

**Database Session Management Pattern (from existing code):**

```python
from src.models.base import SessionLocal  # Factory from SQLAlchemy sessionmaker
db = SessionLocal()
try:
    # Do database operations
    db.commit()
finally:
    db.close()
```

The `SessionLocal` is defined in `backend/src/models/base.py` (lines 1-21):
- Database URL: `sqlite:///../data/experts.db` (relative to backend directory)
- Engine config: `check_same_thread=False` for SQLite
- Session: autocommit=False, autoflush=False

### Telethon Integration and Rate Limiting Architecture

**SafeTelegramCommentsFetcher Base Class**

This class (backend/src/data/telegram_comments_fetcher.py, lines 29-310) provides all the low-level Telegram API integration we'll extend. Understanding how it works is critical because we inherit from it:

**Initialization Flow:**
```python
fetcher = SafeTelegramCommentsFetcher(
    api_id=int,           # From my.telegram.org
    api_hash=str,         # From my.telegram.org
    session_name=str      # Creates .session file (default: 'telegram_fetcher')
)
```

When initialized, it doesn't connect yet. Connection happens in `fetch_all_comments()` via:
```python
self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
await self.client.start()  # Interactive auth on first run, then uses .session file
```

The `.session` file stores auth tokens so you don't re-authenticate every time. Current file: `backend/telegram_fetcher.session` (49KB, already authorized).

**Critical API Method: iter_messages()**

This is Telethon's core method for fetching messages. Current usage in line 114:
```python
async for reply in self.client.iter_messages(
    channel,
    reply_to=post_id,  # Filters for comments replying to this post
    limit=None         # Get ALL comments
):
```

For our sync, we'll use a different variant:
```python
async for message in self.client.iter_messages(
    channel,
    min_id=last_synced_message_id,  # Only messages AFTER this ID
    reverse=True,                    # Oldest first (chronological)
    limit=None                       # Get all new messages
):
```

The `min_id` parameter is what makes incremental sync possible. Telegram's message IDs are sequential per channel, so min_id=164 means "give me all messages with ID > 164."

**Rate Limiting Strategy (Built-in + Custom):**

1. **Telethon's FloodWait Protection** (lines 73-77):
   ```python
   except FloodWaitError as e:
       wait_time = e.seconds + 10  # Telegram says wait X seconds, we wait X+10
       await asyncio.sleep(wait_time)
   ```
   This is automatic retry with the exact wait time Telegram requests. The +10 buffer prevents edge cases.

2. **Manual Delay Between Requests** (line 35, 288):
   ```python
   DELAY_BETWEEN_POSTS = 2.0  # 2 seconds
   await asyncio.sleep(self.DELAY_BETWEEN_POSTS)
   ```
   This proactive delay prevents hitting flood limits in the first place. For a channel with ~1 post every 3 days, this means sync of 3 new posts takes 6 seconds of artificial delay.

3. **Retry Mechanism** (lines 59-84):
   ```python
   async def fetch_with_retry(self, func, *args, **kwargs):
       for attempt in range(self.MAX_RETRIES):  # MAX_RETRIES = 3
           try:
               return await func(*args, **kwargs)
           except FloodWaitError as e:
               # Handle flood wait
           except Exception as e:
               # Wait with exponential backoff: 5s, 10s, 15s
               await asyncio.sleep(5 * (attempt + 1))
   ```

**Stats Tracking Pattern:**
The base class maintains a `self.stats` dict (lines 52-57):
```python
self.stats = {
    'posts_processed': 0,
    'comments_found': 0,
    'comments_saved': 0,
    'errors': 0
}
```

We'll extend this for sync to track:
```python
{
    'new_posts_found': 0,
    'new_posts_saved': 0,
    'posts_updated': 0,  # Posts where we refreshed comments
    'new_comments_found': 0,
    'new_comments_saved': 0,
    'errors': 0,
    'duration_seconds': 0
}
```

**Database Integration Pattern (lines 176-207):**

The base class shows how to safely save comments with duplicate detection:
```python
def save_comments_to_db(self, db: Session, comments: List[Dict[str, Any]]):
    for comment_data in comments:
        # 1. Find post by telegram_message_id
        post = db.query(Post).filter(
            Post.telegram_message_id == comment_data['parent_telegram_message_id']
        ).first()

        # 2. Create Comment with all fields
        comment = Comment(
            post_id=post.post_id,
            comment_text=comment_data['content'],
            # ... other fields
            telegram_comment_id=comment_data['telegram_comment_id']
        )

        # 3. Add to session (batch insert)
        db.add(comment)
```

The UNIQUE constraint on `telegram_comment_id` in the database schema prevents duplicate comments automatically. If we try to insert an existing comment, SQLite raises an IntegrityError, which we can catch and skip.

### Drift Analysis Integration Point

**Two-Phase Drift System Architecture:**

The drift analysis happens in two completely separate phases, and understanding this separation is crucial for the sync integration:

**Phase 1: Pre-Analysis (Offline, Manual Trigger)**

Script: `backend/analyze_drift.py` (lines 1-291)
When to run: After importing new comment groups, before query time
Model: Claude Sonnet 4.5 via OpenRouter (high-accuracy model for drift detection)

Process:
1. Loads ALL posts with comments from database (line 136-140):
   ```python
   posts_with_comments = db.query(Post).join(
       Comment, Post.post_id == Comment.post_id
   ).filter(
       Comment.telegram_comment_id.isnot(None)
   ).distinct().all()
   ```

2. For each post, analyzes if comments DRIFT from anchor post topic (lines 51-125)
3. Uses detailed prompt at `backend/prompts/extract_drift_topics.txt` (200 lines of instructions)
4. Extracts structured JSON: `{has_drift: bool, drift_topics: [{topic, keywords, key_phrases, context}]}`
5. Saves to `comment_group_drift` table (lines 212-251)

Currently: 139 groups analyzed, stored in database

**Phase 2: Query-Time Matching (Online, Fast)**

Service: `CommentGroupMapService` (backend/src/services/comment_group_map_service.py, lines 24-381)
When runs: During user queries, parallel to main Map-Reduce pipeline
Model: GPT-4o-mini (fast, cheap for keyword matching)

Process:
1. Loads pre-analyzed drift groups from database using `_load_drift_groups()` (lines 83-160):
   ```python
   query = db.query(
       comment_group_drift.c.post_id,
       comment_group_drift.c.drift_topics,  # Pre-extracted topics
       Post.telegram_message_id,
       Post.message_text,
       # ...
   ).join(Post).filter(
       comment_group_drift.c.has_drift == True  # Only groups WITH drift
   )
   ```

2. Formats drift_topics for GPT evaluation, NOT raw comments (lines 176-193)
3. Sends user query + drift topics (not full comment text) to GPT-4o-mini
4. GPT matches query against topic keywords and phrases
5. Returns only HIGH/MEDIUM relevance groups

**Why This Two-Phase Design Matters for Sync:**

The sync script will fetch new posts and comments, but those new comment groups won't have drift_topics yet. They need to go through Phase 1 (analyze_drift.py) before they can be found by Phase 2 (query-time matching).

**Sync Integration Strategy:**

After sync completes, we need to identify which comment groups are NEW (not in comment_group_drift table) and run drift analysis on them. The query to find unanalyzed groups:

```sql
SELECT DISTINCT c.post_id, p.telegram_message_id
FROM comments c
JOIN posts p ON c.post_id = p.post_id
LEFT JOIN comment_group_drift cgd ON c.post_id = cgd.post_id
WHERE c.telegram_comment_id IS NOT NULL  -- Only Telegram comments
  AND cgd.post_id IS NULL                -- Not yet analyzed
GROUP BY c.post_id
HAVING COUNT(c.comment_id) >= 1          -- Has at least 1 comment
```

**Drift-Extraction Agent Integration:**

There's already an agent for this: `.claude/agents/drift-extraction.md` (lines 1-237). This agent:
- Reads the extraction prompt template
- YOU (Claude Sonnet 4.5) analyze the comments directly (no API call needed - you ARE the model)
- Generates drift_topics JSON
- Saves to database via SQL UPDATE

The sync workflow will invoke this agent via the Task tool, passing the list of new comment group post_ids.

**Expected Workflow After Sync:**
```
1. Sync finds 3 new posts (IDs: 165, 166, 167)
2. Fetches comments for each → finds 2 have discussions (165, 167)
3. Outputs JSON: {"new_comment_groups": [165, 167]}
4. Claude Code parses JSON, invokes drift-extraction agent
5. Agent analyzes posts 165, 167 → extracts drift_topics
6. Saves to comment_group_drift table
7. Now these groups are searchable via CommentGroupMapService
```

### Configuration and Environment Setup

**Current Environment Variables:**

From `.env.example` (lines 1-20):
```bash
# Required for OpenAI API (OpenRouter)
OPENAI_API_KEY=sk-...

# Optional production config
PRODUCTION_ORIGIN=https://...
DATABASE_URL=sqlite:///path/to/database.db  # Defaults to data/experts.db
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

**Missing: Telegram Credentials**

Need to add to `.env.example`:
```bash
# Telegram API Configuration (get from https://my.telegram.org)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+1234567890  # For initial auth only

# Sync Configuration
TELEGRAM_CHANNEL=nobilix  # Channel username
SYNC_DEPTH=3              # Check last N posts for new comments
```

**Proposed Config File: sync_config.yaml**

The task proposes creating a YAML config file (lines 79-92) to avoid hardcoding:

```yaml
telegram:
  channel: nobilix
  sync_depth: 3  # Check last 3 posts for new comments

drift_analysis:
  batch_size: 10
  model: claude-sonnet-4.5

rate_limiting:
  delay_between_posts: 2
  flood_threshold: 60
```

This separates operational config (how many posts to check, rate limits) from secrets (.env file). The sync script will:
1. Load secrets from environment variables (API keys)
2. Load operational config from sync_config.yaml
3. Merge both for runtime configuration

**File Loading Pattern (from CommentGroupMapService, lines 56-81):**

```python
def _load_config(self) -> dict:
    config_path = Path(__file__).parent.parent / "sync_config.yaml"

    # Security: Prevent path traversal
    if not config_path.resolve().is_relative_to(config_path.parent.resolve()):
        raise ValueError(f"Invalid config path")

    # Security: Check file permissions (not world-writable)
    if config_path.stat().st_mode & 0o002:
        raise PermissionError("Unsafe config file permissions")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
```

This security pattern (path validation, permission checks) should be applied to sync_config.yaml loading.

### JSON Output Format and Structured Results

**Why Structured Output Matters:**

The task emphasizes JSON output (lines 94-108) for a critical reason: The sync workflow needs to be parseable by the drift-extraction agent. If sync outputs plain text like "Found 3 new posts", the agent can't programmatically know which post IDs to analyze.

**Proposed Output Schema:**

```json
{
  "success": true,
  "new_posts": [134, 135, 136],           // telegram_message_ids of new posts
  "updated_posts": [131, 132, 133],       // Posts where comments were refreshed
  "new_comment_groups": [134, 135],       // Posts with NEW comments (need drift analysis)
  "stats": {
    "total_posts": 3,
    "total_comments": 47,
    "groups_need_drift": 2,               // Count of new_comment_groups
    "duration_seconds": 323
  },
  "errors": []  // Array of error messages if any
}
```

**Dual Output Strategy:**

The sync script should write BOTH:

1. **Structured JSON to stdout** (for programmatic parsing):
   ```python
   print(json.dumps(result, indent=2))
   ```

2. **Pretty formatted to stderr** (for human reading):
   ```python
   import sys
   from rich.console import Console
   from rich.table import Table

   console = Console(file=sys.stderr)
   console.print("[bold green]✓ Sync complete![/bold green]")
   table = Table(title="Sync Results")
   table.add_row("New posts", str(len(result["new_posts"])))
   # ...
   console.print(table)
   ```

This way, Claude Code can parse stdout JSON while user sees pretty progress on stderr.

**Dry-Run Mode Implementation:**

When `--dry-run` flag is used (line 30, success criteria), the script should:
1. Connect to Telegram and fetch what WOULD be synced
2. Generate the same JSON output structure
3. Set a flag: `"dry_run": true` in JSON
4. NOT write anything to database
5. Show preview: "Would import 3 posts, update 47 comments"

Implementation pattern:
```python
def save_to_db(obj, dry_run=False):
    if dry_run:
        logger.info(f"[DRY-RUN] Would save: {obj}")
        return
    db.add(obj)
    db.commit()
```

### Preflight Checks and Error Handling

**Required Checks Before Sync (lines 110-117):**

The task outlines 5 critical preflight checks. Here's how to implement each:

**1. Telegram Session File Exists:**
```python
session_path = Path(f"{session_name}.session")
if not session_path.exists():
    raise FileNotFoundError(
        f"Telegram session not found: {session_path}\n"
        f"Run: python -m src.data.telegram_comments_fetcher\n"
        f"This will authenticate and create the session file."
    )
```

Current file exists: `backend/telegram_fetcher.session` (49KB), so this check would pass.

**2. API Credentials in Environment:**
```python
import os
required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH']
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    raise EnvironmentError(
        f"Missing environment variables: {', '.join(missing)}\n"
        f"Add to .env file or export them:\n"
        f"export TELEGRAM_API_ID=12345678\n"
        f"export TELEGRAM_API_HASH=abcdef...\n"
        f"Get credentials from: https://my.telegram.org"
    )
```

**3. Database Accessible and Writable:**
```python
db_path = Path("../data/experts.db")
if not db_path.exists():
    raise FileNotFoundError(f"Database not found: {db_path}")

# Test write access
try:
    db = SessionLocal()
    db.execute("SELECT 1")  # Test read
    db.execute("CREATE TEMP TABLE _test (id INTEGER)")  # Test write
    db.close()
except Exception as e:
    raise PermissionError(f"Database not writable: {e}")
```

**4. Claude API Key Present (for drift agent):**
```python
if not os.getenv('OPENAI_API_KEY'):
    logger.warning(
        "OPENAI_API_KEY not found. Drift analysis will fail.\n"
        "Sync will complete but new comment groups won't be analyzed."
    )
    # Not a hard error - sync can continue, drift analysis is optional
```

**5. sync_state Table Exists:**
```python
try:
    db.execute("SELECT 1 FROM sync_state LIMIT 1")
except:
    raise RuntimeError(
        "sync_state table missing. Run migration:\n"
        f"sqlite3 {db_path} < migrations/002_add_sync_state.sql"
    )
```

**Error Message Pattern (from task requirements, line 42):**

All errors should follow this pattern:
```
❌ ERROR: [What went wrong]

How to fix:
1. [Step 1]
2. [Step 2]

For more help: [link to docs or command]
```

Example:
```
❌ ERROR: Telegram session file not found

How to fix:
1. Run: python -m src.data.telegram_comments_fetcher
2. Follow interactive prompts to authenticate
3. Session file will be created automatically

This is a one-time setup. Session file: telegram_fetcher.session
```

### Integration with Todo Workflow and Agent System

**The Todo Workflow Pattern:**

The task requires integration with Claude Code's todo workflow (lines 52-63, success criteria Phase 3). This creates transparency - the user sees each step as it executes:

```
User: /sync

Claude Code creates todo list:
☐ 1. Preflight checks (session, API keys, DB)
☐ 2. Run sync_channel.py --dry-run (preview)
☐ 3. Ask user confirmation
☐ 4. Run sync_channel.py (real sync)
☐ 5. Parse JSON output → get new_comment_groups
☐ 6. Run drift-extraction agent with new_comment_groups
☐ 7. Show summary
```

As each step completes:
```
☑ 1. Preflight checks (session, API keys, DB)
☐ 2. Run sync_channel.py --dry-run (preview)
...
```

**Slash Command Implementation:**

Need to create `.claude/commands/sync.md`:

```markdown
---
name: sync
description: Sync Telegram channel and analyze new comment groups
---

# Sync Telegram Channel

Synchronizes Refat's Telegram channel with local database.

## What this does:
1. Fetches new posts and comments from Telegram
2. Updates recent posts for new comments
3. Runs drift analysis on new comment groups
4. Updates database with all results

## Workflow:
[Create todo list as shown above]

## Prerequisites:
- Telegram session authenticated
- .env file with API credentials
- Database initialized

## Usage:
Just run `/sync` - I'll handle the rest!
```

**Invoking the Drift-Extraction Agent:**

After sync completes, if there are new comment groups, invoke the agent:

```markdown
I need to analyze new comment groups for drift topics.

New groups (post_ids): 165, 167, 169

Please analyze these groups and save drift_topics to the database.
```

The drift-extraction agent will:
1. Read the task description
2. Load each post + comments from database
3. Apply drift detection logic (the agent IS Claude Sonnet 4.5)
4. Generate drift_topics JSON
5. Save via SQL UPDATE to comment_group_drift table

**Summary Report Format (success criteria Phase 4, line 42):**

After all steps complete:

```
╔══════════════════════════════════════════════════════════╗
║        TELEGRAM SYNC COMPLETE                            ║
╚══════════════════════════════════════════════════════════╝

📊 Sync Results:
   • New posts imported: 3 (IDs: 165, 166, 167)
   • Posts updated: 3 (IDs: 162, 163, 164)
   • New comments: 47

🎯 Drift Analysis:
   • New comment groups: 2 (IDs: 165, 167)
   • Drift topics extracted: 5
   • Analysis time: 2m 15s

⏱️  Total Duration: 5m 32s

✅ Database up to date!
   Next sync will start from message ID: 167
```

## Technical Reference Details

### File Locations and Paths

**Backend Structure:**
- Database: `/Users/andreysazonov/Documents/Projects/Experts_panel/data/experts.db`
- Session file: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/telegram_fetcher.session`
- Migrations: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/`
- Prompts: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/prompts/`

**New Files to Create:**
- Config: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/sync_config.yaml`
- Syncer class: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/data/channel_syncer.py`
- CLI script: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/sync_channel.py`
- Migration: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/002_add_sync_state.sql`
- Slash command: `/Users/andreysazonov/Documents/Projects/Experts_panel/.claude/commands/sync.md`

### Key Method Signatures

**TelegramChannelSyncer Class (to implement):**

```python
class TelegramChannelSyncer(SafeTelegramCommentsFetcher):
    """Extends SafeTelegramCommentsFetcher with incremental sync."""

    RECENT_POSTS_DEPTH = 3  # Check last 3 posts for new comments

    async def sync_channel_incremental(
        self,
        channel_username: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch new posts since last sync.

        Returns:
            {
                "success": bool,
                "new_posts": List[int],  # telegram_message_ids
                "updated_posts": List[int],
                "new_comment_groups": List[int],
                "stats": {...},
                "errors": List[str]
            }
        """

    async def update_recent_posts_comments(
        self,
        channel_username: str,
        depth: int = 3,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Refresh comments for last N posts.

        Args:
            channel_username: Channel to sync
            depth: How many recent posts to check
            dry_run: If True, don't save to database
        """

    def calculate_new_comment_groups(self, db: Session) -> List[int]:
        """
        Find posts with comments but no drift analysis.

        Returns:
            List of post_ids that need drift analysis
        """
```

**CLI Entry Point (sync_channel.py):**

```python
async def main():
    parser = argparse.ArgumentParser(description="Sync Telegram channel")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default="sync_config.yaml")
    parser.add_argument("--depth", type=int, help="Override sync_depth")
    args = parser.parse_args()

    # Preflight checks
    run_preflight_checks()

    # Load config
    config = load_config(args.config)

    # Run sync
    syncer = TelegramChannelSyncer(...)
    result = await syncer.sync_channel_incremental(
        channel_username=config['telegram']['channel'],
        dry_run=args.dry_run
    )

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    # Pretty output to stderr
    print_summary(result, file=sys.stderr)
```

### Database Queries

**Get Last Synced Message ID:**
```python
last_id = db.execute(
    "SELECT last_synced_message_id FROM sync_state WHERE channel_username = ?",
    (channel_username,)
).fetchone()
```

**Find Unanalyzed Comment Groups:**
```sql
SELECT DISTINCT c.post_id, p.telegram_message_id, COUNT(c.comment_id) as count
FROM comments c
JOIN posts p ON c.post_id = p.post_id
LEFT JOIN comment_group_drift cgd ON c.post_id = cgd.post_id
WHERE c.telegram_comment_id IS NOT NULL
  AND cgd.post_id IS NULL
GROUP BY c.post_id
HAVING count >= 1
ORDER BY p.telegram_message_id
```

**Update Sync State:**
```python
db.execute(
    """UPDATE sync_state
       SET last_synced_message_id = ?,
           last_synced_at = ?,
           total_posts_synced = total_posts_synced + ?,
           total_comments_synced = total_comments_synced + ?
       WHERE channel_username = ?""",
    (max_message_id, datetime.utcnow(), new_posts_count, new_comments_count, channel_username)
)
```

### Telethon API Calls

**Fetch New Posts (Incremental):**
```python
async for message in client.iter_messages(
    entity=channel,
    min_id=last_synced_message_id,  # Only newer than this
    reverse=True,                    # Chronological order
    limit=None                       # All new messages
):
    # Process message → create Post record
```

**Get Channel Entity:**
```python
channel = await client.get_entity(channel_username)
# Returns: Channel object with id, title, username
```

**Fetch Comments for Post:**
```python
async for reply in client.iter_messages(
    entity=channel,
    reply_to=post_telegram_message_id,
    limit=None
):
    # Process reply → create Comment record
```

### Configuration Schema

**sync_config.yaml Structure:**
```yaml
telegram:
  channel: nobilix              # Channel username (without @)
  sync_depth: 3                 # Check last N posts for new comments

drift_analysis:
  batch_size: 10                # Process N groups at a time
  model: claude-sonnet-4.5      # Model for drift detection

rate_limiting:
  delay_between_posts: 2        # Seconds between API calls
  flood_threshold: 60           # Max seconds to wait for FloodWait

output:
  json_indent: 2                # Pretty print JSON
  show_progress: true           # Progress bars during sync
```

### Exit Codes

```python
EXIT_SUCCESS = 0           # Sync completed successfully
EXIT_PREFLIGHT_FAILED = 1  # Preflight checks failed
EXIT_SYNC_FAILED = 2       # Sync encountered errors
EXIT_DRIFT_FAILED = 3      # Drift analysis failed (but sync succeeded)
```

## User Notes

**Key Requirements:**
1. Посты Рефата: ~1 раз в 3 дня (не чаще)
2. Комментарии: проверять depth=3 последних поста
3. Drift analysis: только для новых comment groups
4. Использовать существующий drift-extraction агент (не переделывать)
5. Todo workflow для прозрачности процесса
6. Dry-run обязателен для безопасности

**Existing Components to Reuse:**
- `SafeTelegramCommentsFetcher` - rate limiting, FloodWait handling
- `drift-extraction` agent - для drift analysis
- `analyze_drift.py` - можно использовать логику определения новых групп

**Design Principles:**
- Idempotent операции (можно перезапускать)
- Structured output (JSON > text parsing)
- Config-driven (не хардкодить параметры)
- Fail-fast с понятными ошибками
- Элегантная интеграция через todo workflow

## Implementation Plan (MVP - 3-4 hours)

### Step 1: Database Migration (30 min)
```sql
-- migrations/002_add_sync_state.sql
CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT UNIQUE NOT NULL,
    last_synced_message_id INTEGER,
    last_synced_at TIMESTAMP
);

INSERT OR IGNORE INTO sync_state (channel_username, last_synced_message_id)
VALUES ('nobilix', (SELECT MAX(telegram_message_id) FROM posts));
```

### Step 2: TelegramChannelSyncer Class (2 hours)
Extend `SafeTelegramCommentsFetcher`:
- `sync_channel_incremental()` - fetch new posts via iter_messages(min_id)
- `update_recent_posts_comments()` - refresh last 3 posts (depth from .env)
- `calculate_new_comment_groups()` - SQL query for groups without drift
- Return JSON: `{new_posts, new_comment_groups, stats}`

### Step 3: CLI Script (1 hour)
Create `backend/sync_channel.py`:
- Load config from .env (NOT yaml)
- 2 базовых preflight checks (session, credentials)
- `--dry-run` режим
- JSON to stdout, простой print summary to stderr

### Step 4: /sync Slash Command (15 min, опционально)
Create `.claude/commands/sync.md` - wrapper для запуска скрипта

## Expected Outcomes (MVP)

**After Implementation:**
- ✅ Синхронизация канала через `python backend/sync_channel.py` (или `/sync`)
- ✅ Incremental sync: только новые посты, depth=3 для комментариев
- ✅ JSON output для интеграции с drift-extraction agent
- ✅ Dry-run режим для безопасного тестирования
- ✅ Todo workflow для прозрачности процесса

**Time Estimate:** 3-4 hours (MVP)

**Dependencies:**
- Existing: `SafeTelegramCommentsFetcher`, `drift-extraction` agent
- New: sync_state table, CLI script, .env config

**NOT in MVP (может быть позже):**
- Pretty output с таблицами (rich library)
- Extensive preflight checks (только базовые 2)
- Exit codes система (только 0/1)
- Automatic scheduling
- Multi-channel support
## Work Log

### 2025-10-08
**Planning & Design**
- Task created with comprehensive architecture design
- Simplified to MVP approach: .env config only, basic preflight checks
- Decided on SYNC_DEPTH as configurable parameter

### 2025-10-09
**Implementation**
- Created database migration 002_add_sync_state.sql for incremental sync tracking
- Implemented TelegramChannelSyncer class extending SafeTelegramCommentsFetcher
- Built sync_channel.py CLI with --dry-run mode and JSON output
- Added /sync slash command for workflow integration
- Updated .env.example with Telegram configuration section

**Bug Fixes**
- Fixed session isolation issues in Telegram client
- Implemented per-comment duplicate handling using IntegrityError exceptions
- Added robust JSON serialization for SSE events with ensure_ascii=False

**Testing & Optimization**
- Initial test with SYNC_DEPTH=3: Found 16 comments across 3 posts
- Increased to SYNC_DEPTH=10: Found 74 comments across 9 posts (4.6x improvement)
- Final setting SYNC_DEPTH=20: Covers ~60 days to catch delayed comments on older posts
- Successfully synced 163 new comments (39 on new posts, 124 on old posts)

**Integration**
- Verified drift-extraction agent integration: 7 new drift topics extracted
- End-to-end workflow tested successfully

**Commits**
- dbb0ee6: Core implementation (migration, syncer, CLI)
- 45a3772: /sync slash command
- c348ed6: Task completion documentation

