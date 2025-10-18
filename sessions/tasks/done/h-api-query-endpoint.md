---
task: api-query-endpoint
branch: feature/api-query-endpoint
status: completed
created: 2025-09-26
modules:
  - backend
  - api
tags:
  - telegram-map-resolve
  - phase-3.5-api
---

# Create Query Endpoint with SSE Streaming

## Problem/Goal
Implement the main POST /api/query endpoint that processes user queries through the Map-Resolve-Reduce pipeline with Server-Sent Events for real-time progress updates.

## Context Manifest
**Key Files**:
- backend/src/api/query_endpoints.py
- backend/src/api/models.py (request/response models)

**Key Concepts**:
- Server-Sent Events (SSE)
- Async request processing
- Pipeline orchestration
- Real-time progress streaming

## Success Criteria
- [ ] POST /api/query endpoint implemented
- [ ] SSE streaming for progress updates
- [ ] Request validation with Pydantic
- [ ] Pipeline service orchestration
- [ ] Error handling and recovery
- [ ] Response streaming format
- [ ] Request ID tracking
- [ ] Timeout handling

## Implementation Notes
- Use FastAPI's StreamingResponse
- Send progress events for each phase
- Handle client disconnections gracefully
- Include timing metrics in events
- Stream partial results if possible
- Implement request cancellation

## Dependencies
- Previous: T016-T019 (pipeline services), T023 (FastAPI main)
- Blocks: T036 (SSE implementation details)
- Can run parallel with: T025-T028 (other endpoints)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T024)
- Priority set to high (core API endpoint)

### 2025-09-27 - Task Completed
- Created Pydantic models for request/response validation
- Implemented POST /api/query endpoint
- Full Map-Resolve-Reduce pipeline orchestration
- Server-Sent Events (SSE) for real-time progress updates
- Support for both streaming and synchronous modes
- Request ID tracking for each query
- Token usage and timing metrics
- Created backend/src/api/models.py and backend/src/api/query_endpoints.py