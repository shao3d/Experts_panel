# Research Document: Intelligent Telegram Channel Analysis System

## Phase 0 Research Results

### 1. Telegram JSON Export Format
**Decision**: Use machine-readable JSON format from Telegram Desktop export
**Rationale**:
- Contains structured data with text_entities preserving formatting
- Includes internal links as href attributes (t.me/channel/ID format)
- Preserves dates, reactions, and edit history
- Already validated with sample data (154 posts, 77 internal links)
**Alternatives considered**:
- HTML export: More visual but harder to parse reliably
- API scraping: Would require authorization and rate limiting

### 2. LLM Model Selection for Map-Resolve-Reduce
**Decision**: GPT-4o-mini for all three phases
**Rationale**:
- Cost-effective (~$0.02 per full query)
- 128K token context window sufficient for our chunks
- Good balance of quality and speed for Russian content
- Single model simplifies prompt engineering
**Alternatives considered**:
- GPT-4o: Better quality but 30x more expensive
- Claude: Not considered due to user's existing OpenAI setup
- Local models: Too slow for interactive use

### 3. Chunking Strategy
**Decision**: 30 posts per chunk
**Rationale**:
- Optimal for GPT-4o-mini context (up to 128K tokens total)
- Allows 4-5 parallel calls for 100-300 post channels
- Full posts without truncation - GPT-4o-mini can handle it
- Even if some posts are large, 30 posts should fit comfortably
**Alternatives considered**:
- 50 posts: Risk of context overflow
- 10 posts: Too many API calls, higher cost

### 4. Caching Strategy
**Decision**: No caching for MVP - accuracy first
**Rationale**:
- Similarity matching risks false positives (Python vs JavaScript at 87% similarity)
- Each query costs only ~$0.02 with GPT-4o-mini
- Ensures 100% accuracy for validation phase
- Simpler implementation without cache logic
**Future consideration**:
- May implement entity-based caching after analyzing usage patterns
- Exact match caching only if needed
**Alternatives rejected**:
- 85% similarity: Too risky for false matches
- Redis/Memory cache: Unnecessary complexity for MVP

### 5. Database Schema Design
**Decision**: SQLite with three core tables (posts, links, comments)
**Rationale**:
- Foreign keys maintain referential integrity
- Links as first-class entities enable efficient graph traversal
- Single file deployment perfect for Railway
- Good learning opportunity for relational design
**Alternatives considered**:
- PostgreSQL: Unnecessary complexity for MVP
- NoSQL: Poor fit for highly relational data
- JSON files: No query capabilities

### 6. Progress Communication
**Decision**: Server-Sent Events (SSE) for real-time updates
**Rationale**:
- Native browser support, no additional libraries
- Unidirectional flow perfect for progress updates
- Simple to implement with FastAPI
- Allows detailed logging per constitution requirement
**Alternatives considered**:
- WebSockets: Bidirectional unnecessary
- Polling: Poor user experience
- Static loading bar: Violates transparency principle

### 7. Comment Collection Method
**Decision**: Interactive CLI with smart post filtering
**Rationale**:
- User maintains quality control
- System suggests posts likely to have comments
- Copy-paste from Telegram preserves formatting
- Progressive save every 10 posts
**Alternatives considered**:
- Bulk import: No quality control
- Web UI: Unnecessary complexity for one-time task
- Skip comments: Loses valuable context

### 8. Frontend Framework
**Decision**: React 18 with TypeScript, minimal dependencies
**Rationale**:
- User learning objective
- Component model perfect for expandable sources
- TypeScript catches errors early
- No UI library keeps it simple
**Alternatives considered**:
- Vue/Svelte: Less mainstream for portfolio
- Vanilla JS: Too much boilerplate
- Next.js: Overkill for single-page app

### 9. Deployment Strategy
**Decision**: Docker container to Railway
**Rationale**:
- Single Dockerfile for both frontend and backend
- Environment variables for configuration
- Railway's free tier sufficient for MVP
- One-click deploy from GitHub
**Alternatives considered**:
- Vercel + separate backend: More complex
- VPS: Requires maintenance
- Local only: No portfolio value

### 10. Error Handling Strategy
**Decision**: Fail fast with detailed logging
**Rationale**:
- Learning focus - need to see what breaks
- Clear error messages help debugging
- No silent failures per constitution
- Retry only for transient network errors
**Alternatives considered**:
- Extensive retry logic: Hides problems
- Graceful degradation: Complexity not worth it for MVP
- Silent logging: User won't learn

## All Technical Context Questions Resolved
✅ No remaining NEEDS CLARIFICATION items
✅ All dependencies identified and researched
✅ Best practices documented for each technology choice
✅ Ready to proceed to Phase 1 (Design & Contracts)