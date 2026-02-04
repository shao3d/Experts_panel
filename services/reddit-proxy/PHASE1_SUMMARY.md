# Phase 1 Summary: Reddit MCP Proxy Service

**Status:** ✅ COMPLETE  
**Date:** 2026-02-04  
**Scope:** Local Prototype (Robust Proxy)

---

## 🎯 What Was Built

A production-ready Node.js microservice that acts as a resilient bridge between the Experts Panel backend and Reddit via MCP (Model Context Protocol).

---

## 📁 Project Structure

```
services/reddit-proxy/
├── src/
│   └── index.ts              # Main application (~600 lines)
├── dist/                     # Compiled JavaScript
│   └── index.js
├── package.json              # Node.js dependencies
├── tsconfig.json             # TypeScript config
├── Dockerfile                # Production container
├── fly.toml                  # Fly.io deployment config
├── .env.example              # Environment template
├── .gitignore               # Git exclusions
├── README.md                # Documentation
└── PHASE1_SUMMARY.md        # This file
```

---

## 🔧 Key Features Implemented

### 1. Watchdog Pattern (Resilience)
- **Persistent Process**: Spawns `reddit-mcp-buddy` once and keeps it alive
- **Queue**: `p-queue` with concurrency 1 (sequential processing)
- **Timeout**: 15s timeout on any MCP call
- **Kill & Respawn**: SIGKILL + immediate respawn on timeout (prevents zombie states)
- **Max Restarts**: 10 restarts limit before giving up

### 2. Smart Aggregation Pipeline
```
Search → Filter → Enrich → Sanitize
```

| Step | Description |
|------|-------------|
| **Search** | Calls `searchReddit` tool via MCP |
| **Filter** | Removes low-quality posts (score < 5), sorts by engagement |
| **Enrich** | Maps Reddit API response to internal format |
| **Sanitize** | Removes Zalgo text, normalizes whitespace |

### 3. API Endpoints

#### `POST /search`
**Request:**
```json
{
  "query": "best mechanical keyboard",
  "limit": 10,
  "subreddits": ["MechanicalKeyboards"],
  "sort": "relevance",
  "time": "month"
}
```

**Response:**
```json
{
  "markdown": "### 1. Best budget mechanical keyboard...",
  "foundCount": 10,
  "sources": [
    {
      "title": "Best budget mechanical keyboard",
      "url": "https://reddit.com/r/MechanicalKeyboards/comments/...",
      "score": 542,
      "commentsCount": 128,
      "subreddit": "MechanicalKeyboards"
    }
  ],
  "query": "best mechanical keyboard",
  "processingTimeMs": 2450
}
```

#### `GET /health`
Health check for monitoring and load balancers.

### 4. Text Sanitization
- **Zalgo Removal**: Strips Unicode combining characters (U+0300–U+036F, etc.)
- **Whitespace Normalization**: Collapses multiple spaces/newlines
- **Markdown Escaping**: Escapes special markdown characters

---

## 🛠️ Technology Stack

| Component | Technology |
|-----------|------------|
| Runtime | Node.js 20 (Alpine) |
| Framework | Fastify 4.x |
| MCP SDK | `@modelcontextprotocol/sdk` v1.x |
| Process Mgmt | `cross-spawn` + custom Watchdog |
| Queue | `p-queue` (concurrency: 1) |
| Cache | `lru-cache` (5 min TTL) |
| Validation | Zod |
| Language | TypeScript 5.x |

---

## 🔌 MCP Integration Details

**MCP Server:** `reddit-mcp-buddy` (npm package)  
**Transport:** stdio (JSON-RPC over stdin/stdout)  
**Tools Used:**
- `searchReddit` - Search posts across Reddit
- (Ready for) `getPostDetails` - Fetch post with comments
- (Ready for) `browseSubreddit` - Browse specific subreddit

**Tool Schema (searchReddit):**
```typescript
{
  query: string;
  subreddits?: string[];
  sort: 'relevance' | 'hot' | 'top' | 'new' | 'comments';
  time: 'hour' | 'day' | 'week' | 'month' | 'year' | 'all';
  limit: number (1-100);
  author?: string;
  flair?: string;
}
```

---

## 🚀 Next Steps (Phase 2 & 3)

### Phase 2: Deployment
```bash
# Build and push Docker image
docker build -t experts-reddit-proxy .

# Deploy to Fly.io
fly deploy

# Set secrets
fly secrets set REDDIT_USER_AGENT="android:com.experts.panel:v1.0 (by /u/YOUR_USERNAME)"
```

### Phase 3: Backend Integration
1. Create `src/services/reddit_service.py` in main backend
2. Update `simplified_query_endpoint.py` with:
   - Parallel Reddit pipeline execution
   - Keep-Alive SSE pings (every 2-3 seconds)
   - Response merging (Expert + Reddit)
3. Add error handling (fail-safe: Reddit failure doesn't break Expert response)

### Phase 4: Frontend
1. Create `<CommunityInsightsSection />` component
2. Display Reddit markdown with source links

---

## 🧪 Testing Locally

```bash
cd services/reddit-proxy

# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env: Set your Reddit username in REDDIT_USER_AGENT

# 3. Build
npm run build

# 4. Run
npm start

# 5. Test health endpoint
curl http://localhost:3000/health

# 6. Test search
curl -X POST http://localhost:3000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "best mechanical keyboard", "limit": 5}'
```

---

## ⚠️ Known Limitations / TODO

1. **MCP Tool Discovery**: Currently hardcoded `searchReddit` tool name. If reddit-mcp-buddy changes tool names, needs update.

2. **Error Handling**: Reddit API errors (rate limit, 404 subreddit) are passed through as generic errors. Could be more specific.

3. **Caching**: Simple LRU cache. No cache invalidation strategy for "fresh" content.

4. **Pagination**: Not implemented. Returns first N results only.

5. **Authentication**: reddit-mcp-buddy supports optional auth (`--auth` flag) for higher rate limits. Not integrated yet.

---

## 📊 Spec Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| Node.js 20-alpine | ✅ | Dockerfile uses `node:20-alpine` |
| Fastify | ✅ | v4.24.0 |
| MCP SDK | ✅ | `@modelcontextprotocol/sdk` v1.x |
| p-queue (concurrency: 1) | ✅ | Sequential processing |
| Timeout & Kill (15s) | ✅ | Watchdog implemented |
| User-Agent enforcement | ✅ | Via env var |
| Zalgo sanitization | ✅ | Full Unicode combining char removal |
| Whitespace normalization | ✅ | Collapses multiple spaces/newlines |
| POST /search endpoint | ✅ | Returns `{markdown, foundCount, sources}` |
| LRU Cache | ✅ | 5 min TTL, 100 entries |
| Health endpoint | ✅ | `/health` with MCP status |
| Dockerfile | ✅ | Multi-stage, non-root user |
| fly.toml | ✅ | Health checks, auto-scaling |

---

## 🎉 Phase 1 Complete!

The Reddit Proxy service is ready for:
1. ✅ Local testing
2. ✅ Docker deployment
3. ✅ Fly.io deployment
4. ⏭️ Backend integration (Phase 3)

**Ready to proceed to Phase 2 (Deployment) and Phase 3 (Backend Integration)!**
