---
task: component-source-viewer
branch: feature/component-source-viewer
status: pending
created: 2025-09-26
modules:
  - frontend
  - components
tags:
  - telegram-map-resolve
  - phase-3.6-frontend
---

# Create SourceViewer Component

## Problem/Goal
Build the SourceViewer React component that displays the source posts referenced in the answer, with expandable details and navigation.

## Context Manifest
**Key Files**:
- frontend/src/components/SourceViewer.tsx
- frontend/src/components/SourceViewer.css

**Key Concepts**:
- Source post display
- Expandable post details
- Post navigation
- Comment visibility

## Success Criteria
- [ ] SourceViewer.tsx component created
- [ ] List of referenced posts
- [ ] Expandable post content
- [ ] Show post metadata
- [ ] Display expert comments
- [ ] Link relationships visible
- [ ] Pagination for many sources
- [ ] TypeScript props interface

## Implementation Notes
- Fetch post details on demand
- Lazy load for performance
- Group by relevance score
- Show timestamps
- Highlight search terms
- Mobile-responsive accordion

## Dependencies
- Previous: T003 (React frontend init), T005 (TypeScript config)
- Blocks: T033 (MainPage integration)
- Can run parallel with: T029-T031, T034 (other components)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T032)
- Priority set to high (core UI component)