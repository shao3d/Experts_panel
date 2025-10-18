---
task: dockerfile
branch: feature/dockerfile
status: pending
created: 2025-09-26
modules:
  - deployment
  - infrastructure
tags:
  - telegram-map-resolve
  - phase-3.7-integration
---

# Create Dockerfile for Combined Deployment

## Problem/Goal
Create a Dockerfile that builds both frontend and backend into a single deployable container image for production deployment.

## Context Manifest
**Key Files**:
- Dockerfile
- .dockerignore

**Key Concepts**:
- Multi-stage Docker build
- Production optimization
- Security best practices
- Size optimization

## Success Criteria
- [ ] Multi-stage Dockerfile created
- [ ] Frontend build stage
- [ ] Backend runtime stage
- [ ] Static files served correctly
- [ ] Environment variables configured
- [ ] Non-root user setup
- [ ] Health check configured
- [ ] Minimal final image size

## Implementation Notes
- Use node:alpine for frontend build
- Use python:slim for backend
- Copy only production dependencies
- Set proper file permissions
- Configure for Railway deployment
- Include .dockerignore file

## Dependencies
- Previous: All implementation tasks
- Blocks: T044 (Railway deployment)
- Can run parallel with: T040 (docker-compose)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T039)
- Priority set to medium (deployment task)