# Quickstart Guide: Experts Panel

## Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key
- Telegram Desktop (for channel export)

## 1. Export Your Telegram Channel

1. Open Telegram Desktop
2. Navigate to your target channel
3. Click three dots menu → Export Chat History
4. Select:
   - Format: **JSON (machine-readable)**
   - Media: **Unchecked** (text only)
   - Date range: As needed
5. Save the `result.json` file

## 2. Set Up the Application

```bash
# Clone repository
git clone https://github.com/yourusername/experts-panel.git
cd experts-panel

# Set up backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up frontend
cd ../frontend
npm install

# Configure environment
cd ..
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## 3. Import Channel Data

```bash
cd backend
python -m src.data.json_parser /path/to/your/result.json

# Output:
# ✅ Imported 154 posts
# ✅ Found 77 internal links
# ✅ Database created: data/experts.db
```

## 4. Add Comments (Interactive)

```bash
python -m src.data.comment_collector

# The system will show posts likely to have comments:
#
# 📝 Post 7 (2025-03-14): "Про пет проекты и vibe coding..."
# Has 20 reactions - likely has discussion
# Add comments? (y/n/skip): y
#
# Paste comments from Telegram, type END when done:
# [Paste comments here]
# END
#
# ✅ Added 5 comments to post 7
```

## 5. Start the Application

```bash
# Terminal 1: Start backend
cd backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser

## 6. Test the System

### Example Query 1: Topic Search
```
Question: "What does the author think about OSINT and AI?"

Expected behavior:
- MAP: Finds posts 44 and 47 mentioning OSINT
- RESOLVE: Discovers post 47 links to 44, adds both
- REDUCE: Synthesizes comprehensive answer
- Time: ~2-3 minutes
```

### Example Query 2: Follow References
```
Question: "Tell me about getting resources for startups"

Expected behavior:
- MAP: Finds posts 22 and 43 about startup resources
- RESOLVE: Discovers they form a series, includes both
- REDUCE: Presents complete guide from both parts
```

## 7. Understanding the Process Log

The interface shows real-time progress:

```
🔍 Analyzing your question...

📊 MAP phase (parallel search):
  ✓ Chunk 1-30: found 2 relevant posts (#7, #12)
  ✓ Chunk 31-60: found 1 post (#44)
  ✓ Chunk 61-90: found 3 posts (#67, #71, #89)
  ✓ Chunk 91-120: no relevant posts

🔗 RESOLVE phase (enrichment):
  → Post #44 links to #47 - adding
  ← Post #7 is referenced by #9 - adding
  Depth 2: No new links found

✨ REDUCE phase (synthesis):
  Generating comprehensive answer...

[Answer appears here with expandable sources]
```

## 8. Exploring Results

Click on any source to expand:
1. **Level 1**: Summary answer
2. **Level 2**: Click "Sources (6 posts)" to see list
3. **Level 3**: Click any post to see full text
4. **Level 4**: Click "Show comments" if available
5. **Level 5**: View individual comments

## 9. Deploy to Production

```bash
# Build Docker image
docker build -t experts-panel .

# Test locally
docker run -p 8000:8000 --env-file .env experts-panel

# Deploy to Railway
railway up
# Set OPENAI_API_KEY in Railway dashboard
```

## Troubleshooting

### "No posts found"
- Check your query is relevant to channel content
- Try broader search terms
- Verify data import was successful

### "Rate limit exceeded"
- OpenAI API limits reached
- Wait a few minutes
- Check API usage dashboard

## Validation Checklist

- [ ] Can import JSON export successfully
- [ ] Interactive comment addition works
- [ ] Map phase finds relevant posts
- [ ] Resolve phase follows links correctly
- [ ] Reduce phase generates coherent answers
- [ ] Sources are expandable and accurate
- [ ] Progress log shows all phases clearly

## Next Steps

1. Prepare 5-10 test queries with expected answers
2. Document accuracy metrics
3. Optimize prompts in `prompts/` directory
4. Adjust chunk size if needed (default: 30)