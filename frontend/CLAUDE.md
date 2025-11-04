# Frontend Architecture - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

React 18 + TypeScript frontend with real-time multi-expert query progress tracking and comprehensive error handling.

## 🛠️ Technology Stack

- **React 18** - Function components with hooks
- **TypeScript** - Strict mode, full type safety
- **Vite** - Build tool and dev server (port 3000) with path aliases
- **SSE (Server-Sent Events)** - Real-time multi-expert progress streaming
- **Advanced Debug Logging** - Console/API/SSE event batching system
- **React Markdown** - Markdown rendering with syntax highlighting
- **React Query** - Server state management (optional)
- **Inline styles** - No CSS frameworks for MVP simplicity

## 📁 Project Structure

```
frontend/src/
├── App.tsx                    # Main application with state management
├── index.tsx                  # Entry point
├── components/
│   ├── QueryForm.tsx          # Query input with validation
│   ├── ProgressSection.tsx    # Enhanced progress display with expert feedback
│   ├── ExpertResponse.tsx     # Answer display with source links
│   ├── PostsList.tsx          # Posts list with selection
│   ├── PostCard.tsx           # Individual post card display
│   ├── ExpertAccordion.tsx    # Expandable expert response sections
│   ├── ExpertSelector.tsx     # Expert selection interface
│   ├── ExpertSelectionBar.tsx # Expert filtering and selection bar
│   ├── StatsAndSelectors.tsx  # Statistics display and filtering controls
│   ├── CommentSynthesis.tsx   # Comment synthesis display component
│   ├── CommentGroupsList.tsx  # Comment groups list interface
│   ├── ProgressLog.tsx        # Legacy SSE progress events
│   └── QueryResult.tsx        # Legacy result container
├── services/
│   ├── api.ts                 # APIClient with SSE streaming
│   ├── error-handler.ts       # Error handling utilities
│   └── index.ts               # Service exports
├── utils/
│   └── debugLogger.ts         # Console/SSE/API logging utility
└── types/
    └── api.ts                 # TypeScript interfaces (matches backend)
```

## 🎯 Core Components

### App.tsx - Main Application State
```typescript
const [isProcessing, setIsProcessing] = useState(false);
const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
const [result, setResult] = useState<QueryResponse | null>(null);
const [error, setError] = useState<string | null>(null);
const [posts, setPosts] = useState<PostDetail[]>([]);
const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
```

**Responsibilities:**
- Multi-expert query submission and API communication
- Progress events collection via SSE with expert tracking
- Multi-expert result/error state management
- Posts loading with expert context and translation support
- Component orchestration and error boundary handling

### QueryForm.tsx - Input Validation
**Features:**
- Character limit: 3-1000 chars with real-time counter
- Submit validation and disabled state during processing
- Clear error handling and user feedback

**Props:**
```typescript
interface QueryFormProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
  placeholder?: string;
}
```

### ProgressSection.tsx - Real-time Multi-Expert Progress Tracking
**Features:**
- Active expert count display during parallel processing
- Contextual phase descriptions ("Searching relevant posts...", "Medium scoring...", "Analyzing connections...")
- Warning indicators (⚠️) for processes exceeding 300 seconds
- Frontend-only `final_results` phase for completion detection
- Enhanced phase handling: map, medium_scoring, resolve, reduce, language_validation
- Real-time elapsed time counter per expert
- Error event display with user-friendly messages

**Props:**
```typescript
interface ProgressSectionProps {
  isProcessing: boolean;
  progressEvents: ProgressEvent[];
  stats?: {
    totalPosts: number;
    processingTime: number;
    expertCount?: number;
  };
}
```

### ExpertResponse.tsx - Multi-Expert Answer Display
**Features:**
- Formatted answer text with markdown and syntax highlighting
- Clickable source references with expert-aware post navigation
- Expert badge display with confidence indicators and processing time
- Language validation status display
- Multi-expert response rendering with accordion organization
- Comment groups synthesis display
- Error state handling for individual expert failures

**Props:**
```typescript
interface ExpertResponseProps {
  answer: string;
  sources: number[];
  confidence: ConfidenceLevel;
  language: string;
  onPostClick: (postId: number) => void;
  expertId?: string;
  expertName?: string;
  processingTime?: number;
}
```

### PostsList.tsx & PostCard.tsx - Expert-Aware Content Navigation
**Features:**
- Scrollable posts container with selection highlighting
- Auto-scroll to selected post with smooth animation
- Expert comments section with expand/collapse
- Consistent DOM ID generation for expert-aware post reference clicking
- Multi-expert support with expertId context and channel usernames
- Translation support for posts with language detection
- Expert badge display and metadata

**DOM ID Pattern:**
```typescript
// PostCard.tsx - Reliable element lookup
id={`post-${expertId || 'unknown'}-${post.telegram_message_id}`}

// PostsList.tsx - Element lookup with fallback
let element = document.getElementById(`post-${expertId || 'unknown'}-${selectedPostId}`);
if (!element) {
  element = document.getElementById(`post-${selectedPostId}`); // Backward compatibility
}
```

## 🔄 Services Layer

### APIClient (services/api.ts)
Main API client with multi-expert SSE streaming support:

```typescript
class APIClient {
  async submitQuery(
    request: QueryRequest,
    onProgress?: ProgressCallback
  ): Promise<MultiExpertQueryResponse>

  async checkHealth(): Promise<HealthResponse>
  async getPostDetail(postId: number, expertId?: string, query?: string, translate?: boolean): Promise<PostDetailResponse>
  async getPostsByIds(postIds: number[]): Promise<PostDetailResponse[]>
  async logBatch(events: LogEvent[]): Promise<void>
}
```

**SSE Streaming Implementation:**
- Line-by-line parsing with incremental buffering
- Multi-expert progress event extraction and callback handling
- Error recovery and stream state management
- Real-time expert tracking with expert_id context
- User-friendly error message processing
- Event sanitization for safe JSON transmission

### Debug Logger (utils/debugLogger.ts)
Advanced logging system for development debugging:

**Features:**
- **Console Interception**: Captures all console.log/warn/error with recursion prevention
- **SSE Event Logging**: Real-time pipeline phase tracking with expert context
- **API Request Monitoring**: Automatic fetch/XHR interception with timing
- **Batch Processing**: 10-second interval batching to `/api/v1/log-batch`
- **Memory Management**: 1000-event circular buffer prevents memory leaks

**Usage:**
```typescript
import { debugLogger } from './utils/debugLogger';

// Automatic console capture
console.log('User interaction detected'); // Automatically logged

// Manual SSE event logging
debugLogger.logSSEEvent('map', 'phase_start', { expert_id: 'refat' });
```

## 📝 Type System

Complete TypeScript interfaces matching backend Pydantic models:

### Key Interfaces
```typescript
interface QueryRequest {
  query: string;                    // 3-1000 chars
  max_posts?: number;
  include_comments?: boolean;
  include_comment_groups?: boolean; // Comment analysis
  stream_progress?: boolean;        // Default: true
  expert_filter?: string[];         // Optional expert filtering
}

interface MultiExpertQueryResponse {
  query: string;
  expert_responses: ExpertResponse[];
  total_processing_time_ms: number;
  request_id: string;
}

interface ExpertResponse {
  expert_id: string;
  expert_name: string;
  channel_username: string;
  answer: string;
  main_sources: number[];           // telegram_message_ids
  confidence: ConfidenceLevel;      // HIGH, MEDIUM, LOW
  posts_analyzed: number;
  processing_time_ms: number;
  relevant_comment_groups: CommentGroupResponse[];
  comment_groups_synthesis?: string;
}

interface ProgressEvent {
  event_type: 'phase_start' | 'progress' | 'phase_complete' | 'complete' | 'error' | 'expert_complete' | 'expert_error';
  phase: string;                    // map, medium_scoring, resolve, reduce, language_validation, etc.
  status: string;
  message: string;
  timestamp?: string;
  data?: Record<string, any>;       // Contains expert_id, error_info, user_friendly, etc.
}
```

## 🎨 Code Patterns

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
    fontWeight: '600' as const,
    cursor: 'pointer'
  }
};
```

### 2. Enhanced Multi-Expert Progress Event Handling
```typescript
// Special phase status logic
const getPhaseStatus = (phaseName: string): 'pending' | 'active' | 'completed' => {
  if (phaseName === 'resolve') {
    // Combine resolve + medium_scoring events for comprehensive status
  }
  if (phaseName === 'final_results') {
    // Frontend-only completion detection
  }
  // Standard phase logic
};

// Active expert count extraction
const getActiveExpertsCount = (): number => {
  const activeExperts = new Set();
  progressEvents.forEach(event => {
    if (event.data?.expert_id && event.event_type !== 'complete' && event.event_type !== 'expert_complete') {
      activeExperts.add(event.data.expert_id);
    }
  });
  return activeExperts.size;
};

// Error event processing with user-friendly messages
const processErrorEvent = (event: ProgressEvent): string => {
  if (event.data?.user_friendly && event.data?.error_info) {
    return event.data.error_info.message || event.message;
  }
  return event.message;
};
```

### 3. Error Handling Pattern
```typescript
try {
  const response = await apiClient.submitQuery(request, onProgress);
  setResult(response);
} catch (err) {
  const errorMessage = err instanceof Error ? err.message : 'Произошла ошибка';
  setError(errorMessage);
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
  setSelectedPostId(null);
};
```

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

## 🛠️ Development Commands

```bash
# Install dependencies
npm install

# Run development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check

# Preview production build
npm run preview
```

## 🎯 Key Architectural Decisions

### 1. SSE Over WebSockets
- Simpler HTTP-based protocol
- Built-in browser support
- Unidirectional flow (sufficient for progress updates)

### 2. Inline Styles Over CSS Frameworks
- Faster MVP development
- Component-local styling
- Easy to replace later

### 3. Vertical Layout (15%/40%/45%)
- Query & Progress: 15% (top)
- Expert Response: 40% (middle)
- Posts with Comments: 45% (bottom)

### 4. Post Reference Clicking System
- **Consistent DOM IDs**: expertId-based pattern across components
- **Multi-Expert Support**: Works across different expert channels
- **Backward Compatibility**: Fallback ID pattern for edge cases

## 🔧 Frontend-Only Configuration

### Vite Configuration (vite.config.ts)
```typescript
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@services': path.resolve(__dirname, './src/services'),
      '@types': path.resolve(__dirname, './src/types'),
    },
  },
  server: {
    port: 3000,                    // Fixed port for consistency
    strictPort: true,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
```

### Package.json Scripts
```json
{
  "dev": "vite --debug --host 2>&1 | tee frontend.log",
  "dev-logs": "DEBUG=vite:* node --inspect vite --debug --host 2>&1 | tee ../frontend-debug.log",
  "build": "tsc && vite build",
  "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
  "preview": "vite preview",
  "type-check": "tsc --noEmit"
}
```

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