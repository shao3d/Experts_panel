# Frontend Architecture - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

React 18 + TypeScript frontend with a modern Sidebar layout, Tailwind CSS styling, and real-time multi-expert query progress tracking.

## 🛠️ Technology Stack

- **React 18** - Function components with hooks and concurrent features
- **TypeScript** - Strict mode, full type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS (v3)** - Utility-first CSS framework for responsive design and theming
- **@tailwindcss/typography** - Plugin for beautiful Markdown rendering (`prose` classes)
- **SSE (Server-Sent Events)** - Real-time progress streaming
- **React Markdown** - Markdown rendering with GFM support
- **React Hot Toast** - Notifications

## 📁 Project Structure
The frontend source code is located in `frontend/src/`:
- **`App.tsx`**: Main layout controller. Manages global state and orchestrates parallel streams (Experts, Reddit, Video).
- **`components/`**:
  - **`Sidebar.tsx`**: Left navigation panel with expert selection and search filters.
  - **`QueryForm.tsx`**: Clean input area for user queries.
  - **`ExpertAccordion.tsx`**: Specialized view for expert and video insights (🎥 icons, "Video Archive" labels).
  - **`PostCard.tsx`**: Renders Telegram posts and Video segments (YouTube deep-links via `media_metadata`).
  - **`ExpertResponse.tsx`**: Renders the AI answer with source citations.
  - **`CommunityInsightsSection.tsx`**: Reddit analysis display.
  - **`ProgressSection.tsx`**: Real-time progress bars.
- **`config/`**:
  - **`expertConfig.ts`**: Central configuration for expert groups, including the new **Knowledge Hub** (Video Hub).
- **`services/`**: API client (`api.ts`) and error handling.
- **`styles/`**: Tailwind directives in `index.css`.

## 🎯 Core Layout & UX

### Sidebar Layout (Desktop)
The application uses a responsive two-pane layout:
- **Left Sidebar**:
  - Contains **Search Options** ("Recent Only", "Search Reddit").
  - Displays **Expert Groups** (Tech, Business) with "Select All" functionality.
  - Collapsible: Shows smart **Initials Avatars** when collapsed (e.g., "AI_Arch" -> "AA").
- **Main Content**:
  - Top: Query Input and Progress.
  - Center: Scrollable list of results (Accordions).

### Mobile Experience
- Sidebar is hidden.
- Bottom Sticky Footer provides access to:
  - **Expert Selector Drawer** (includes filters).
  - **Query Input**.
- Sticky Header shows progress.

## 🔄 State Management

### Lifting State Up
Key query parameters are managed at the **App level** (`App.tsx`) to synchronize the Sidebar and Query submission:
- `selectedExperts`: Set<string>
- `useRecentOnly`: boolean
- `includeReddit`: boolean

The `Sidebar` updates these states, and `App` passes the current values to the API when `QueryForm` triggers a submit.

## 🎨 Styling Strategy (Tailwind CSS)

- **Typography**: We use `prose prose-base prose-blue` for all AI-generated content (Markdown) to ensure excellent readability.
- **Clean UI**: Removed nested "card-in-card" borders. Content sits cleanly on the background.
- **Light Theme**: The interface is designed in a modern Light mode (White/Gray/Blue).
- **Custom Scrollbars**: Thin, unobtrusive scrollbars (`.custom-scrollbar`) that match the light theme.

## 📡 Data Flow

1. **User interacts** with Sidebar (selects experts/filters).
2. **User submits** query in `QueryForm`.
3. **App.tsx** gathers state + query and calls `apiClient.submitQuery()`.
4. **SSE Stream** updates `progressEvents`.
5. **Results** populate `expertResponses` and `redditResponse`.

## 🛠️ Build and Development

```bash
# Install dependencies (ensure Tailwind packages are present)
npm install

# Start Dev Server
npm run dev

# Build for Production
npm run build
```

## 🐛 Troubleshooting

- **Tailwind Styles Missing?** Check `postcss.config.js` and `tailwind.config.js`. Ensure you are using compat build (v3) if PostCSS errors occur.
- **Scrollbars Ugly?** Check `index.css` for `.custom-scrollbar` styles.
- **Sidebar Glitches?** Ensure `isCollapsed` logic correctly toggles width classes and hides text labels.

---

**Related Documentation:**
- **Main Project**: `../CLAUDE.md`
- **Backend API**: `../backend/CLAUDE.md`
