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
- **Vitest** - Test framework with jsdom environment (55+ tests)
- **pixel-agents engine** - Canvas-based pixel art office (ported from [pixel-agents](https://github.com/pablodelucca/pixel-agents))

## 📁 Project Structure
The frontend source code is located in `frontend/src/`:
- **`App.tsx`**: Main layout controller. Manages global state and orchestrates parallel streams (Experts, Reddit, Video).
- **`components/`**:
  - **`Sidebar.tsx`**: Left navigation panel with expert selection and search filters.
  - **`QueryForm.tsx`**: Clean input area for user queries.
  - **`ExpertAccordion.tsx`**: Specialized view for expert and video insights (🎥 icons, "Video Archive" labels).
  - **`PostCard.tsx`**: Renders Telegram posts and Video segments (YouTube deep-links via `media_metadata`).
  - **`ExpertResponse.tsx`**: Renders the AI answer with source citations.
  - **`MetaSynthesisSection.tsx`**: Cross-expert unified analysis (above expert accordions, ≥2 experts). Bilingual title: "Сводный анализ" / "Cross-Expert Analysis".
  - **`CommunityInsightsSection.tsx`**: Reddit analysis display.
  - **`ProgressSection.tsx`**: Real-time progress with **Smart Grouping** — dynamically groups backend phases (Search, Analysis, Insights, Video, Synthesis, Reddit) based on `pipeline_state` from SSE events. Phase names shown without icons; completed phases marked with ✓. Legacy fallback for old backends.
  - **`PixelOffice.tsx`**: Canvas-based animated pixel office (desktop only, ≥768px). Lazy-loaded via `React.lazy()`. 4-room layout (Kitchen, 2 Work rooms, Library) with 42×15 tile grid, warm wood-tone floor palette. Characters animate based on pipeline phase mix: **read** during search/analysis, **type** during synthesis. Animations distributed proportionally across characters with staggered transitions. Context-aware seat rotation: readers randomly go to lounge seats (kitchen/library chairs), writers stay at or return to PC desks via `ensurePCSeat()`. Sofas excluded from lounge rotation. CSS scaling fallback for non-retina displays. Wrapped in `PixelOfficeErrorBoundary` for graceful degradation.
  - **`PixelMascot.tsx`**: CSS-sprite mobile mascot (<768px). Single character with idle+bounce animation. No engine chunk downloaded on mobile.
  - **`PixelCharacter.tsx`**: CSS sprite renderer for mobile mascot. Supports walk/type/read/idle animations.
- **`pixel-office/`**: Canvas engine files (characters FSM, pathfinding, renderer, sprites, furniture catalog). Ported from [pixel-agents](https://github.com/pablodelucca/pixel-agents) with browser asset loading.
- **`utils/`**:
  - **`pipelineAnimState.ts`**: Maps pipeline phases to character animations. `getAnimMix()` returns proportional type/read weights from active phases; `mixToKey()` buckets by ~20% to avoid excessive re-triggers. Search/analysis phases → read; synthesis phases → type.
  - **`useMediaQuery.ts`**: JS-based media query hook (used instead of CSS to prevent engine chunk loading on mobile).
- **`config/`**:
  - **`expertConfig.ts`**: Central configuration for expert groups, including the new **Knowledge Hub** (Video Hub).
- **`services/`**: API client (`api.ts`) and error handling.
- **`styles/`**: Tailwind directives in `index.css`.

## 🎯 Core Layout & UX

### Sidebar Layout (Desktop)
The application uses a responsive two-pane layout:
- **Left Sidebar**:
  - Contains **Search Options** (Top to bottom: "Embs&Keys", "Recent Only", "Reddit").
  - Displays **Expert Groups** (Tech, Business) with "Select All" functionality.
  - Collapsible: Shows smart **Initials Avatars** when collapsed (e.g., "AI_Arch" -> "AA").
- **Main Content**:
  - Top: Query Input and Progress.
  - **Pixel Office** (Canvas, ~360px): Animated pixel art office with 4 rooms (Kitchen, Work L, Work R, Library) and characters at desks. Always visible, scrolls with content. Desktop only — mobile shows PixelMascot instead.
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
- `useSuperPassport`: boolean (Embs&Keys Hybrid Search toggle)
- `metaSynthesis`: string | null (Cross-expert unified analysis, populated when ≥2 experts respond)

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
4. **SSE Stream** updates `progressEvents`. Each event carries `pipeline_state` — aggregate phase statuses across all experts.
5. **ProgressSection** reads latest `pipeline_state`, groups phases into dynamic UI groups (visible/hidden based on query config).
6. **Results** populate `expertResponses`, `redditResponse`, and `metaSynthesis`.
6. **Meta-Synthesis** (if ≥2 experts) renders above expert accordions as `MetaSynthesisSection`.

## 🛠️ Build and Development

```bash
# Install dependencies (ensure Tailwind packages are present)
npm install

# Start Dev Server
npm run dev

# Build for Production
npm run build

# Run Tests
npm test          # watch mode
npm run test:run  # single run (CI)
```

## 🐛 Troubleshooting

- **Tailwind Styles Missing?** Check `postcss.config.js` and `tailwind.config.js`. Ensure you are using compat build (v3) if PostCSS errors occur.
- **Scrollbars Ugly?** Check `index.css` for `.custom-scrollbar` styles.
- **Sidebar Glitches?** Ensure `isCollapsed` logic correctly toggles width classes and hides text labels.

---

**Related Documentation:**
- **Main Project**: `../CLAUDE.md`
- **Backend API**: `../backend/CLAUDE.md`
