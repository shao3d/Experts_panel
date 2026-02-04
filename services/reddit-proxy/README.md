# Reddit MCP Proxy Service

Sidecar microservice for Experts Panel providing resilient Reddit search capabilities via MCP (Model Context Protocol).

## Architecture

```
┌─────────────────┐      HTTP POST       ┌─────────────────┐      MCP Stdio      ┌─────────────┐
│  Main Backend   │ ───────────────────► │  Reddit Proxy   │ ───────────────────►│ reddit-buddy│
│   (Python)      │                      │    (Node.js)    │                     │   (MCP)     │
└─────────────────┘◄─────────────────────└─────────────────┘◄────────────────────└─────────────┘
                          JSON Response                        JSON-RPC
```

## Features

- 🔒 **Watchdog Pattern**: Persistent MCP process with automatic respawn on timeout
- 🛡️ **Resilience**: 15s timeout + SIGKILL + immediate respawn prevents zombie states
- 🧹 **Sanitization**: Removes Zalgo text and normalizes whitespace
- ⚡ **Caching**: LRU cache with 5-minute TTL
- 📊 **Smart Aggregation**: Search x2 → Filter → Fetch → Sanitize pipeline
- 🏥 **Health Checks**: `/health` endpoint for monitoring

## Quick Start

```bash
# Install dependencies
npm install

# Copy environment config
cp .env.example .env
# Edit .env and set your Reddit username in REDDIT_USER_AGENT

# Run in development mode
npm run dev

# Or build and run
npm run build
npm start
```

## API

### POST /search

Search Reddit for discussions.

**Request:**
```json
{
  "query": "best mechanical keyboard",
  "limit": 10,
  "subreddits": ["MechanicalKeyboards", "keyboards"],
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

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "mcpReady": true,
  "uptime": 3600,
  "timestamp": "2026-02-04T12:00:00Z"
}
```

## Deployment

### Fly.io

```bash
# Deploy to Fly.io
fly deploy

# Set secrets
fly secrets set REDDIT_USER_AGENT="android:com.experts.panel:v1.0 (by /u/YOUR_USERNAME)"
```

### Local Docker

```bash
docker build -t reddit-proxy .
docker run -p 3000:3000 -e REDDIT_USER_AGENT="..." reddit-proxy
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3000` | Server port |
| `MCP_TIMEOUT_MS` | `15000` | MCP call timeout (ms) |
| `REDDIT_USER_AGENT` | Required | Reddit API user agent |
| `CACHE_TTL_MS` | `300000` | Cache TTL (ms) |
| `LOG_LEVEL` | `info` | Log level (debug/info/warn/error) |

## Smart Aggregation Pipeline

1. **Search x2**: Search Reddit with query + optional subreddit filters
2. **Filter**: Remove low-quality posts (score < 5), sort by engagement
3. **Fetch**: Enrich with full content (future enhancement)
4. **Sanitize**: Remove Zalgo text, normalize whitespace, escape markdown

## Watchdog Behavior

- Spawns `reddit-buddy` MCP server as persistent process
- Queue concurrency: 1 (sequential processing)
- On 15s timeout: SIGKILL process → immediate respawn
- Max restarts: 10 (then throws error)

## License

MIT
