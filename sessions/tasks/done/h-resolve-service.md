---
task: resolve-service
branch: feature/resolve-service
status: completed
created: 2025-09-26
modules:
  - backend
  - pipeline
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Resolve Service with 2-Level Depth Control

## Problem/Goal
Implement the Resolve service that enriches relevant posts by following references up to depth 2. This recursively fetches linked posts to provide complete context.

## Context Manifest
**Key Files**:
- backend/src/services/resolve_service.py
- backend/src/services/__init__.py

**Key Concepts**:
- Recursive reference following
- Depth-2 maximum traversal
- Link relationship queries
- Context enrichment

## Success Criteria
- [ ] ResolveService class with async process method
- [ ] Follow links up to depth 2
- [ ] Track visited posts to avoid cycles
- [ ] Fetch linked posts from database
- [ ] Build context trees for each post
- [ ] Handle missing/deleted references
- [ ] Progress tracking for SSE
- [ ] Configurable depth limit

## Implementation Notes
- Use BFS or DFS for traversal
- Maintain visited set to prevent loops
- Batch database queries for efficiency
- Include link type in context
- Limit total posts to prevent explosion
- Return enriched post objects

## Dependencies
- Previous: T011 (Link model), T013 (database schema)
- Blocks: T024 (query endpoint), T035 (service integration)
- Can run parallel with: T016, T018-T022 (other pipeline services)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T017)
- Priority set to high (core pipeline component)

### 2025-09-27 - Task Completed
- Implemented ResolveService class with async architecture
- Database-driven link resolution (NOT text parsing)
- BFS traversal with configurable depth (max 2)
- GPT-4o-mini for link importance evaluation
- Cycle prevention with visited set tracking
- Limited to 10 additional posts to prevent explosion
- Progress callbacks for SSE streaming
- Created backend/src/services/resolve_service.py