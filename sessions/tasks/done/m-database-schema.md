---
task: database-schema
branch: feature/database-schema
status: completed
created: 2025-09-26
modules:
  - backend
  - database
tags:
  - telegram-map-resolve
  - phase-3.3-data-layer
---

# Create SQLite Database Schema

## Problem/Goal
Create the SQLite database schema with proper indexes and foreign key constraints. Initialize the database connection and session management.

## Context Manifest
**Key Files**:
- backend/src/models/database.py
- backend/schema.sql (optional)
- data/experts.db (database file)

**Key Concepts**:
- SQLite with foreign keys enabled
- Connection pooling for async operations
- Migration strategy
- Index optimization

## Success Criteria
- [ ] Database initialization script created
- [ ] Foreign keys enabled in SQLite
- [ ] All tables created from models
- [ ] Indexes on frequently queried columns
- [ ] Full-text search index on post content
- [ ] Session factory configured
- [ ] Async session support
- [ ] Database URL configuration

## Implementation Notes
- Enable SQLite foreign key support
- Use SQLAlchemy create_all() for schema
- Create composite indexes for common queries
- Consider FTS5 for full-text search
- Set appropriate timeouts and pool size
- Include database initialization function

## Dependencies
- Previous: T010 (Post model), T011 (Link model), T012 (Comment model)
- Blocks: T014 (JSON parser), T015 (comment collector), all services
- Can run parallel with: None (depends on all models)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T013)
- Priority set to medium (data layer implementation)