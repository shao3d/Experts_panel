# Map-Resolve-Reduce Pipeline Prompts

## Overview
These prompts power the three-phase query processing pipeline for analyzing Telegram channel posts.

## Versions

### Current (Optimized for GPT-4o-mini)
- `map_prompt.txt` - Identifies relevant posts from chunks
- `resolve_prompt.txt` - Evaluates importance of linked posts (uses DB links)
- `reduce_prompt.txt` - Synthesizes final comprehensive answer

### Original (v1)
- `*_prompt_v1.txt` - Original complex versions from spec phase

## Key Optimizations

### Map Phase
- Fixed field names: `telegram_id` → `telegram_message_id`
- Simplified scoring: float (0-1) → enum (HIGH/MEDIUM/LOW)
- Removed `key_phrases` array to reduce complexity
- Added author field for context

### Resolve Phase
- **Major change**: Now uses Links from database instead of parsing text
- GPT only evaluates importance, doesn't extract URLs
- Simplified output to just list of IDs
- Works with our LinkType enum (REPLY/FORWARD/MENTION)

### Reduce Phase
- Flattened JSON structure (removed nested objects)
- Removed metadata section
- Added expert comments integration
- Simplified confidence to enum

## Usage with JSON Mode (example)

```python
# Enable JSON strict mode for reliability
response = openai.chat.completions.create(
    model="gpt-4o-mini",  # or any other supported model
    response_format={"type": "json_object", "strict": True},
    messages=[...]
)
```

## Token Optimization
- Chunk size: 20-25 posts (was 30)
- Max context: 128k tokens
- Max output: 16k tokens

## Field Mapping to Models

| Prompt Field | SQLAlchemy Model Field |
|-------------|------------------------|
| telegram_message_id | Post.telegram_message_id |
| content | Post.message_text |
| author | Post.author_name |
| date | Post.created_at |
| link_type | LinkType.REPLY/FORWARD/MENTION |