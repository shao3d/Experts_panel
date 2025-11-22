# Frontend Architecture - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

React 18 + TypeScript frontend with real-time multi-expert query progress tracking and comprehensive error handling.

## 🛠️ Technology Stack

- **React 18** - Function components with hooks and concurrent features
- **TypeScript** - Strict mode, full type safety with comprehensive interfaces
- **Vite** - Build tool and dev server (port 3000) with path aliases and HMR
- **SSE (Server-Sent Events)** - Real-time multi-expert progress streaming with enhanced error handling
- **Advanced Debug Logging** - Console/API/SSE event batching system with production compatibility
- **React Markdown** - Markdown rendering with syntax highlighting and GFM support
- **React Query (TanStack Query)** - Server state management and caching (v5.56.2)
- **React Hot Toast** - Elegant notification system for user feedback
- **React Loading Skeleton** - Smooth loading states and skeleton screens
- **clsx** - Conditional className utility for cleaner styling
- **Inline styles** - No CSS frameworks for MVP simplicity with planned migration to CSS modules

## 📁 Project Structure
The frontend source code is located in `frontend/src/` and is organized as follows:
- **`App.tsx`**: The main application component containing the primary state management.
- **`index.tsx`**: The entry point for the React application.
- **`components/`**: Contains all React components, such as `QueryForm.tsx`, `ProgressSection.tsx`, and `ExpertAccordion.tsx`.
- **`services/`**: Houses the API client (`api.ts`) for communicating with the backend, including SSE streaming logic.
- **`utils/`**: Includes utility functions, notably the `debugLogger.ts` for advanced logging.
- **`types/`**: Contains all TypeScript interface definitions, primarily in `api.ts`, which mirror the backend models.

## 🎯 Core Components

The application's UI is built from a set of modular React components located in `frontend/src/components/`.

- **`App.tsx`**: The main application component responsible for overall state management, component orchestration, and handling the primary query lifecycle.
- **`QueryForm.tsx`**: Provides the user input form with real-time validation.
- **`ProgressSection.tsx`**: Displays real-time, multi-expert progress updates streamed from the backend via SSE.
- **`ExpertAccordion.tsx`**: The primary UI element for organizing and displaying responses from multiple experts.
- **`ExpertResponse.tsx`**: Renders the formatted answer, sources, and metadata for a single expert.
- **`PostsList.tsx` & `PostCard.tsx`**: Work together to display the list of source posts, handle selection, and manage navigation. They use a consistent DOM ID pattern (`post-{expertId}-{postId}`) to link sources in the answer to the corresponding post in the list.

For detailed implementation, props, and state management of each component, refer to its source file in the `frontend/src/components/` directory.

## 🔄 Services, Types, and Patterns

### Services Layer
The application's logic for communicating with the backend is centralized in the `frontend/src/services/` directory.
- **`api.ts`**: Contains the `APIClient` class, which encapsulates all `fetch` calls to the backend API. It includes robust logic for handling the SSE stream for progress updates.
- **`error-handler.ts`**: Provides utilities for processing and displaying user-friendly error messages.

### Type System
All TypeScript types and interfaces are defined in the `frontend/src/types/` directory, primarily within `api.ts`. These interfaces are kept in sync with the backend's Pydantic models to ensure type safety across the application.

### Code Patterns
The codebase follows several key patterns:
- **State Management**: Component state is managed using React hooks (`useState`, `useEffect`). For server state, caching, and data fetching, the application uses TanStack Query (React Query).
- **Styling**: To simplify development, the application currently uses inline style objects.
- **Error Handling**: API calls are wrapped in `try/catch` blocks, with a centralized error handler service and user-facing notifications provided by `react-hot-toast`.
- **Dynamic Loading**: Data such as the list of available experts is fetched from the API on application load to ensure the UI is always up-to-date without requiring a deployment.

## 📡 Multi-Expert SSE Communication Flow

```
1. User submits query → App.handleQuerySubmit()
   └─> apiClient.submitQuery(request, onProgressCallback)

2. Backend processes all experts in parallel, streams SSE events
   └─> Phase events per expert: map → medium_scoring → resolve → reduce → language_validation → final
   └─> Expert completion events: expert_complete, expert_error
   └─> Format: "data: {json}\n\n" per line (sanitized for safety)

3. Frontend parses stream line-by-line
   └─> parseSSEStream() processes incremental chunks
   └─> Buffers incomplete JSON lines
   └─> sanitize_for_json() prevents XSS/JSON parse errors
   └─> Calls onProgressCallback for each event with expert tracking

4. Multi-expert Progress UI updates in real-time
   └─> ProgressSection re-renders with active expert count
   └─> Contextual phase messages and warnings
   └─> Individual expert status tracking
   └─> User-friendly error message display

5. Multi-expert final event received
   └─> event_type: 'complete' with MultiExpertQueryResponse data
   └─> App sets result state → ExpertResponse renders per expert
   └─> Expert accordion organization for multiple responses
```

## 🛠️ Build and Development

### Development Commands
All development scripts are defined in the `scripts` section of `package.json`. Key commands include:
- `dev`: Starts the Vite development server.
- `build`: Compiles the TypeScript and builds the application for production.
- `lint`: Runs the ESLint static analysis.
- `type-check`: Validates TypeScript types without a full build.

### Configuration
Frontend-specific configuration, such as server port, path aliases, and the proxy to the backend API, is located in `vite.config.ts`.

## 🐛 Troubleshooting

### SSE Connection Issues
- Check CORS headers from backend
- Verify Content-Type: text/event-stream
- Monitor network tab for stream data

### Type Errors
- Ensure types/api.ts matches backend models
- Run `npm run type-check` to validate
- Check for outdated backend API changes

### Post Reference Clicking Issues
- **Element Not Found**: Verify expertId prop passed to PostCard
- **Inconsistent IDs**: Check DOM ID pattern between components
- **Console Errors**: Look for "element not found" when clicking sources

### Debug Logger Issues
- **Missing Logs**: Check `/api/v1/log-batch` endpoint availability
- **Memory Issues**: Monitor circular buffer (1000 event limit)
- **Performance**: Batch processing every 10 seconds

### Multi-Expert Issues
- **Expert Not Processing**: Check expert_filter parameter and database expert IDs
- **Uneven Processing**: Monitor individual expert completion times
- **Expert Errors**: Look for expert_error events with user-friendly messages
- **Response Organization**: Check expert accordion rendering for multiple responses

### Translation Issues
- **Post Translation**: Verify query language detection and translation API calls
- **Language Detection**: Check TranslationService language logic
- **Mixed Languages**: Ensure language validation phase is working

---

**Related Documentation:**
- **Main Project**: `../CLAUDE.md` - Quick Start and full architecture
- **Backend API**: `../backend/CLAUDE.md` - Complete API reference and endpoints
- **Hybrid Model Configuration**: `../backend/src/config.py` - Environment variables and models
- **Environment Setup**: `../.env.example` - Complete configuration reference