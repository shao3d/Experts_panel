---
task: model-comment
branch: feature/model-comment
status: completed
created: 2025-09-26
modules:
  - backend
  - database
tags:
  - telegram-map-resolve
  - phase-3.3-data-layer
---

# Create Comment Model

## Problem/Goal
Implement the Comment model with post relationship to store expert annotations and contextual notes for posts. Supports the interactive comment collection system.

## Context Manifest
**Key Files**:
- backend/src/models/comment.py
- backend/src/models/__init__.py

**Key Concepts**:
- Expert annotations storage
- Many-to-one relationship with Post
- Author tracking for comments
- Timestamp for comment history

## Success Criteria
- [ ] Comment model with primary key
- [ ] Foreign key to Post model (post_id)
- [ ] Comment text field
- [ ] Author/expert name field
- [ ] Created_at timestamp
- [ ] Updated_at timestamp
- [ ] Relationship to Post configured
- [ ] Index on post_id for queries

## Implementation Notes
- Allow multiple comments per post
- Consider comment categories/tags
- Track who added each comment
- Support markdown in comment text
- Consider soft delete for audit trail

## Dependencies
- Previous: T002 (Python backend init)
- Blocks: T013 (database schema), T015 (comment collector)
- Can run parallel with: T010 (Post model), T011 (Link model), T014 (JSON parser), T015 (comment collector)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T012)
- Priority set to medium (data layer implementation)