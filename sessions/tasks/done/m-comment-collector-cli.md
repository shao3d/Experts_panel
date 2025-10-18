---
task: comment-collector-cli
branch: feature/comment-collector-cli
status: completed
created: 2025-09-26
modules:
  - backend
  - cli
tags:
  - telegram-map-resolve
  - phase-3.3-data-layer
---

# Create Interactive Comment Collector CLI

## Problem/Goal
Build an interactive command-line interface for experts to add contextual comments to posts. This helps enrich the dataset with domain knowledge.

## Context Manifest
**Key Files**:
- backend/src/data/comment_collector.py
- backend/src/data/__init__.py

**Key Concepts**:
- Interactive CLI prompts
- Post display and navigation
- Comment input and validation
- Batch comment sessions

## Success Criteria
- [ ] Interactive CLI with clear prompts
- [ ] Display post content for review
- [ ] Accept comment input with validation
- [ ] Navigate between posts (next/previous/skip)
- [ ] Save comments to database
- [ ] Session management (resume/pause)
- [ ] Search posts by keyword/ID
- [ ] Export comments for review

## Implementation Notes
- Use rich or click for better CLI UX
- Show post context (previous/next posts)
- Support markdown in comments
- Allow editing existing comments
- Track comment author/session
- Provide statistics on progress

## Dependencies
- Previous: T012 (Comment model), T013 (database schema)
- Blocks: Comment data collection
- Can run parallel with: T010-T011 (models), T014 (JSON parser)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T015)
- Priority set to medium (data layer implementation)

### 2025-09-27 - Task Completed
- Created interactive CLI with Rich library UI
- Implemented chronological browsing and keyword search
- Added multi-line comment input with markdown support
- Expert name tracking for personalized comments
- Review and statistics features
- JSON export functionality
- Created backend/src/data/comment_collector.py