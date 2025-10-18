<!-- Sync Impact Report
Version change: 2.0.0 → 2.1.0
Modified principles:
  - Added Principle VII: Smart Caching Strategy
Added sections:
  - Deployment and Portfolio Requirements
Removed sections: None
Templates requiring updates:
  - ✅ All templates remain compatible
Follow-up TODOs: None
-->

# Experts Panel Constitution

## Core Principles

### I. Map-Resolve-Reduce Architecture First
Every analysis feature MUST follow the Map-Resolve-Reduce pattern for processing linked content. Traditional RAG approaches are explicitly avoided. The system MUST maintain full context through recursive enrichment of related posts and preserve all cross-references. This ensures comprehensive analysis of interconnected Telegram content rather than isolated document retrieval.

### II. Source Transparency
Every synthesized answer MUST provide complete source traceability. Users MUST be able to expand any answer to see the exact posts used. Each post reference MUST be expandable to show full content and comments. No information may be presented without clear attribution to its source material.

### III. Validation-First Development
Every feature MUST have clear validation criteria before implementation. For MVP, this means preparing test questions with known answers and defining what "complete" means (finding all relevant posts). Formal unit tests are optional for MVP. Integration testing happens through prepared test queries. The focus is on validating that Map-Resolve-Reduce produces correct and complete results.

### IV. Learning-Oriented MVP
The MVP serves dual purpose: proving Map-Resolve-Reduce works AND teaching core concepts (SQLite, async processing, LLM orchestration). Semi-manual processes are intentionally retained for transparency. Speed is explicitly sacrificed for completeness and understanding. Every architectural decision MUST be observable and debuggable. This is a learning laboratory, not a production system.

### V. Data Integrity and Relationships
The system MUST preserve all relationships between posts, including direct links, replies, and forwards. Cross-references MUST be stored as first-class entities in SQLite. Comments MUST be associated with their parent posts through foreign keys. The recursive enrichment depth defaults to 2 for small channels (under 300 posts) and is configurable.

### VI. Process Transparency
Every phase of Map-Resolve-Reduce MUST be observable. Server logs MUST show which posts were found, why they were selected, and how they were linked. The web interface MUST allow drilling down from answer → sources → full posts → comments. No "black box" operations. Users MUST understand HOW the system reached its conclusions.

### VII. No Caching for MVP (Accuracy First)
For MVP, the system MUST NOT use similarity-based caching to ensure 100% accuracy. Each query MUST be processed fresh through all phases to avoid false matches. This ensures we validate the Map-Resolve-Reduce architecture without cache-induced errors. Future versions may implement entity-based caching after analyzing usage patterns. The small cost increase (~$0.02 per query) is acceptable for ensuring quality.

## Technical Constraints

### Technology Stack
- Backend MUST use Python 3.11+ with FastAPI and Pydantic v2
- Frontend MUST use React 18 with TypeScript (minimal, no fancy UI libraries)
- Database MUST use SQLite with proper schema and foreign keys (learning opportunity)
- LLM: GPT-4o-mini для ВСЕХ фаз (Map, Resolve, Reduce) - бюджетная оптимизация
- All async operations MUST use asyncio
- Configuration MUST be in simple JSON/YAML files (not code)
- Prompts MUST be in separate text files for easy experimentation

### Performance Standards (MVP)
- Query response time: 2-3 minutes acceptable (completeness > speed)
- Initial focus: channels with 100-300 posts
- Chunk size: 30 posts (optimal for GPT-4o-mini context)
- Resolve depth: 2 levels (captures most relationships)
- Relevance target: Find 100% of relevant posts (precision secondary)
- Link tracking: MUST follow all t.me/channel/ID format links

## Development Workflow

### Quality Gates (Relaxed for MVP)
- Code MUST be readable and well-commented (learning focus)
- Test validation through prepared Q&A sets (not unit tests)
- Core pipeline (Map-Resolve-Reduce) MUST have error handling
- SQLite schema MUST be documented with comments

### Documentation Requirements
- API endpoints MUST have OpenAPI specifications
- Complex algorithms (Map-Resolve-Reduce) MUST have inline documentation
- User-facing features MUST have quickstart guides
- Data models MUST document all relationships

## Data Preparation Workflow

### Semi-Automated Process (Intentional Design)
1. Export Telegram channel to JSON (machine-readable format)
2. Run interactive parser script to load posts into SQLite
3. Interactively add important comments through terminal UI
4. System shows posts likely to have discussions
5. User pastes comments directly from Telegram
6. Script parses and associates comments with posts

This manual process ensures quality and understanding of the data.

## Deployment and Portfolio Requirements

### Production Deployment
- Application MUST be deployable via Docker to Railway
- Configuration through environment variables (never hardcoded)
- Health check endpoint at /health for monitoring
- Graceful handling of rate limits and API failures

### Production Configuration
- No demo mode - single production configuration
- OpenAI API key через environment variables
- Prompts stored in separate files (prompts/*.txt)
- Error handling: fail fast with detailed logging
- No caching in MVP (accuracy over cost optimization)

### Portfolio Presentation
- README MUST include architecture diagrams
- Live demo link prominently displayed
- Sample queries and responses documented
- Performance metrics and cost analysis included
- Clean commit history with meaningful messages

### Development Order (Data-First)
- Start with JSON parser to SQLite database
- Interactive comment addition system
- Map-Resolve-Reduce pipeline with real data
- API endpoints with detailed progress events
- React interface with live log display

## Learning Objectives

### Primary Skills to Develop
- SQLite database design with proper relationships
- Async Python with FastAPI
- LLM prompt engineering and orchestration
- React basics for data visualization
- Understanding token limits and chunking strategies

### Explicitly NOT Learning (Yet)
- Production deployment (Docker, K8s)
- Authentication and security
- Performance optimization
- Automated testing frameworks

## Governance

### Amendment Process
This constitution supersedes all other development practices. Amendments require:
1. Documented rationale for the change
2. Impact analysis on existing codebase
3. Migration plan for affected components
4. Version increment per semantic versioning rules

### Compliance
- All feature plans MUST pass constitution checks before implementation
- Violations MUST be explicitly justified in complexity tracking
- Code reviews MUST verify constitutional compliance
- Use CLAUDE.md or agent-specific files for runtime development guidance

**Version**: 2.1.0 | **Ratified**: 2025-09-26 | **Last Amended**: 2025-09-26