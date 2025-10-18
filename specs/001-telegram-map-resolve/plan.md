
# Implementation Plan: Intelligent Telegram Channel Analysis System

**Branch**: `001-telegram-map-resolve` | **Date**: 2025-09-26 | **Spec**: spec.md
**Input**: Feature specification from `/specs/001-telegram-map-resolve/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Building an intelligent Telegram channel analysis system that uses Map-Resolve-Reduce architecture to process interconnected posts and provide comprehensive, context-aware answers to natural language queries. The system will handle channels with 100-300 posts, preserve all cross-references between posts, and provide full source transparency.

## Technical Context
**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy, OpenAI SDK  
**Storage**: SQLite with foreign keys for relationships  
**Testing**: Validation through Q&A test sets (not unit tests for MVP)  
**Target Platform**: Docker container deployable to Railway
**Project Type**: web - frontend + backend architecture  
**Performance Goals**: 2-3 minute query response time, 100% recall  
**Constraints**: Process 30 posts per chunk, 2-level resolve depth, no caching (accuracy first)  
**Scale/Scope**: MVP for single channel, 100-300 posts, single user

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Map-Resolve-Reduce architecture used (not RAG) - Principle I
- [x] Full source transparency with expandable posts - Principle II
- [x] Validation criteria defined (test Q&A sets) - Principle III
- [x] Learning-oriented with observable decisions - Principle IV
- [x] SQLite with proper foreign keys for links - Principle V
- [x] Process transparency with detailed logging - Principle VI
- [x] No caching for MVP (accuracy first) - Principle VII
- [x] Using only GPT-4o-mini for all phases - Technical Constraint
- [x] Data-first development order - Development Order

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
backend/
├── src/
│   ├── models/
│   │   ├── post.py
│   │   ├── link.py
│   │   └── comment.py
│   ├── services/
│   │   ├── map_service.py
│   │   ├── resolve_service.py
│   │   ├── reduce_service.py
│   │   └── log_service.py
│   ├── api/
│   │   ├── main.py
│   │   └── query_endpoints.py
│   └── data/
│       ├── json_parser.py
│       └── comment_collector.py
├── prompts/
│   ├── map_prompt.txt
│   ├── resolve_prompt.txt
│   └── reduce_prompt.txt
└── tests/
    └── validation/
        └── test_queries.yaml

frontend/
├── src/
│   ├── components/
│   │   ├── QueryInput.tsx
│   │   ├── ProcessLog.tsx
│   │   ├── Answer.tsx
│   │   └── SourceViewer.tsx
│   ├── pages/
│   │   └── MainPage.tsx
│   └── services/
│       └── api.ts
└── public/

data/
├── exports/         # Telegram JSON exports
└── experts.db       # SQLite database
```

**Structure Decision**: Web application structure selected due to frontend + backend requirements. Backend handles Map-Resolve-Reduce pipeline with FastAPI, frontend provides React interface with live progress display. Separate data directory for persistence.

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Data import tasks from data-model.md entities
- API endpoint tasks from contracts/api-spec.yaml
- Pipeline tasks for Map-Resolve-Reduce phases
- Frontend component tasks for progress display

**Task Categories for This Feature**:
1. **Data Layer** (6-8 tasks)
   - SQLite schema creation
   - JSON parser implementation
   - Comment collector CLI
   - Link extraction and resolution

2. **Pipeline Core** (8-10 tasks)
   - Map service with chunking
   - Resolve service with depth control
   - Reduce service with synthesis
   - Simple logging service (no cache for MVP)
   - Prompt management system

3. **API Layer** (4-5 tasks)
   - FastAPI setup with CORS
   - Query endpoint with SSE
   - Post detail endpoint
   - Import endpoint
   - Health check

4. **Frontend** (5-6 tasks)
   - Query input component
   - Progress log display with SSE
   - Answer display with sources
   - Expandable post viewer
   - Comment display

5. **Integration** (3-4 tasks)
   - Docker configuration
   - Environment setup
   - Validation test suite
   - Deployment preparation

**Ordering Strategy**:
- Data layer first (need database for everything)
- Pipeline core next (business logic)
- API layer (expose functionality)
- Frontend (user interface)
- Integration last (deployment ready)
- Mark [P] for parallel execution within each phase

**Estimated Output**: 26-33 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

No violations identified. The implementation follows all constitutional principles:
- ✅ Map-Resolve-Reduce architecture (not RAG)
- ✅ Full source transparency
- ✅ Validation-first approach
- ✅ Learning-oriented MVP
- ✅ Data integrity with SQLite foreign keys
- ✅ Process transparency with detailed logging
- ✅ No caching for MVP (accuracy first)
- ✅ Using only GPT-4o-mini
- ✅ Data-first development order


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [ ] Complexity deviations documented (none required)

---
*Based on Constitution v2.0.0 - See `/memory/constitution.md`*
