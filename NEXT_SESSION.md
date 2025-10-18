# Next Session: Drift Analysis Quality Review (Posts #88-134)

## Task Status
**Current task:** `i-implement-drift-analysis`
**Branch:** `feature/simplified-architecture`
**Progress:** 87/134 posts reviewed (64.9%)
**Remaining:** 47 posts (#88-134)

## What to Do Next

Continue systematic quality review of drift analysis from **post #88**.

### Process (one post at a time):
1. Read full post text
2. Read ALL comments
3. Check current drift in database
4. Apply quality criteria (below)
5. Fix/remove/add drift as needed
6. Update TodoWrite and move to next post

### Quality Criteria (STRICT!)

**✅ DRIFT = Concrete tools/products/platforms NOT in post**
- Examples: qdrant, vLLM, Proxycurl, ScrapeNinja, Aqua Voice
- Specific models: t-lite FP16, whisperX, Sesame CSM 1B
- Tool combinations: Windsurf + Obsidian

**❌ NOT DRIFT:**
- Methodologies: "chunk overlap", "reward tuning", "sliding window"
- Generic categories: "NLP", "ML", "STT", "TTS"
- Framework comparisons: "browser-use vs langchain"
- Tools from original post: check keywords are NOT in post!

### Common Error Patterns (watch for!)

1. **Tools from post in drift keywords**
   - Always verify keywords are NOT mentioned in post
   - Recent examples: Dify, Spider, Chunkr, ElevenLabs, ScrapeGraphAI

2. **Generic terms instead of concrete tools**
   - Replace "NLP", "ML" with actual tools
   - Replace "chunk overlap" with qdrant, vLLM, etc.

3. **Missing concrete alternatives**
   - Check comments carefully for product names
   - Look for GitHub links, service names

### Keywords Structure

Each drift_topics entry must have:
```json
{
  "topic": "Descriptive phrase about WHAT drift discusses",
  "keywords": ["Concrete", "Tool", "Names", "Only"],
  "key_phrases": ["Direct quotes from comments"],
  "context": "Why this is drift - what new info discussed"
}
```

### Commands

```bash
# Check drift for post #88
sqlite3 data/experts.db "SELECT has_drift, drift_topics FROM comment_group_drift WHERE post_id = (SELECT post_id FROM posts WHERE telegram_message_id = 88)"

# Get post and comments
sqlite3 data/experts.db "SELECT message_text FROM posts WHERE telegram_message_id = 88"
sqlite3 data/experts.db "SELECT comment_text FROM comments WHERE parent_telegram_message_id = 88 ORDER BY comment_id"
```

### Todo List Template

Create todo list for posts #88-97 (next 10):
- Review drift analysis for post #88
- Review drift analysis for post #89
- ... (etc)

## Session Stats Target

- Review rate: ~10 posts per focused session
- Error rate: ~51% need fixes (based on previous sessions)
- Estimated time: 2-3 hours for remaining 47 posts

## Success Metrics

When all 134 posts reviewed:
- All keywords are concrete tools/products
- No tools from posts in drift keywords
- No methodologies or generic terms
- All drift provides value to 4o-mini matching

---

**Remember:** Work systematically, one post at a time. Quality > speed!
