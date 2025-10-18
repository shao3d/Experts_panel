---
task: prompt-map
branch: feature/prompt-map
status: completed
created: 2025-09-26
modules:
  - prompts
  - backend
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Map Prompt Template

## Problem/Goal
Create the prompt template for the Map phase that instructs GPT-4o-mini to identify relevant posts from chunks of 30 posts based on the user's query.

## Context Manifest
**Key Files**:
- backend/prompts/map_prompt.txt
- backend/prompts/README.md

**Key Concepts**:
- LLM prompt engineering
- Relevance scoring instructions
- Structured output format
- Chunk processing context

## Success Criteria
- [ ] map_prompt.txt template created
- [ ] Clear instructions for relevance assessment
- [ ] Structured output format defined
- [ ] Scoring criteria explained
- [ ] Example input/output included
- [ ] Handles various query types
- [ ] Optimized for GPT-4o-mini
- [ ] Version tracking comment

## Implementation Notes
- Use placeholders for dynamic content
- Request JSON or structured output
- Include relevance scoring (0-10)
- Explain context of chunking
- Keep concise for token efficiency
- Test with various query types

## Dependencies
- Previous: T001 (project structure)
- Blocks: T016 (Map service implementation)
- Can run parallel with: T016-T019, T021-T022 (services and other prompts)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T020)
- Priority set to medium (prompt template)