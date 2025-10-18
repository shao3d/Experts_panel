---
task: api-post-endpoint
branch: feature/api-post-endpoint
status: pending
created: 2025-09-26
modules:
  - backend
  - api
tags:
  - telegram-map-resolve
  - phase-3.5-api
---

# Create Post Retrieval Endpoint

## Problem/Goal
Implement GET /api/posts/{postId} endpoint to retrieve individual post details, including comments and links, for the source viewer component.

## Context Manifest
**Key Files**:
- backend/src/api/query_endpoints.py
- backend/src/api/models.py

**Key Concepts**:
- RESTful resource retrieval
- Post detail serialization
- Related data loading
- Response caching

## Success Criteria
- [ ] GET /api/posts/{postId} endpoint
- [ ] Fetch post with comments
- [ ] Include link relationships
- [ ] Proper 404 handling
- [ ] Response model with Pydantic
- [ ] Include metadata fields
- [ ] Efficient query with joins
- [ ] Cache headers for performance

## Implementation Notes
- Use SQLAlchemy eager loading
- Include related comments
- Serialize datetime fields properly
- Handle deleted posts gracefully
- Consider pagination for comments
- Add ETag support for caching

## Dependencies
- Previous: T010-T012 (models), T023 (FastAPI main)
- Blocks: Frontend SourceViewer component
- Can run parallel with: T024, T026-T028 (other endpoints)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T025)
- Priority set to medium (supporting endpoint)