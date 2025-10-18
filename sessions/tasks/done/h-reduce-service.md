---
task: reduce-service
branch: feature/reduce-service
status: completed
created: 2025-09-26
modules:
  - backend
  - pipeline
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Reduce Service with Synthesis Logic

## Problem/Goal
Implement the Reduce service that synthesizes all gathered information into a comprehensive answer. This final phase combines insights from Map and Resolve phases.

## Context Manifest
**Key Files**:
- backend/src/services/reduce_service.py
- backend/src/services/__init__.py

**Key Concepts**:
- Answer synthesis from multiple sources
- GPT-4o-mini for comprehensive response
- Source attribution
- Context integration

## Success Criteria
- [ ] ReduceService class with async process method
- [ ] Combine Map and Resolve outputs
- [ ] Generate comprehensive answer via LLM
- [ ] Include source post references
- [ ] Format answer in markdown
- [ ] Track token usage
- [ ] Handle large context gracefully
- [ ] Progress tracking for SSE

## Implementation Notes
- Prioritize most relevant content
- Include post IDs for source tracking
- Structure prompt for comprehensive answers
- Handle token limits intelligently
- Preserve important context
- Return structured response object

## Dependencies
- Previous: T016 (Map service), T017 (Resolve service)
- Blocks: T024 (query endpoint), T035 (service integration)
- Can run parallel with: T019-T022 (logging and prompts)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T018)
- Priority set to high (core pipeline component)

### 2025-09-27 - Task Completed
- Implemented ReduceService class with async architecture
- GPT-4o-mini integration for answer synthesis
- Source attribution with [post:ID] notation
- Expert comments integration from database
- Token usage tracking for cost control
- Context limited to 50 posts maximum
- Progress callbacks for SSE streaming
- Confidence levels (HIGH/MEDIUM/LOW) and language detection
- Created backend/src/services/reduce_service.py