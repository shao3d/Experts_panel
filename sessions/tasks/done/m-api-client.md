---
task: api-client
branch: feature/api-client
status: pending
created: 2025-09-26
modules:
  - frontend
  - services
tags:
  - telegram-map-resolve
  - phase-3.6-frontend
---

# Create API Client Service

## Problem/Goal
Build a TypeScript API client service with type definitions for all backend endpoints, handling requests and responses with proper error handling.

## Context Manifest
**Key Files**:
- frontend/src/services/api.ts
- frontend/src/services/types.ts

**Key Concepts**:
- TypeScript API client
- Type-safe requests
- Error handling
- SSE support

## Success Criteria
- [ ] api.ts service created
- [ ] TypeScript interfaces for all endpoints
- [ ] Query submission method
- [ ] Post fetching method
- [ ] SSE stream handling
- [ ] Error response types
- [ ] Request interceptors
- [ ] Response transformers

## Implementation Notes
- Use fetch API or axios
- Generate types from OpenAPI
- Handle network errors
- Implement retry logic
- Support request cancellation
- Configure base URL

## Dependencies
- Previous: T003 (React frontend init), T005 (TypeScript config)
- Blocks: T033 (MainPage integration)
- Can run parallel with: T029-T032 (components)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T034)
- Priority set to medium (frontend service)