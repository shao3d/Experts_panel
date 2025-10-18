---
task: prompt-reduce
branch: feature/prompt-reduce
status: completed
created: 2025-09-26
modules:
  - prompts
  - backend
tags:
  - telegram-map-resolve
  - phase-3.4-pipeline
---

# Create Reduce Prompt Template

## Problem/Goal
Create the prompt template for the Reduce phase that instructs GPT-4o-mini to synthesize all gathered information into a comprehensive, well-structured answer.

## Context Manifest
**Key Files**:
- backend/prompts/reduce_prompt.txt
- backend/prompts/README.md

**Key Concepts**:
- Answer synthesis instructions
- Source integration
- Comprehensive response generation
- Citation formatting

## Success Criteria
- [ ] reduce_prompt.txt template created
- [ ] Synthesis instructions clear
- [ ] Source attribution format defined
- [ ] Answer structure guidelines
- [ ] Handling conflicting information
- [ ] Markdown formatting rules
- [ ] Completeness vs conciseness balance
- [ ] Version tracking comment

## Implementation Notes
- Emphasize comprehensive answers
- Include post ID citations
- Structure for readability
- Handle contradictions gracefully
- Prioritize expert comments
- Format for web display

## Dependencies
- Previous: T001 (project structure)
- Blocks: T018 (Reduce service implementation)
- Can run parallel with: T016-T021 (services and other prompts)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T022)
- Priority set to medium (prompt template)