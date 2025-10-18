---
task: services-model-connect
branch: feature/services-model-connect
status: pending
created: 2025-09-26
modules:
  - backend
  - integration
tags:
  - telegram-map-resolve
  - phase-3.7-integration
---

# Connect Services to SQLAlchemy Models

## Problem/Goal
Integrate all pipeline services with SQLAlchemy models, ensuring proper database queries, transactions, and data flow throughout the system.

## Context Manifest
**Key Files**:
- backend/src/services/*.py (all services)
- backend/src/models/*.py (all models)

**Key Concepts**:
- Service-model integration
- Database session management
- Query optimization
- Transaction handling

## Success Criteria
- [ ] Map service queries posts efficiently
- [ ] Resolve service fetches links properly
- [ ] Services use async sessions
- [ ] Proper transaction boundaries
- [ ] Optimized queries with joins
- [ ] Connection pooling configured
- [ ] Error handling for DB issues
- [ ] Session cleanup

## Implementation Notes
- Use async SQLAlchemy sessions
- Implement unit of work pattern
- Batch queries where possible
- Use eager loading for relationships
- Handle connection timeouts
- Implement query logging

## Dependencies
- Previous: T010-T013 (models), T016-T019 (services)
- Blocks: End-to-end functionality
- Can run parallel with: T036-T040 (other integration tasks)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T035)
- Priority set to medium (integration task)