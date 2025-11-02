# Frontend Architecture - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

React 18 + TypeScript frontend with real-time query progress tracking and expert feedback display.

## 🛠️ Technology Stack

- **React 18** - Function components with hooks
- **TypeScript** - Strict mode, full type safety
- **Vite** - Build tool and dev server (port 3000)
- **SSE (Server-Sent Events)** - Real-time progress streaming
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
- Query submission and API communication
- Progress events collection via SSE
- Result/error state management
- Posts loading with expert context
- Component orchestration

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

### ProgressSection.tsx - Real-time Progress Tracking
**Features:**
- Active expert count display during processing
- Contextual phase descriptions ("Searching relevant posts...", "Analyzing connections...")
- Warning indicators (⚠️) for processes exceeding 300 seconds
- Frontend-only `final_results` phase for completion detection
- Enhanced resolve phase handling with medium_scoring events
- Real-time elapsed time counter

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

### ExpertResponse.tsx - Answer Display
**Features:**
- Formatted answer text with markdown rendering
- Clickable source references with post navigation
- Expert badge display and confidence indicators
- Language validation status display

**Props:**
```typescript
interface ExpertResponseProps {
  answer: string;
  sources: number[];
  confidence: ConfidenceLevel;
  language: string;
  onPostClick: (postId: number) => void;
}
```

### PostsList.tsx & PostCard.tsx - Content Navigation
**Features:**
- Scrollable posts container with selection highlighting
- Auto-scroll to selected post with smooth animation
- Expert comments section with expand/collapse
- Consistent DOM ID generation for post reference clicking
- Multi-expert support with expertId context

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
Main API client with SSE streaming support:

```typescript
class APIClient {
  async submitQuery(
    request: QueryRequest,
    onProgress?: ProgressCallback
  ): Promise<QueryResponse>

  async checkHealth(): Promise<HealthResponse>
  async getPostDetail(postId: number): Promise<PostDetailResponse>
  async getPostsByIds(postIds: number[]): Promise<PostDetailResponse[]>
}
```

**SSE Streaming Implementation:**
- Line-by-line parsing with incremental buffering
- Progress event extraction and callback handling
- Error recovery and stream state management
- Real-time expert tracking with expert_id context

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
  stream_progress?: boolean;        // Default: true
  expert_filter?: string[];         // Optional expert filtering
}

interface QueryResponse {
  query: string;
  answer: string;
  main_sources: number[];           // telegram_message_ids
  confidence: ConfidenceLevel;      // HIGH, MEDIUM, LOW
  language: string;
  has_expert_comments: boolean;
  posts_analyzed: number;
  expert_comments_included: number;
  relevance_distribution: Record<string, number>;
  processing_time_ms: number;
  request_id: string;
}

interface ProgressEvent {
  event_type: 'phase_start' | 'progress' | 'phase_complete' | 'complete' | 'error';
  phase: string;                    // map, resolve, reduce, comment_groups, etc.
  status: string;
  message: string;
  timestamp?: string;
  data?: Record<string, any>;       // Contains expert_id, response, etc.
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

### 2. Enhanced Progress Event Handling
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
    if (event.data?.expert_id && event.event_type !== 'complete') {
      activeExperts.add(event.data.expert_id);
    }
  });
  return activeExperts.size;
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

## 📡 SSE Communication Flow

```
1. User submits query → App.handleQuerySubmit()
   └─> apiClient.submitQuery(request, onProgressCallback)

2. Backend streams SSE events
   └─> Phase events: map → resolve → reduce → final
   └─> Format: "data: {json}\n\n" per line

3. Frontend parses stream line-by-line
   └─> parseSSEStream() processes incremental chunks
   └─> Buffers incomplete JSON lines
   └─> Calls onProgressCallback for each event

4. Progress UI updates in real-time
   └─> ProgressSection re-renders with expert count
   └─> Contextual messages and warnings
   └─> Active expert tracking

5. Final event received
   └─> event_type: 'complete' with response data
   └─> App sets result state → ExpertResponse renders
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
  server: {
    port: 3000,                    // Fixed port for consistency
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### Package.json Scripts
```json
{
  "dev": "vite --debug --host 2>&1 | tee frontend.log",
  "build": "tsc && vite build",
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

---

**Related Documentation:**
- **Main Project**: `../CLAUDE.md` - Quick Start and full architecture
- **Backend API**: `../backend/CLAUDE.md` - Complete API reference and endpoints
- **Model Configuration**: `../backend/src/config.py` - Environment variables