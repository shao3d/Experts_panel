# Data Model: Intelligent Telegram Channel Analysis System

## Entity Definitions

### Post
Represents a single Telegram channel message.

**Fields**:
- `id`: Integer, Primary Key, Auto-increment
- `telegram_message_id`: Integer, Unique, Not Null - Original post ID from Telegram
- `content`: Text, Not Null - Full text content of the post
- `content_plain`: Text - Plain text without formatting for search
- `date`: Timestamp, Not Null - When post was published
- `edited_date`: Timestamp, Nullable - Last edit timestamp if edited
- `reactions_count`: Integer, Default 0 - Total sum of all reactions
- `has_comments`: Boolean, Default False - Flag indicating comments exist

**Relationships**:
- Has many Comments (one-to-many)
- Has many outgoing Links (one-to-many, from_post)
- Has many incoming Links (one-to-many, to_post)

**Validation Rules**:
- `telegram_message_id` must be positive integer
- `content` no maximum length limit (store full post)
- `date` cannot be in the future
- `reactions_count` >= 0

**State Transitions**: None (posts are immutable after import)

### Link
Represents a connection between posts or to external resources.

**Fields**:
- `id`: Integer, Primary Key, Auto-increment
- `from_post_id`: Integer, Not Null, Foreign Key → Post.id
- `to_post_id`: Integer, Nullable, Foreign Key → Post.id (null for external)
- `url`: Text - Full URL of the link
- `link_type`: Text, Default 'internal_link' - Type of connection
- `anchor_text`: Text - Visible text of the link

**Relationships**:
- Belongs to Post (many-to-one, from_post)
- Optionally belongs to Post (many-to-one, to_post)

**Validation Rules**:
- `from_post_id` must exist in posts table
- `to_post_id` must exist in posts table if not null
- `url` must be valid URL format
- `link_type` in ['internal_link', 'external_link']
- Cannot have `from_post_id` equal to `to_post_id` (no self-links)

**State Transitions**: None (links are immutable after import)

### Comment
Represents user-added annotation to a post.

**Fields**:
- `id`: Integer, Primary Key, Auto-increment
- `post_id`: Integer, Not Null, Foreign Key → Post.id
- `author`: Text, Nullable - Comment author name
- `content`: Text, Not Null - Comment text
- `date`: Timestamp, Nullable - When comment was made

**Relationships**:
- Belongs to Post (many-to-one)

**Validation Rules**:
- `post_id` must exist in posts table
- `content` length between 1 and 10000 characters
- `date` cannot be before parent post's date

**State Transitions**: None (comments added once during import)

### Query (Runtime Entity - Not Persisted)
Represents a user's question to the system.

**Fields**:
- `id`: UUID - Unique identifier for the query session
- `question`: Text - Natural language question from user
- `timestamp`: Timestamp - When query was submitted

**Relationships**:
- Produces one Answer

**Validation Rules**:
- `question` length between 1 and 1000 characters
- `question` cannot be empty or whitespace only

### Answer (Runtime Entity - Not Persisted)
Represents system's response to a query.

**Fields**:
- `id`: UUID - Unique identifier
- `query_id`: UUID - Reference to originating query
- `content`: Text - Synthesized answer text
- `source_post_ids`: Array[Integer] - IDs of posts used
- `processing_time_ms`: Integer - Time taken to generate
- `phase_details`: JSON - Detailed log of each phase

**Relationships**:
- Belongs to Query (one-to-one)
- References many Posts (via source_post_ids)

**Validation Rules**:
- `content` must not be empty
- `source_post_ids` must contain at least one valid post ID
- `processing_time_ms` > 0

## Database Schema (SQLite)

```sql
-- Posts table
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER UNIQUE NOT NULL,
    content TEXT NOT NULL,
    content_plain TEXT,
    date TIMESTAMP NOT NULL,
    edited_date TIMESTAMP,
    reactions_count INTEGER DEFAULT 0,
    has_comments BOOLEAN DEFAULT FALSE,
    CHECK (telegram_message_id > 0),
    CHECK (length(content) >= 1),
    CHECK (reactions_count >= 0)
);

-- Links table
CREATE TABLE links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_post_id INTEGER NOT NULL,
    to_post_id INTEGER,
    url TEXT,
    link_type TEXT DEFAULT 'internal_link',
    anchor_text TEXT,
    FOREIGN KEY (from_post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (to_post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CHECK (from_post_id != to_post_id),
    CHECK (link_type IN ('internal_link', 'external_link'))
);

-- Comments table
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    author TEXT,
    content TEXT NOT NULL,
    date TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CHECK (length(content) BETWEEN 1 AND 10000)
);

-- Indexes for performance
CREATE INDEX idx_posts_date ON posts(date);
CREATE INDEX idx_posts_telegram_message_id ON posts(telegram_message_id);
CREATE INDEX idx_links_from ON links(from_post_id);
CREATE INDEX idx_links_to ON links(to_post_id);
CREATE INDEX idx_comments_post ON comments(post_id);
```

## Data Flow

1. **Import Phase**:
   - JSON → Posts table (with telegram_message_id mapping)
   - Extract links → Links table (with post resolution)
   - Interactive comments → Comments table

2. **Query Phase**:
   - Query → Map (chunks of posts)
   - Map results → Resolve (follow links)
   - Resolved posts → Reduce (synthesize)
   - Final posts → Answer with source IDs

## Relationships Diagram

```
Post (1) ←────────────→ (*) Comment
  │                           │
  │ from_post                 │ post_id
  ↓                           ↓
Link (*) ←──────────────────→ (1) Post
  │
  │ to_post (nullable)
  ↓
Post (0..1)
```