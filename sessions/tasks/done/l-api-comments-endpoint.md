---
task: api-comments-endpoint
branch: feature/api-comments-endpoint
status: pending
created: 2025-09-26
modules:
  - backend
  - api
tags:
  - telegram-map-resolve
  - phase-3.5-api
---

# Create Comments Collection Endpoint

## Problem/Goal
Implement POST /api/comments/collect endpoint to support the interactive comment collection workflow through the web interface.

## Context Manifest
**Key Files**:
- backend/src/api/query_endpoints.py
- backend/src/api/models.py

**Key Concepts**:
- Comment submission API
- Post navigation for commenting
- Session management
- Expert identification

## Success Criteria
- [ ] POST /api/comments/collect endpoint
- [ ] Add comment to specific post
- [ ] Update existing comments
- [ ] Expert/author tracking
- [ ] Session-based workflow
- [ ] Get next post for review
- [ ] Comment validation
- [ ] Batch comment submission

## Implementation Notes
- Support both single and batch operations
- Track comment author/session
- Allow markdown in comments
- Implement comment versioning
- Return next post for workflow
- Consider rate limiting

## Dependencies
- Previous: T012 (Comment model), T023 (FastAPI main)
- Blocks: Web-based comment collection
- Can run parallel with: T024-T026, T028 (other endpoints)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T027)
- Priority set to low (auxiliary feature)