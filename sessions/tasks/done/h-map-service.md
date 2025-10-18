---
task: map-service
branch: feature/map-service
status: completed
created: 2025-09-26
modules:
  - backend
  - pipeline
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Map Service with 30-Post Chunking

## Problem/Goal
Implement the Map service that processes posts in parallel chunks of 30, sending each chunk to GPT-4o-mini for initial relevance assessment. This is the first phase of the Map-Resolve-Reduce pipeline.

## Context Manifest
**Key Files**:
- backend/src/services/map_service.py
- backend/src/services/__init__.py

**Key Concepts**:
- Parallel processing of post chunks
- 30-post chunk size (optimized for GPT-4o-mini)
- Relevance scoring
- Async OpenAI API calls

## Success Criteria
- [ ] MapService class with async process method
- [ ] Chunk posts into groups of 30
- [ ] Parallel processing with asyncio
- [ ] OpenAI API integration
- [ ] Relevance scoring for each post
- [ ] Progress tracking via callbacks
- [ ] Error handling for API failures
- [ ] Configurable chunk size

## Implementation Notes
- Use asyncio.gather() for parallel execution
- Implement retry logic for API failures
- Stream progress updates for SSE
- Return scored posts sorted by relevance
- Consider rate limiting for API calls
- Cache chunk results during processing

## Dependencies
- Previous: T010-T013 (data models and schema)
- Blocks: T024 (query endpoint), T035 (service integration)
- Can run parallel with: T017-T022 (other pipeline services)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T016)
- Priority set to high (core pipeline component)

### 2025-09-27 - Task Completed
- Implemented MapService class with async architecture
- Added 30-post chunking with configurable size
- Implemented parallel processing with asyncio and semaphore for concurrency control
- Integrated GPT-4o-mini with JSON response format
- Added retry logic using tenacity (3 attempts with exponential backoff)
- Implemented progress callbacks for SSE streaming support
- Results sorted by relevance (HIGH → MEDIUM → LOW)
- Created backend/src/services/map_service.py