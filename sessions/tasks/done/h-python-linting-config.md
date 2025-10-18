---
task: python-linting-config
branch: feature/python-linting-config
status: completed
created: 2025-09-26
started: 2025-09-27
completed: 2025-09-27
modules:
  - backend
tags:
  - telegram-map-resolve
  - phase-3.1-setup
---

# Configure Python Linting and Formatting

## Problem/Goal
Configure Python linting with ruff for code quality and consistent formatting across the backend codebase. Set up proper rules for the project's coding standards.

## Context Manifest
**Key Files**:
- backend/.ruff.toml
- backend/pyproject.toml (optional)

**Key Concepts**:
- Ruff for fast Python linting
- Code formatting standards
- Import sorting
- Type checking integration

## Success Criteria
- [x] backend/.ruff.toml created with project rules
- [x] Line length set to appropriate limit (88 or 100)
- [x] Import sorting configured
- [x] Docstring conventions defined
- [x] Ignore rules for specific patterns if needed
- [x] Pre-commit hooks configured (optional)

## Implementation Notes
- Configure for Python 3.11+ syntax
- Enable pyflakes, pycodestyle checks
- Configure isort-compatible import sorting
- Set up ignore patterns for migrations, tests if needed
- Consider enabling autofix for safe fixes

## Dependencies
- Previous: T002 (Python backend init)
- Blocks: None
- Can run parallel with: T005 (TypeScript linting), T006 (.env.example)

## Work Log
### 2025-09-26 - Task Migration
- Migrated from specs/001-telegram-map-resolve/tasks.md (Original: T004)
- Priority set to high (critical setup task)

### 2025-09-27 - Task Completed
- Created backend/.ruff.toml with comprehensive linting rules
- Configured for Python 3.11+ with line length 88 (Black standard)
- Enabled rules: pycodestyle, pyflakes, bugbear, isort, and more
- Set up import sorting with isort configuration
- Added per-file ignores for tests and __init__ files
- Created backend/pyproject.toml with pytest, coverage, and mypy config
- Google-style docstrings convention configured
- All success criteria met