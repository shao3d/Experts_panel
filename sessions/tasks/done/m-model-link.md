---
task: model-link
branch: feature/model-link
status: completed
created: 2025-09-26
modules:
  - backend
  - database
tags:
  - telegram-map-resolve
  - phase-3.3-data-layer
---

# Create Link Model

## Problem/Goal
Implement the Link model with foreign key constraints to represent relationships between posts (replies, forwards, mentions). Critical for the Resolve phase's reference following.

## Context Manifest
**Key Files**:
- backend/src/models/link.py
- backend/src/models/__init__.py

**Key Concepts**:
- Post-to-post relationships
- Foreign key constraints
- Link types (reply, forward, mention)
- Bidirectional traversal

## Success Criteria
- [ ] Link model with source_post_id and target_post_id
- [ ] Foreign keys to Post model configured
- [ ] Link type enumeration (reply/forward/mention)
- [ ] Created_at timestamp field
- [ ] Cascade delete rules configured
- [ ] Indexes on both foreign keys
- [ ] Unique constraint on source-target-type combination

## Implementation Notes
- Use SQLAlchemy relationship() for navigation
- Consider self-referential relationship on Post
- Enum for link types for type safety
- Index both directions for efficient queries
- Handle deleted/missing posts gracefully

## Dependencies
- Previous: T002 (Python backend init)
- Blocks: T013 (database schema), T017 (Resolve service)
- Can run parallel with: T010 (Post model), T012 (Comment model), T014 (JSON parser), T015 (comment collector)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T011)
- Priority set to medium (data layer implementation)