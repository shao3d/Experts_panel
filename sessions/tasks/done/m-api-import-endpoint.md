---
task: api-import-endpoint
branch: feature/api-import-endpoint
status: completed
created: 2025-09-26
modules:
  - backend
  - api
tags:
  - telegram-map-resolve
  - phase-3.5-api
---

# Create Import Endpoint for JSON Files

## Problem/Goal
Implement POST /api/import endpoint to handle Telegram JSON export file uploads and trigger the parsing and database import process.

## Context Manifest
**Key Files**:
- backend/src/api/query_endpoints.py
- backend/src/api/models.py

**Key Concepts**:
- File upload handling
- Async JSON parsing
- Batch database import
- Progress reporting

## Success Criteria
- [ ] POST /api/import endpoint
- [ ] File upload validation
- [ ] JSON format verification
- [ ] Async processing with background task
- [ ] Progress updates via SSE or polling
- [ ] Error reporting for invalid data
- [ ] Import statistics response
- [ ] Duplicate handling strategy

## Implementation Notes
- Use FastAPI's UploadFile
- Validate file size limits
- Run parser in background task
- Return job ID for status polling
- Handle large files efficiently
- Log import statistics

## Dependencies
- Previous: T014 (JSON parser), T023 (FastAPI main)
- Blocks: Data import functionality
- Can run parallel with: T024-T025, T027-T028 (other endpoints)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T026)
- Priority set to medium (data management endpoint)

### 2025-09-27 - Task Completed
- Implemented POST /api/import endpoint with file upload
- Added async background processing with job tracking
- Created status endpoint for job polling
- Added job history and management endpoints
- File validation (JSON format, 50MB limit)
- Telegram export structure validation
- Integrated with TelegramJsonParser
- Created backend/src/api/import_endpoints.py