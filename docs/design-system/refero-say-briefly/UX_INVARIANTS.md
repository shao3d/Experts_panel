# Experts Panel UI Invariants

Source of truth for the current Experts Panel UI shell and future visual work.
These rules come from the accepted product framing in chat on 2026-06-23 and
the first deployed redesign pass on the same date.

## Design Goal

Experts Panel should remain a working cockpit interface:

- left side: expert and search controls;
- top: query launch and processing status;
- center/top content: pixel office scene;
- results: equal working columns for expert answer and source evidence;
- visual language: Refero Say Briefly paper/sketchbook style.

The redesign should make the interface warmer, clearer, and more branded without turning it into a landing page or changing the product mechanics.

## Hard UX Invariants

- Do not redesign the pixel office scene, pixel characters, pixel assets, or pixel-office runtime.
- Keep the left sidebar as the primary desktop expert/search control surface.
- Keep the sidebar collapse/expand behavior.
- Keep the current sidebar width logic approximately intact: expanded around 280-304px, collapsed around 64px.
- Keep desktop result columns as a balanced two-panel reading surface.
- Treat the answer column and the source-posts/comments column as equally important.
- Preserve the right column as the source evidence column.
- Preserve the source-link overflow fix: long links and markdown content must wrap within the column.
- Preserve mobile query/footer/drawer behavior on the first redesign pass.
- Do not move the mobile query composer or expert drawer without a separate product decision.

## Desktop Results Layout

Default target: 50/50 columns.

Implementation can use flexible CSS such as `minmax(0, 1fr) minmax(0, 1fr)`, but the user-facing result should still read as two equal work panels:

- left: expert response and synthesis;
- right: source posts, source comments, relevant comment groups.

Avoid making the answer column significantly wider by default. The evidence column is not secondary.

## Top Query Deck

Use a collapsible top panel pattern.

Product name: `Collapsible Query Deck`.

States:

- `expanded`: full query textarea, single action button, full progress/statistics area, and a thin collapse handle below the whole deck;
- `compact`: a thin top strip that keeps query context and status while freeing vertical space for results.

Current desktop behavior:

- Default to `expanded` before the first query.
- Do not collapse immediately on query submit; keep the deck stable while the query is starting.
- Automatically collapse to `compact` only after processing completes successfully.
- Keep the deck expanded on error so the user can correct or restart.
- Keep the deck compact while the user is reading results.
- Allow one-click expansion from the compact strip.
- Allow manual collapse from the expanded state through the long lower handle.
- Do not fully hide the panel.
- Do not overlay results with a floating panel as the primary behavior; reclaim real layout height.

Recommended sizing:

- expanded height: close to current top section, about 150-170px;
- compact height: about 44-56px.

Expanded deck layout:

- left query textarea/card and right progress/statistics card must be equal-width work surfaces on desktop;
- the central action column should stay narrow and stable: `120px` desktop, `112px` at the current tablet/mobile breakpoint;
- left and right gaps around the action button should stay equal;
- the action button is a single button: `Ask` when idle, `Stop` while processing;
- `Stop` aborts the active query, clears the draft query, and returns the system to an expanded ready state;
- do not reintroduce inline `Edit` / `New` buttons in the action column without a separate product decision;
- the expanded collapse affordance is a long thin button under the whole top deck, using the same double-chevron SVG as the sidebar, rotated upward;
- the collapse handle must not shift the left input, action button, or right progress card when it appears.

Compact strip should include:

- an expand/collapse affordance;
- one-line current query summary with ellipsis;
- processing phase or result statistics;
- no separate `Edit` / `New` actions in the first deployed pass.

## Sidebar

Keep current information architecture:

- application title/identity at top;
- search options near top;
- grouped expert list below;
- footer/status at bottom;
- collapsed rail with icons/initials.

The redesign may change visual styling, colors, surfaces, typography, borders, and selected states. It must not remove group toggles, expert toggles, external Telegram links, or collapsed mode.

## Mobile

First pass should be conservative:

- keep top mobile progress/header behavior;
- keep bottom query composer;
- keep expert selector drawer;
- keep source toggle behavior inside expert accordions;
- apply visual system only after preserving the current mechanics.

Future pass may consider a mobile compact composer, but only after separate review.

## Visual Redesign Scope

Allowed:

- introduce CSS variables from the Refero Say Briefly snapshot;
- move from gray/blue enterprise styling to cream paper, forest ink, highlighter yellow, and controlled sticky-note accents;
- update borders, radii, focus states, selected states, empty/error states, cards, buttons, badges, and markdown surfaces;
- gradually replace inline styles that block consistent theming.

Not allowed without separate approval:

- changing product flow;
- changing column meaning;
- hiding source evidence;
- removing sidebar collapse;
- turning the app into a marketing/landing-page layout;
- upgrading Tailwind major version solely for the redesign;
- redesigning pixel-office visuals.

## Implementation Order

Recommended sequence:

1. Add app-level design tokens and base surfaces.
2. Redesign desktop shell: sidebar, top query deck, progress/statistics, empty/error states. Done in first pass.
3. Implement `Collapsible Query Deck`. Done in first pass.
4. Redesign result panels while preserving 50/50 structure. Done in first pass.
5. Migrate source/evidence components away from blocking inline styles. Done for the known long-link overflow issue; keep watching source/evidence surfaces.
6. Apply conservative mobile styling with existing mechanics.
7. Verify desktop and mobile screenshots or DOM layout metrics.

## Verification Checklist

- Sidebar expands and collapses.
- Expanded and compact top query deck both work.
- Query can be submitted from the expected state.
- `Ask` turns into `Stop` during processing.
- `Stop` aborts the active query and clears the input.
- The expanded deck has no `Edit` / `New` action buttons.
- The lower collapse handle points upward and does not cause horizontal layout shift.
- Results retain balanced answer/source columns.
- Long links and long markdown tokens do not create horizontal page scroll.
- Pixel office scene still renders and is visually unchanged.
- Mobile footer, expert drawer, and source toggle still work.
- `npm run type-check`, `npm run test:run`, and `npm run build` pass before closing implementation work.
