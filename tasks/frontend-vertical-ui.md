# Task: Frontend Vertical UI Implementation

## Objective
Implement new vertical UI layout for Experts Panel frontend with collapsible comments and scalability for multi-expert system.

## Context

### Current State
- Frontend cleaned up: removed unused components (MainPage, QueryInput, ProcessLog, etc.)
- Only 3 working components remain: QueryForm, ProgressLog, QueryResult
- API already supports PostDetailResponse with comments
- TypeScript types ready for posts/comments

### New UI Design (Vertical Layout)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          🔍 Experts Panel                                │
└──────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────┐ ─┐
│  Мой запрос                                   Прогресс и статистика      │  │
│ ┌─────────────────────────────┐  ┌──────────────────────────────────────│  │ 15%
│ │ [Текст вашего запроса...]   │  │ ⏳ Map [████░░░] 60%                 │  │
│ │                              │  │    или после завершения:             │  │
│ └─────────────────────────────┘  │ ✅ Постов: 850 | Время: 12.5с       │  │
│ [🔍 Найти ответ]                 └──────────────────────────────────────│ ─┘
└──────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────┐ ─┐
│  Ответ системы                                                       [▼] │  │ 40%
│  [Scrollable content with clickable post references like [123]]         │  │
└──────────────────────────────────────────────────────────────────────────┘ ─┘
┌──────────────────────────────────────────────────────────────────────────┐ ─┐
│  Оригинальные посты с комментариями                                 [▼] │  │
│  [Post cards with [+/-] toggle for comments]                            │  │ 45%
└──────────────────────────────────────────────────────────────────────────┘ ─┘
```

### Key Requirements

1. **Layout Proportions**:
   - Top section (query + progress): 15%
   - Middle section (expert response): 40%
   - Bottom section (posts with comments): 45%

2. **Functionality**:
   - Query field always visible
   - Progress/statistics toggle (same area)
   - Clickable post references [123] → scroll to post
   - Collapsible comments with [+/-] toggle
   - Posts sorted by relevance

3. **Scalability for Multi-Expert**:
   - Structure ready for expert columns (future)
   - Use arrays/maps even for single expert
   - Expert ID parametrization

## Implementation Tasks

### 1. Create New Components

#### ExpertResponse.tsx
```typescript
interface Props {
  answer: string;
  sources: number[];
  onPostClick: (postId: number) => void;
}
```
- Parse and render answer text
- Make [123] references clickable
- Handle scroll to post on click

#### PostCard.tsx
```typescript
interface Props {
  post: PostDetailResponse;
  isExpanded: boolean;
  onToggleComments: () => void;
}
```
- Display post content
- Show comment count
- Toggle comments visibility
- Render comments list when expanded

#### PostsList.tsx
```typescript
interface Props {
  posts: PostDetailResponse[];
  selectedPostId?: number;
}
```
- Manage expanded/collapsed state for each post
- Handle scroll to selected post
- Render list of PostCard components

#### ProgressSection.tsx
```typescript
interface Props {
  isProcessing: boolean;
  progressEvents: ProgressEvent[];
  stats?: QueryStats;
}
```
- Show progress bar during processing
- Switch to statistics after completion
- Compact display format

### 2. Update Existing Components

#### App.tsx
- Replace current layout with vertical sections
- Add state for selected post ID
- Add posts loading after query completion
- Handle post reference clicks

#### QueryForm.tsx
- Keep as-is but adjust styling for new layout

### 3. API Integration

- Use existing `apiClient.getPostsByIds()` to fetch posts
- Load posts after receiving QueryResponse with main_sources
- Handle loading states

### 4. State Management

```typescript
// App.tsx state
const [posts, setPosts] = useState<PostDetailResponse[]>([]);
const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
const [postsLoading, setPostsLoading] = useState(false);

// After query success:
const postDetails = await apiClient.getPostsByIds(response.main_sources);
setPosts(postDetails);
```

## Success Criteria

1. ✅ Vertical layout with correct proportions
2. ✅ Collapsible comments working smoothly
3. ✅ Clickable post references scroll to post
4. ✅ Progress/statistics toggle in same area
5. ✅ Clean code ready for multi-expert expansion

## Technical Notes

- Use inline styles (no CSS files) for consistency
- Keep components pure/functional
- Use React hooks for state
- Ensure TypeScript strict typing
- Test with mock data first

## Future Considerations

When adding multiple experts:
- Top section stays the same
- Middle and bottom sections become columns
- Each expert gets own response + posts column
- Max 3 experts visible (scroll for more)

## Work Log

### 2025-10-02

#### Completed
- Cleaned up frontend codebase: removed unused components (MainPage, QueryInput, ProcessLog, etc.)
- Fixed TypeScript bug in api.ts (SSE buffer parsing)
- Analyzed current UI structure and created comprehensive design plan
- Designed new vertical UI layout with user input (Photoshop mockup reviewed)
- Created ASCII diagrams for both single-expert and multi-expert layouts
- Defined component architecture for scalability
- Created detailed task file for implementation

#### Decisions
- Vertical layout with 15%/40%/45% proportions (query+progress / answer / posts)
- Query field always visible
- Progress and statistics toggle in the same area
- Collapsible comments with [+/-] buttons
- Clickable post references [123] scroll to corresponding post
- Posts sorted by relevance (not by date)
- Multi-expert architecture: each expert gets own column (answer + posts)
- Maximum 3 experts visible simultaneously

#### Discovered
- API already fully supports PostDetailResponse with comments array
- getPostsByIds() method ready for batch post loading
- CommentResponse interface includes all needed fields
- Current components can be cleanly replaced without breaking changes

#### Next Steps
- Create ExpertResponse component with clickable post references
- Implement PostCard component with collapsible comments
- Build PostsList component with scroll-to-post functionality
- Create ProgressSection component switching between progress/stats
- Update App.tsx with new vertical layout structure
- Test comment expansion/collapse behavior

## Context Manifest

### Essential Context
- Frontend architecture: React 18 + TypeScript
- Styling: Inline styles only (no CSS files)
- API: FastAPI backend with SSE streaming
- Current components: App, QueryForm, ProgressLog, QueryResult

### Key Files
- `frontend/src/App.tsx` - Main application
- `frontend/src/types/api.ts` - TypeScript interfaces (CommentResponse, PostDetailResponse)
- `frontend/src/services/api.ts` - API client with SSE and getPostsByIds()
- `frontend/src/components/*` - React components

### Important Decisions
- Vertical layout chosen over horizontal panels
- Comments collapsible by default
- Single expert for MVP, but architecture ready for multi-expert
- Posts sorted by relevance not date
- Arrays/maps used throughout for future multi-expert support