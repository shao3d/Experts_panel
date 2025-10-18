---
task: validation-reference-follow
branch: feature/validation-reference-follow
status: completed
created: 2025-09-26
modules:
  - testing
  - validation
tags:
  - telegram-map-resolve
  - phase-3.2-validation
---

# Create Reference Following Validation Scenario

## Problem/Goal
Create a validation scenario for testing the system's ability to follow references and links between posts. This validates the Resolve phase's depth-2 enrichment capability.

## Context Manifest
**Key Files**:
- backend/tests/validation/test_reference_follow.yaml

**Key Concepts**:
- Link traversal validation
- Depth-2 reference following
- Resolve phase accuracy
- Chain of references testing

## Success Criteria
- [ ] test_reference_follow.yaml created with structure
- [ ] Test cases for direct references (depth 1)
- [ ] Test cases for indirect references (depth 2)
- [ ] Expected link chains documented
- [ ] Circular reference handling tested
- [ ] Missing reference handling tested

## Implementation Notes
- Test both forward and reply references
- Include cases where referenced posts are deleted
- Verify depth limit is respected (max 2 levels)
- Test performance with heavily linked posts
- Document expected traversal paths

## Dependencies
- Previous: T001 (project structure)
- Blocks: T041 (performance validation)
- Can run parallel with: T007 (topic search), T009 (test queries)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T008)
- Priority set to medium (validation setup)

### 2025-09-28 - Task Completed
- Created comprehensive `test_reference_follow.yaml` with:
  - 5 reference following test cases (direct replies)
  - 2 depth-2 traversal scenarios
  - 4 edge cases (circular references, missing targets, empty sets)
  - 2 performance test scenarios
- Validated YAML structure with PyYAML
- Tests based on actual link relationships in database (2→1, 6→4 replies)
- Included tests for all link types (reply, forward, mention)
- Added relevance scoring rules for different link types
- Documented expected traversal paths and enrichment results