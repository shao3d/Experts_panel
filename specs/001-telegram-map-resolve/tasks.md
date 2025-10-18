# Tasks: Intelligent Telegram Channel Analysis System

**Input**: Design documents from `/specs/001-telegram-map-resolve/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Web app**: `backend/src/`, `frontend/src/`
- Docker at repository root
- Data directory at `data/`

## Phase 3.1: Setup
- [ ] T001 Create project structure per implementation plan (backend/, frontend/, data/, prompts/)
- [ ] T002 Initialize Python backend with FastAPI, Pydantic v2, SQLAlchemy dependencies in backend/requirements.txt
- [ ] T003 Initialize React frontend with TypeScript in frontend/package.json
- [ ] T004 [P] Configure Python linting (ruff) and formatting in backend/.ruff.toml
- [ ] T005 [P] Configure TypeScript linting and strict mode in frontend/tsconfig.json
- [ ] T006 [P] Create .env.example with OPENAI_API_KEY placeholder

## Phase 3.2: Validation Setup (Per Constitution Principle III)
**Focus on Q&A test sets for validation, not formal unit tests**
- [ ] T007 [P] Create topic search validation scenario in backend/tests/validation/test_topic_search.yaml
- [ ] T008 [P] Create reference following validation scenario in backend/tests/validation/test_reference_follow.yaml
- [ ] T009 [P] Create comprehensive test queries with expected posts in backend/tests/validation/test_queries.yaml

## Phase 3.3: Core Implementation - Data Layer
- [ ] T010 [P] Post model with all fields and relationships in backend/src/models/post.py
- [ ] T011 [P] Link model with foreign key constraints in backend/src/models/link.py
- [ ] T012 [P] Comment model with post relationship in backend/src/models/comment.py
- [ ] T013 Create SQLite database schema and indexes in backend/src/models/database.py
- [ ] T014 [P] JSON parser for Telegram exports in backend/src/data/json_parser.py
- [ ] T015 [P] Interactive comment collector CLI in backend/src/data/comment_collector.py

## Phase 3.4: Core Implementation - Pipeline Services
- [ ] T016 [P] Map service with 30-post chunking in backend/src/services/map_service.py
- [ ] T017 [P] Resolve service with 2-level depth control in backend/src/services/resolve_service.py
- [ ] T018 [P] Reduce service with synthesis logic in backend/src/services/reduce_service.py
- [ ] T019 [P] Simple logging service for process transparency in backend/src/services/log_service.py
- [ ] T020 [P] Create map prompt template in backend/prompts/map_prompt.txt
- [ ] T021 [P] Create resolve prompt template in backend/prompts/resolve_prompt.txt
- [ ] T022 [P] Create reduce prompt template in backend/prompts/reduce_prompt.txt

## Phase 3.5: Core Implementation - API Layer
- [ ] T023 FastAPI application with CORS configuration in backend/src/api/main.py
- [ ] T024 POST /api/query endpoint with SSE streaming in backend/src/api/query_endpoints.py
- [ ] T025 GET /api/posts/{postId} endpoint implementation in backend/src/api/query_endpoints.py
- [ ] T026 POST /api/import endpoint for JSON files in backend/src/api/query_endpoints.py
- [ ] T027 POST /api/comments/collect endpoint in backend/src/api/query_endpoints.py
- [ ] T028 GET /health endpoint in backend/src/api/main.py

## Phase 3.6: Frontend Implementation
- [ ] T029 [P] QueryInput component with validation in frontend/src/components/QueryInput.tsx
- [ ] T030 [P] ProcessLog component with SSE handling in frontend/src/components/ProcessLog.tsx
- [ ] T031 [P] Answer component with markdown rendering in frontend/src/components/Answer.tsx
- [ ] T032 [P] SourceViewer component with expandable posts in frontend/src/components/SourceViewer.tsx
- [ ] T033 MainPage component integrating all components in frontend/src/pages/MainPage.tsx
- [ ] T034 [P] API client service with type definitions in frontend/src/services/api.ts

## Phase 3.7: Integration
- [ ] T035 Connect all services to SQLAlchemy models in backend/src/services/
- [ ] T036 Implement SSE progress updates in query endpoint
- [ ] T037 Add error handling and logging throughout backend
- [ ] T038 Frontend error handling and loading states
- [ ] T039 Create Dockerfile for combined deployment
- [ ] T040 Create docker-compose.yml for local development

## Phase 3.8: Polish & Validation
- [ ] T041 Performance validation (<3 minute response time) using test queries
- [ ] T042 [P] Update README.md with setup instructions
- [ ] T043 Run quickstart.md validation checklist
- [ ] T044 Prepare Railway deployment configuration

## Dependencies
- Setup (T001-T006) must complete first
- Validation scenarios (T007-T009) can be prepared early
- Data models (T010-T012) before database schema (T013)
- Database schema (T013) before parsers (T014-T015)
- Pipeline services (T016-T022) can run after models
- API endpoints (T023-T028) require services
- Frontend (T029-T034) can start after API design
- Integration (T035-T040) requires all core components
- Polish & Validation (T041-T044) comes last

## Parallel Execution Examples

### Phase 3.1 Setup (T004-T006 in parallel):
```
Task: "Configure Python linting (ruff) and formatting in backend/.ruff.toml"
Task: "Configure TypeScript linting and strict mode in frontend/tsconfig.json"
Task: "Create .env.example with OPENAI_API_KEY placeholder"
```

### Phase 3.2 Validation Setup (T007-T009 in parallel):
```
Task: "Create topic search validation scenario in backend/tests/validation/test_topic_search.yaml"
Task: "Create reference following validation scenario in backend/tests/validation/test_reference_follow.yaml"
Task: "Create comprehensive test queries with expected posts in backend/tests/validation/test_queries.yaml"
```

### Phase 3.3 Data Models (T010-T012, T014-T015 in parallel):
```
Task: "Post model with all fields and relationships in backend/src/models/post.py"
Task: "Link model with foreign key constraints in backend/src/models/link.py"
Task: "Comment model with post relationship in backend/src/models/comment.py"
Task: "JSON parser for Telegram exports in backend/src/data/json_parser.py"
Task: "Interactive comment collector CLI in backend/src/data/comment_collector.py"
```

### Phase 3.4 Pipeline Services (T016-T022 in parallel):
```
Task: "Map service with 30-post chunking in backend/src/services/map_service.py"
Task: "Resolve service with 2-level depth control in backend/src/services/resolve_service.py"
Task: "Reduce service with synthesis logic in backend/src/services/reduce_service.py"
Task: "Simple logging service for process transparency in backend/src/services/log_service.py"
Task: "Create map prompt template in backend/prompts/map_prompt.txt"
Task: "Create resolve prompt template in backend/prompts/resolve_prompt.txt"
Task: "Create reduce prompt template in backend/prompts/reduce_prompt.txt"
```

### Phase 3.6 Frontend Components (T029-T032, T034 in parallel):
```
Task: "QueryInput component with validation in frontend/src/components/QueryInput.tsx"
Task: "ProcessLog component with SSE handling in frontend/src/components/ProcessLog.tsx"
Task: "Answer component with markdown rendering in frontend/src/components/Answer.tsx"
Task: "SourceViewer component with expandable posts in frontend/src/components/SourceViewer.tsx"
Task: "API client service with type definitions in frontend/src/services/api.ts"
```

## Notes
- [P] tasks = different files, no shared state
- Validation through Q&A test sets, not unit tests (Principle III)
- Commit after each completed task
- No caching in MVP (per constitution)
- 30 posts per chunk (per research.md)
- 2-level resolve depth maximum
- SSE for progress updates, not WebSockets
- SQLite with foreign keys for relationships

## Validation Checklist
*GATE: All must pass before execution*

- [x] All 3 entities have model tasks (T010-T012)
- [x] Validation scenarios prepared (T007-T009)
- [x] All API endpoints have implementations (T024-T028)
- [x] Parallel tasks use different files
- [x] Each task specifies exact file path
- [x] No [P] tasks modify same file
- [x] Validation scenarios from quickstart.md included (T007-T008)
- [x] All prompts as external files (T020-T022)
- [x] Follows Validation-First principle from constitution

**Total Tasks**: 44 numbered, ordered, executable tasks ready for implementation