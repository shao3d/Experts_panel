# Say Briefly Design System

Source: https://styles.refero.design/style/8b91f4c9-74e5-4925-90a3-3dd31fd5725e
API snapshot: https://styles.refero.design/api/styles/8b91f4c9-74e5-4925-90a3-3dd31fd5725e
Retrieved UTC: 2026-06-23T11:41:14Z
Original site: https://saybriefly.com

## North Star

creative agency sketchbook on cream paper

## Description

SayBriefly speaks the visual language of a creative studio's moodboard: warm cream paper, a single deep forest green that does the heavy lifting for text and primary actions, and a vivid school-bus yellow that acts as both highlight marker and playful punctuation. Type is deliberately split-personality — Bricolage Grotesque at extrabold for display headlines with positive tracking that gives the words a sticker-book chunkiness, paired with Inter's clean humanist sans for everything functional. The overall feel is approachable, hand-made, and slightly rebellious: rounded 6px corners everywhere, minimal shadows, scattered pastel accent cards that feel like sticky notes rather than UI cards. Color is rationed — green for structure, yellow for emphasis, and tiny washes of teal/pink/orange as decorative one-offs.

## Theme

- Industry: saas
- Theme: light
- Color scheme: light

## Colors

| Name | Hex | Group | Role |
| --- | --- | --- | --- |
| Forest Ink | `#1a3300` | brand | Primary text, filled CTA buttons, link text, nav borders, card borders — the structural backbone. This near-black green carries 90% of the interface weight |
| Highlighter Yellow | `#ffe95c` | brand | Text highlight wash (behind keywords in headlines), badge backgrounds, accent fills. Always reads as a marker stroke, never as a CTA |
| Cream Paper | `#fcfaf5` | neutral | Page canvas, card surfaces, nav background — the warm off-white everything sits on. Slightly yellow-shifted to feel like aged paper, not screen white |
| Pencil Gray | `#b6b6b6` | neutral | Nav and divider borders — a single mid-gray for hairlines that should recede |
| Whisper Gray | `#f1f1f1` | neutral | Muted helper text, secondary labels — disappears into the cream canvas |
| Sticky Note Teal | `#a8e5e5` | accent | Teal action color for filled buttons, selected navigation states, and focused conversion moments. |
| Sticky Note Mint | `#d5f5c2` | accent | Green action color for filled buttons, selected navigation states, and focused conversion moments |
| Sticky Note Blush | `#f6d0ff` | accent | Decorative button/card fill. Sprinkle use only |
| Terracotta | `#cb5521` | accent | Decorative card accent — warm counterpoint to the green/yellow palette |

## Typography

### Bricolage Grotesque

- role: Display headlines only. Custom variable font with positive tracking (0.04-0.05em) that makes characters feel chunky and sticker-like. This is the signature voice — never use for body or UI.
- sizes: 55px, 66px, 90px
- weight: 800
- lineHeight: 1.00-1.20
- letterSpacing: 0.04em at 55px, 0.05em at 66-90px
- substitute: Archivo Black, or Mulish 900 as fallback

### Inter

- role: Everything functional: body copy, nav, buttons, cards, subheadings. Weight 400 for body, 500-600 for labels and subheads, 700 for section headings. Clean humanist sans that lets the Bricolage display type stay loud.
- sizes: 11px, 12px, 14px, 16px, 17px, 18px, 20px, 24px, 28px, 30px, 32px, 36px, 38px, 40px, 64px
- weight: 300, 400, 500, 600, 700
- lineHeight: 1.20-1.63
- substitute: system-ui, -apple-system, Segoe UI

### Roboto Mono

- role: Micro-labels in nav, small caps-style tags, and technical metadata. Mono signals 'tool/utility' context within the otherwise rounded typographic system.
- sizes: 12px, 15px, 16px
- weight: 400
- lineHeight: 1.00-1.38
- substitute: JetBrains Mono, IBM Plex Mono

## Type Scale

| Role | Size | Line height |
| --- | ---: | ---: |
| micro | 11 | 1.3 |
| caption | 14 | 1.5 |
| body-sm | 16 | 1.5 |
| body | 18 | 1.5 |
| body-lg | 20 | 1.38 |
| subheading | 28 | 1.25 |
| heading-sm | 40 | 1.1 |
| heading | 55 | 1 |
| heading-lg | 66 | 1 |
| display | 90 | 1 |

## Spacing And Shape

- pageMaxWidth: 1200px
- sectionGap: 64px
- cardPadding: 24px
- elementGap: 16px
- radius.nav: 16px
- radius.tags: 9999px
- radius.cards: 12px
- radius.buttons: 6px

## Surfaces

| Level | Name | Hex | Purpose |
| ---: | --- | --- | --- |
| 1 | Cream Paper | `#fcfaf5` | Page canvas and nav background |
| 2 | Sticky Note Mint | `#d5f5c2` | Soft feature card surface |
| 3 | Highlighter Yellow | `#ffe95c` | Accent card or highlighted callout surface |
| 4 | Sticky Note Blush | `#f6d0ff` | Decorative card surface |
| 5 | Sticky Note Teal | `#a8e5e5` | Decorative card surface |

## Elevation Philosophy

Elevation is used so sparingly it barely exists. The system separates layers through color fill (pastel cards on cream canvas) and 1px hairline borders, not shadows. The only shadow tokens are 1-2px blurs on buttons to give them physical weight. The nav bar has one extravagant multi-layer yellow glow shadow that breaks the restraint — it's a signature flourish, not a pattern to replicate.

## Elevation

| Element | Style |
| --- | --- |
| Primary CTA Button | `rgba(0, 0, 0, 0.05) 0px 1px 2px 0px` |
| Secondary Button (hover/active) | `rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.1) 0px 1px 2px -1px` |

## Layout

Page layout is max-width 1200px centered with generous side padding. The hero is a single centered column: logo top-left in the nav, tagline badge, massive display headline (2 lines), subhead paragraph (~600px), and CTA button stack — all vertically centered with comfortable spacing (64px between blocks). Sections stack vertically without alternating dark/light bands; the cream canvas is consistent throughout. Feature sections transition to 2-column and 3-column card grids further down. The navigation sits in a floating pill-shaped container centered at the top rather than a full-width bar. The overall rhythm is spacious — sections breathe with 64-80px gaps, cards never crowd. The single visual anchor is the centered hero block; everything else is subordinate to it.

## Imagery

Imagery is minimal and hand-crafted rather than photographic. The system uses black-line sketch illustrations at reduced opacity as atmospheric background elements — abstract shapes, partial drawings, and gestural marks that feel like a designer's notebook scribbles bleeding off the page. There is no product photography, no stock imagery, no 3D renders. Decorative elements are monoline (1-2px stroke), unfilled, and deliberately imperfect. The logo mark itself is hand-drawn. Iconography in the interface is small and functional, appearing mostly in the tagline badge and form contexts. The overall image density is low — the page is text-dominant with illustration serving as texture rather than content.

## Components

### Primary CTA Button

- Role: Conversion action
- Description: Filled Forest Ink (#1a3300) background, Cream Paper (#fcfaf5) text, 6px radius, padding 19px 40px (or 12px 20px for compact). Inter 500 at 16px. Subtle shadow: rgba(0,0,0,0.05) 0px 1px 2px. Contains inline arrow glyph (→) before label.

### Outline Nav Button

- Role: Secondary nav action
- Description: Transparent fill, 1px Forest Ink border, 6px radius, padding 8px 16px. Inter 500 at 14px in Forest Ink. Used for 'Log In' in nav.

### Highlighted Word

- Role: Editorial emphasis within display text
- Description: Individual words or short phrases in a Bricolage Grotesque headline wrapped in a Highlighter Yellow (#ffe95c) background. The highlight is a rectangular wash behind the text, not a border. Creates a marker-pen effect.

### Logo Mark

- Role: Brand identity
- Description: Two-part lockup: a 40x40 square in Highlighter Yellow containing a hand-drawn 'lo' monogram in Forest Ink (rounded, slightly imperfect strokes), followed by 'SayBriefly' wordmark in Inter 700 at 20px in Forest Ink.

### Sticky Note Card

- Role: Feature or decorative surface
- Description: 12-16px radius, 24-28px padding, filled with one of the pastel accents (Mint, Blush, Teal, Terracotta) or Cream Paper. Forest Ink text. Optional 1px Forest Ink border. No shadow — the color fill does the separation work.

### Top Navigation Bar

- Role: Primary site navigation
- Description: Cream Paper background, 16px radius container (pill-shaped), 1px Pencil Gray border. Logo left, centered nav links (Inter 500, 14px), auth buttons right. Padding 8-12px vertical. Contains the unusual multi-layer yellow shadow glow that bleeds beyond the nav edges.

### Tagline Badge

- Role: Eyebrow label above headline
- Description: Small pill or rounded rectangle with a tiny icon (lightbulb/star), Highlighter Yellow background, Forest Ink text at 12-14px Inter 500. Sits centered above the display headline as a 'category marker'.

### Backed-By Logo Strip

- Role: Social proof / credibility bar
- Description: Small horizontal row of partner/funder logos in muted gray, preceded by 'Backed by:' label in Inter 400 12px. Logos sit at uniform 16-20px height. Appears below primary CTAs.

### Display Hero Headline

- Role: Page-level title
- Description: Bricolage Grotesque 800 at 66-90px, Forest Ink color, line-height 1.0, letter-spacing 0.04-0.05em. One or two words within the headline get the Highlighter Yellow background treatment.

### Subhead Paragraph

- Role: Hero supporting copy
- Description: Inter 400 at 18-20px, Forest Ink color, line-height 1.5, max-width ~600px, centered. The only place body text reaches 20px — everywhere else it sits at 16-18px.

### Reassurance Caption

- Role: Microcopy below CTA
- Description: Inter 400 at 12-14px, Whisper Gray (#f1f1f1) or Pencil Gray. Examples: 'no credit card required.' Sits 8-12px below the primary button.

### Decorative Sketch Element

- Role: Atmospheric illustration
- Description: Hand-drawn line illustrations in Forest Ink at ~30% opacity, placed as background atmosphere in hero/transition zones. Sharp 1-2px strokes, no fill, slight imperfection in line quality. Not icons — mood.

### Pastel Accent Button

- Role: Playful secondary action
- Description: Filled with one of the sticky-note pastels (Blush, Teal, Mint), Forest Ink text at 14-16px Inter 500, 6px radius. Used for demo/secondary paths where a green CTA would feel too committed.

## Do's

- Use Forest Ink (#1a3300) for all primary text, links, and CTA buttons — it is the single chromatic workhorse.
- Set display headlines in Bricolage Grotesque 800 with positive letter-spacing (0.04-0.05em); let it breathe at line-height 1.0.
- Apply Highlighter Yellow (#ffe95c) as a background wash behind individual words in headlines, not as a button fill or full surface.
- Use 6px radius for all buttons and 12-16px for cards — never mix sharp 0px corners with the rounded system.
- Set body copy at 18-20px Inter 400 with 1.5 line-height; this is a comfortable-density reading experience.
- Separate layers with color fills and 1px borders, not shadows. Shadows are reserved for the nav glow and button lift only.
- Keep the page 95% cream + forest green. Pastel accents (Mint, Blush, Teal) appear as individual card or button fills, never as large surfaces.

## Don'ts

- Don't use Bricolage Grotesque for body text, nav, buttons, or anything below 40px — its 800 weight is too heavy for small sizes.
- Don't introduce a second primary brand color. Forest Ink is the only chromatic authority; everything else is accent or neutral.
- Don't apply heavy drop shadows. The system relies on color and borders for hierarchy; box-shadows above 2px blur break the flat aesthetic.
- Don't use pure black (#000000) for text. Forest Ink is the text color — pure black should only appear as SVG fill/stroke in decorative elements.
- Don't center-align body paragraphs wider than 640px. Headlines and subheads center, but reading copy should be left-aligned or constrained.
- Don't use Highlighter Yellow as a CTA background. It reads as a marker, not an action — reserve it for text highlight washes.
- Don't combine multiple pastel accent cards in the same row. Each pastel card should be separated by cream space to maintain the sticky-note rhythm.

## Custom Sections

### Agent Prompt Guide

**Quick Color Reference**
- text: #1a3300 (Forest Ink)
- background: #fcfaf5 (Cream Paper)
- border: #b6b6b6 (Pencil Gray)
- accent: #ffe95c (Highlighter Yellow)
- muted text: #f1f1f1 (Whisper Gray)
- primary action: #1a3300 (filled action)

**3-5 Example Component Prompts**

1. Build a hero section on #fcfaf5 canvas. Centered display headline: Bricolage Grotesque 800 at 72px, #1a3300, letter-spacing 0.05em, line-height 1.0. Highlight the word 'brief' with #ffe95c background. Subhead below: Inter 400 at 18px #1a3300, line-height 1.5, max-width 580px. Primary CTA: 6px radius, #1a3300 fill, #fcfaf5 text, padding 19px 40px, Inter 500 16px with '→' glyph.

2. Build a feature card. 12px radius, 24px padding, #d5f5c2 fill, no shadow. Heading: Inter 600 at 24px #1a3300. Body: Inter 400 at 16px #1a3300 line-height 1.5. Optional 1px #1a3300 border.

3. Build the floating nav bar. 16px radius, 1px #b6b6b6 border, #fcfaf5 background, horizontal padding 12px. Logo left (40x40 #ffe95c square with 'lo' monogram + 'SayBriefly' Inter 700 20px #1a3300). Center: nav links Inter 500 14px #1a3300. Right: outline button (1px #1a3300 border, 6px radius, 8px 16px padding, Inter 500 14px #1a3300) + filled primary CTA (6px radius, #1a3300 fill, #fcfaf5 text, 8px 16px padding).

4. Build a tagline badge. Inline-flex, 4px vertical padding, 8px horizontal padding, #ffe95c background, 6px radius. Inter 500 at 12px #1a3300, with a small icon glyph (lightbulb or star) preceding the text.

5. Build a backed-by strip. Horizontal flex row, 16px gap between items, preceded by 'Backed by:' label in Inter 400 12px #b6b6b6. Partner logos at 16-20px height, displayed in single-color #b6b6b6 or #1a3300.

## Similar References

- None
- None
- None
- None

## Quick Start: CSS Variables

```css
/* Generated from Refero Say Briefly style snapshot.
   Source: https://styles.refero.design/style/8b91f4c9-74e5-4925-90a3-3dd31fd5725e
   Retrieved: 2026-06-23T11:41:14Z */
:root {
  --color-forest-ink: #1a3300; /* Primary text, filled CTA buttons, link text, nav borders, card borders — the structural backbone. This near-black green carries 90% of the interface weight */
  --color-highlighter-yellow: #ffe95c; /* Text highlight wash (behind keywords in headlines), badge backgrounds, accent fills. Always reads as a marker stroke, never as a CTA */
  --color-cream-paper: #fcfaf5; /* Page canvas, card surfaces, nav background — the warm off-white everything sits on. Slightly yellow-shifted to feel like aged paper, not screen white */
  --color-pencil-gray: #b6b6b6; /* Nav and divider borders — a single mid-gray for hairlines that should recede */
  --color-whisper-gray: #f1f1f1; /* Muted helper text, secondary labels — disappears into the cream canvas */
  --color-sticky-note-teal: #a8e5e5; /* Teal action color for filled buttons, selected navigation states, and focused conversion moments. */
  --color-sticky-note-mint: #d5f5c2; /* Green action color for filled buttons, selected navigation states, and focused conversion moments */
  --color-sticky-note-blush: #f6d0ff; /* Decorative button/card fill. Sprinkle use only */
  --color-terracotta: #cb5521; /* Decorative card accent — warm counterpoint to the green/yellow palette */

  --font-display: 'Bricolage Grotesque', 'Archivo Black', 'Mulish', sans-serif;
  --font-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'Roboto Mono', 'SFMono-Regular', Consolas, monospace;

  --space-base: 8px;
  --space-element-gap: 16px;
  --space-section-gap: 64px;
  --space-card-padding: 24px;
  --layout-page-max-width: 1200px;

  --radius-nav: 16px;
  --radius-tags: 9999px;
  --radius-cards: 12px;
  --radius-buttons: 6px;

  --shadow-cta: rgba(0, 0, 0, 0.05) 0px 1px 2px 0px;
  --shadow-secondary-active: rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.1) 0px 1px 2px -1px;
}

```

## Quick Start: Tailwind v4

```css
/* Generated from Refero Say Briefly style snapshot.
   Source: https://styles.refero.design/style/8b91f4c9-74e5-4925-90a3-3dd31fd5725e
   Retrieved: 2026-06-23T11:41:14Z */
@import "tailwindcss";

@theme {
  --color-forest-ink: #1a3300;
  --color-highlighter-yellow: #ffe95c;
  --color-cream-paper: #fcfaf5;
  --color-pencil-gray: #b6b6b6;
  --color-whisper-gray: #f1f1f1;
  --color-sticky-note-teal: #a8e5e5;
  --color-sticky-note-mint: #d5f5c2;
  --color-sticky-note-blush: #f6d0ff;
  --color-terracotta: #cb5521;

  --font-display: 'Bricolage Grotesque', 'Archivo Black', 'Mulish', sans-serif;
  --font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'Roboto Mono', 'SFMono-Regular', Consolas, monospace;

  --spacing-base: 8px;
  --spacing-element-gap: 16px;
  --spacing-section-gap: 64px;
  --spacing-card-padding: 24px;
  --container-page: 1200px;

  --radius-nav: 16px;
  --radius-tags: 9999px;
  --radius-cards: 12px;
  --radius-buttons: 6px;
}

```

## Raw Source

- Full API payload: `source/refero-style-api.json`
- Full HTML payload: `source/refero-style-page.html`
- Manifest: `source/manifest.json`

