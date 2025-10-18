---
task: validation-topic-search
branch: feature/validation-topic-search
status: completed
created: 2025-09-26
modules:
  - testing
  - validation
tags:
  - telegram-map-resolve
  - phase-3.2-validation
---

# Create Topic Search Validation Scenario

## Problem/Goal
Create a validation scenario for testing the system's ability to find posts related to specific topics. This will be used to verify the Map phase correctly identifies relevant content.

## Context Manifest
**Key Files**:
- backend/tests/validation/test_topic_search.yaml

**Key Concepts**:
- Q&A test sets instead of unit tests (per constitution)
- Topic-based query validation
- Expected post IDs for verification
- Map phase accuracy testing

## Success Criteria
- [ ] test_topic_search.yaml created with structure
- [ ] 3-5 topic-based test queries defined
- [ ] Expected post IDs listed for each query
- [ ] Relevance criteria documented
- [ ] Edge cases included (ambiguous topics)
- [ ] YAML structure parseable and clear

## Implementation Notes
- Follow constitution Principle III: Validation-First Development
- Include queries with varying complexity
- Document why each post should be found
- Consider partial matches and synonyms
- Test both broad and narrow topic searches

## Dependencies
- Previous: T001 (project structure)
- Blocks: T041 (performance validation)
- Can run parallel with: T008 (reference validation), T009 (test queries)

## Work Log
### 2025-09-26 - Task Migration

### 2025-09-28 - Task Completed
- Created validation directory structure at `backend/tests/validation/`
- Created comprehensive `test_topic_search.yaml` with:
  - 5 main test cases covering different topic types
  - 4 edge cases for ambiguous queries, synonyms, negative queries, and empty results
  - Documented relevance criteria for each test
  - Added performance metrics and quality checks
- Validated YAML structure is parseable with PyYAML
- Based on actual posts in test database (7 posts with IDs: 1,2,3,4,5,6,8)
- Included link relationship testing (replies between posts)
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T007)
- Priority set to medium (validation setup)