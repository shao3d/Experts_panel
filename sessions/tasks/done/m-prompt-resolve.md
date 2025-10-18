---
task: prompt-resolve
branch: feature/prompt-resolve
status: completed
created: 2025-09-26
modules:
  - prompts
  - backend
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Resolve Prompt Template

## Problem/Goal
Create the prompt template for the Resolve phase that instructs GPT-4o-mini to assess the importance of linked posts and determine which connections provide valuable context.

## Context Manifest
**Key Files**:
- backend/prompts/resolve_prompt.txt
- backend/prompts/README.md

**Key Concepts**:
- Link relevance assessment
- Context enrichment instructions
- Reference importance scoring
- Depth traversal explanation

## Success Criteria
- [ ] resolve_prompt.txt template created
- [ ] Instructions for link evaluation
- [ ] Context importance criteria
- [ ] Handling of different link types
- [ ] Output format specification
- [ ] Depth level awareness
- [ ] Circular reference handling
- [ ] Version tracking comment

## Implementation Notes
- Explain the concept of depth-2 traversal
- Prioritize direct replies and forwards
- Consider temporal relationships
- Include link type in assessment
- Balance completeness vs relevance
- Keep token usage efficient

## Dependencies
- Previous: T001 (project structure)
- Blocks: T017 (Resolve service implementation)
- Can run parallel with: T016-T020, T022 (services and other prompts)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T021)
- Priority set to medium (prompt template)