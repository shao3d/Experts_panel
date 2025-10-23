# Frontend Architecture - Experts Panel

## Overview

React 18 + TypeScript frontend with SSE streaming for real-time query progress. Built for MVP with inline styles, focusing on type safety and direct API communication.

## Technology Stack

- **React 18** - Function components with hooks
- **TypeScript** - Strict mode, full type safety
- **Vite** - Build tool and dev server
- **SSE (Server-Sent Events)** - Real-time progress streaming
- **Inline styles** - No CSS frameworks for MVP simplicity

## Project Structure

```
frontend/src/
├── App.tsx                    # Main application with state management
├── index.tsx                  # Entry point
├── components/
│   ├── QueryForm.tsx          # Query input with validation
│   ├── ProgressSection.tsx    # Progress display & statistics
│   ├── ExpertResponse.tsx     # Answer display with source links
│   ├── PostsList.tsx          # Posts list with selection
│   ├── PostCard.tsx           # Individual post card display
│   ├── ProgressLog.tsx        # SSE progress events (legacy)
│   └── QueryResult.tsx        # Result container (legacy)
├── services/
│   ├── api.ts                 # APIClient with fixed SSE streaming
│   ├── error-handler.ts       # Error handling utilities
│   └── index.ts               # Service exports
└── types/
    └── api.ts                 # TypeScript interfaces (matches backend)
```

## Core Components

### App.tsx
Main application component managing all state:

```typescript
const [isProcessing, setIsProcessing] = useState(false);
const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
const [result, setResult] = useState<QueryResponse | null>(null);
const [error, setError] = useState<string | null>(null);
const [posts, setPosts] = useState<PostDetail[]>([]);
const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
const [postsLoading, setPostsLoading] = useState(false);
```

**Responsibilities:**
- Query submission handling
- Progress events collection
- Result/error state management
- Posts loading and selection
- Component orchestration

### QueryForm.tsx
Query input form with validation:

**Features:**
- Character limit: 3-1000 chars
- Real-time character counter
- Submit validation
- Disabled state during processing

**Props:**
```typescript
interface QueryFormProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
  placeholder?: string;
}
```

### ProgressSection.tsx
Progress display with statistics:

**Features:**
- Real-time processing status
- Statistics display (posts, time, experts)
- Compact event log view
- Phase indicators

**Props:**
```typescript
interface ProgressSectionProps {
  isProcessing: boolean;
  progressEvents: ProgressEvent[];
  stats?: {
    totalPosts: number;
    processingTime: number;
    expertCount: number;
  };
}
```

### ExpertResponse.tsx
Answer display with source links:

**Features:**
- Formatted answer text
- Clickable source references
- Post ID highlighting
- Expert badge display

**Props:**
```typescript
interface ExpertResponseProps {
  answer: string;
  sources: number[];
  onPostClick: (postId: number) => void;
}
```

### PostsList.tsx
Posts listing with selection:

**Features:**
- Scrollable posts container
- Post selection highlighting
- Auto-scroll to selected post
- Responsive layout

**Props:**
```typescript
interface PostsListProps {
  posts: PostDetail[];
  selectedPostId: number | null;
}
```

### PostCard.tsx
Individual post card display:

**Features:**
- Post content with formatting
- Author and date display
- Expert comments section
- Selection state styling

**Props:**
```typescript
interface PostCardProps {
  post: PostDetail;
  isSelected: boolean;
}
```

## Services Layer

### APIClient (services/api.ts)

Main API client with SSE streaming support:

```typescript
class APIClient {
  private baseURL: string;

  async submitQuery(
    request: QueryRequest,
    onProgress?: ProgressCallback
  ): Promise<QueryResponse>

  async checkHealth(): Promise<HealthResponse>
  async getPostDetail(postId: number): Promise<PostDetailResponse>
  async getPostsByIds(postIds: number[]): Promise<PostDetailResponse[]>
}

export const apiClient = new APIClient(); // Singleton instance
```

**SSE Streaming Implementation:**

```typescript
private async parseSSEStream(
  response: Response,
  onProgress?: ProgressCallback
): Promise<QueryResponse> {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  // Parse SSE format: "data: {json}\n\n"
  // Extract progress events and final response
  // Handle event.data.response for final result
}
```

**Progress Callback Pattern:**

```typescript
await apiClient.submitQuery(
  { query, stream_progress: true },
  (event: ProgressEvent) => {
    // Real-time progress updates
    setProgressEvents(prev => [...prev, event]);
  }
);
```

## Type System (types/api.ts)

Full TypeScript interfaces matching backend Pydantic models:

### Enums
```typescript
enum RelevanceLevel { HIGH, MEDIUM, LOW, CONTEXT }
enum ConfidenceLevel { HIGH, MEDIUM, LOW }
```

### Request Models
```typescript
interface QueryRequest {
  query: string;                    // 3-1000 chars
  max_posts?: number;
  include_comments?: boolean;
  stream_progress?: boolean;        // Default: true
}
```

### Response Models
```typescript
interface QueryResponse {
  query: string;
  answer: string;
  main_sources: number[];           // telegram_message_ids
  confidence: ConfidenceLevel;
  language: string;
  has_expert_comments: boolean;
  posts_analyzed: number;
  expert_comments_included: number;
  relevance_distribution: Record<string, number>;
  token_usage?: TokenUsage;
  processing_time_ms: number;
  request_id: string;
}
```

### SSE Events
```typescript
interface ProgressEvent {
  event_type: 'phase_start' | 'progress' | 'phase_complete' | 'complete' | 'error';
  phase: string;                    // map/resolve/reduce/final
  status: string;
  message: string;
  timestamp?: string;
  data?: Record<string, any>;       // Contains response on 'complete'
}
```

## Code Patterns

### 1. Inline Styles for MVP

All components use inline styles via style objects:

```typescript
const styles = {
  container: {
    padding: '20px',
    backgroundColor: '#f5f5f5',
    borderRadius: '8px'
  },
  button: {
    fontSize: '16px',
    fontWeight: '600' as const,    // Explicit type for TS
    cursor: 'pointer'
  }
};

return <div style={styles.container}>...</div>;
```

**Benefits:**
- Zero external dependencies
- Component-local styles
- Easy to prototype
- No build complexity

### 2. Progress Event Handling

```typescript
// Collect events in array
setProgressEvents(prev => [...prev, event]);

// Display with phase icons
function getPhaseIcon(phase: string): string {
  const icons: Record<string, string> = {
    'map': '🗺️',
    'resolve': '🔗',
    'reduce': '📝',
    'final': '🎯'
  };
  return icons[phase] || '•';
}
```

### 3. Error Handling

```typescript
try {
  const response = await apiClient.submitQuery(...);
  setResult(response);
} catch (err) {
  const errorMessage = err instanceof Error
    ? err.message
    : 'Произошла ошибка';
  setError(errorMessage);
  console.error('Query failed:', err);
} finally {
  setIsProcessing(false);
}
```

### 4. State Reset Pattern

```typescript
const handleReset = (): void => {
  setProgressEvents([]);
  setResult(null);
  setError(null);
};
```

## SSE Communication Flow

```
1. User submits query
   └─> App.handleQuerySubmit()
       └─> apiClient.submitQuery(request, onProgressCallback)

2. Backend starts streaming (simplified phases)
   └─> Phase 1: Map (find relevant posts)
   └─> Phase 2: Resolve+Reduce (expand & synthesize)
   └─> SSE format: line-by-line "data: {json}"

3. Frontend parses stream (fixed parsing)
   └─> parseSSEStream() processes line-by-line
       └─> Buffers incomplete JSON lines
       └─> Calls onProgressCallback for each event
           └─> App updates progressEvents state
               └─> ProgressSection re-renders

4. Backend sends final event
   └─> event_type: 'complete'
       └─> event.data.response contains QueryResponse
           └─> parseSSEStream() returns finalResponse
               └─> App sets result state
                   └─> ExpertResponse renders
                   └─> PostsList loads posts via API
```

## Development Commands

```bash
# Install dependencies
npm install

# Run development server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check

# Preview production build
npm run preview
```

## Code Style Guidelines

### TypeScript
- **Strict mode enabled** - No implicit any
- **Explicit return types** - All functions must specify return type
- **Interface over type** - Use interface for object shapes
- **No any types** - Use unknown or proper types
- **Const assertions** - Use `as const` for style objects

### React
- **Function components only** - No class components
- **Hooks pattern** - useState, useEffect, custom hooks
- **Props interfaces** - All props must have interface
- **Explicit typing** - No implicit children or props

### Naming Conventions
- **Components**: PascalCase (QueryForm.tsx)
- **Functions**: camelCase (handleSubmit)
- **Interfaces**: PascalCase with descriptive names
- **Files**: Match component name exactly

## API Integration

### Base URL Configuration
```typescript
// Development
const apiClient = new APIClient('http://localhost:8000');

// Production (VPS/Cloud)
const apiClient = new APIClient('https://your-domain.com');
```

### Production Deployment Configuration
The frontend is configured for production deployment with nginx:

#### Docker Configuration
- **Multi-stage build**: Node.js build stage + nginx production stage
- **Base images**: node:18-alpine (build), nginx:alpine (production)
- **Static serving**: nginx serves optimized build files from /usr/share/nginx/html
- **Port**: 80 (standard HTTP port)

#### Nginx Features
- **API proxy**: `/api/*` requests proxied to backend service
- **SSE support**: Special headers for Server-Sent Events streaming
- **SPA routing**: All non-file requests served to index.html
- **Gzip compression**: Automatic compression for text-based assets
- **Static caching**: Long-term caching for JS/CSS/image assets

#### Production vs Development
- **Development**: Vite dev server on port 5173 with HMR
- **Production**: nginx serving static files with API proxy
- **API communication**: Uses relative URLs (`/api/*`) in production
- **Environment detection**: Base URL configured per deployment environment

### Health Check
```typescript
const health = await apiClient.checkHealth();
// Returns: { status, version, database, openai_configured, timestamp }
```

### Query Submission
```typescript
const response = await apiClient.submitQuery(
  {
    query: "Ваш вопрос",
    stream_progress: true,
    include_comments: true
  },
  (event) => console.log(event.message)
);
```

### Post Details
```typescript
const post = await apiClient.getPostDetail(12345);
// Returns: PostDetailResponse with comments and links

const posts = await apiClient.getPostsByIds([1, 2, 3]);
// Returns: Array of PostDetailResponse (failed requests filtered out)
```

## Key Architectural Decisions

### 1. SSE Over WebSockets
- Simpler protocol (HTTP-based)
- Built-in browser support
- Unidirectional (sufficient for progress updates)
- Line-by-line parsing (fixed SSE handling)

### 2. Inline Styles Over CSS Frameworks
- Faster MVP development
- No Tailwind/Material-UI learning curve
- Component-scoped styling
- Easy to replace later

### 3. Vertical Layout (15%/40%/45%)
- Query & Progress at top (15%)
- Expert Response in middle (40%)
- Posts with Comments at bottom (45%)
- Optimized for information hierarchy

### 4. Singleton APIClient
- Single source of truth for base URL
- Fixed SSE parsing with buffering
- Parallel post fetching support
- Convenient default export

### 5. Type Safety First
- All API types match backend Pydantic models
- No runtime type checking needed
- Compiler catches integration errors
- Self-documenting interfaces

## Performance Considerations

### SSE Stream Parsing
- Incremental buffer parsing (no memory bloat)
- Early release of reader lock
- Error handling preserves stream state

### Progress Events
- Append-only array (no splice/filter during processing)
- React key by index (stable ordering)
- Max-height with scroll (no DOM overflow)

### Result Display
- Conditional rendering (hide until ready)
- No virtualization needed (small result sets)
- Simple grid layout (no complex calculations)

## Future Enhancements

When moving beyond MVP:

1. **Styling System**
   - Replace inline styles with CSS modules or styled-components
   - Add dark mode support
   - Implement responsive breakpoints

2. **State Management**
   - Consider Zustand/Redux if state grows complex
   - Add persistence for query history

3. **Testing**
   - Add Jest + React Testing Library
   - Mock SSE streams for testing
   - Component snapshot tests

4. **Advanced Features**
   - Source post preview on hover
   - Export results to PDF/JSON
   - Query history and bookmarks
   - Advanced filtering options

## Troubleshooting

### SSE Connection Issues
- Check CORS headers from backend
- Verify Content-Type: text/event-stream
- Check browser network tab for stream data

### Type Errors
- Ensure types/api.ts matches backend models
- Run `npm run type-check` to validate
- Check for outdated backend API changes

### Rendering Issues
- Verify React key props on lists
- Check state updates in React DevTools
- Ensure async operations use finally block
