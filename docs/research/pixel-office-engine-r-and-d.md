# Pixel Office Engine — Porting Guide

> **Назначение**: Портирование Canvas 2D pixel-office из [pixel-agents](https://github.com/pablodelucca/pixel-agents) v1.2.0 на произвольный React-фронтенд. Этот документ — для AI-агента, выполняющего перенос.
>
> **Источник**: pixel-agents (MIT license, код + ассеты). Ноль npm runtime-зависимостей.
>
> **Референсная реализация**: `frontend/src/pixel-office/` в Experts Panel.

---

## PART 1: PORTING GUIDE

---

### 1. Quick Reference

| Параметр | Значение |
|----------|----------|
| Движок | Canvas 2D, requestAnimationFrame, 60fps |
| Размер движка | 4477 строк TypeScript (17 файлов) |
| Интеграционный слой | ~310 строк (React wrapper + animation mapper + media query) |
| npm зависимости | **Ноль** |
| Копировать из | `frontend/src/pixel-office/` |
| Писать с нуля | React wrapper, animation mapper, media query hook |
| Ассеты | `frontend/public/pixel-office/` (~100 KB total) |
| Canvas zoom | Целочисленный, ≥ 3 (ОБЯЗАТЕЛЬНО, иначе размытие) |
| Canvas sizing | Фиксированный canvas size → CSS downscale в контейнер |
| API движка | 6 методов на OfficeState (число, не строка для ID) |
| Mobile | Не показывать (desktop only ≥768px, gating через JS `useMediaQuery`) |

---

### 2. Что копировать

#### 2.1 Файлы движка → `src/pixel-office/`

```
engine/gameLoop.ts              (35)    RAF loop
engine/renderer.ts              (693)   Canvas rendering pipeline
engine/characters.ts            (362)   Character FSM + animation
engine/officeState.ts           (852)   God Object — state, seats, pathfinding
engine/matrixEffect.ts          (139)   Spawn/despawn digital rain
sprites/spriteCache.ts          (77)    SpriteData → cached OffscreenCanvas
sprites/spriteData.ts           (176)   Character sprite sheet parser
sprites/bubble-permission.json         Speech bubble sprite data
sprites/bubble-waiting.json            Speech bubble sprite data
layout/tileMap.ts               (105)   BFS pathfinding (4-connected)
layout/furnitureCatalog.ts      (401)   Manifest parser, rotation/state/animation groups
layout/layoutSerializer.ts      (379)   Layout JSON → tileMap + seats + furniture
colorize.ts                     (222)   HSL colorization (Photoshop-style + adjust)
floorTiles.ts                   (74)    Floor pattern storage
wallTiles.ts                    (203)   Wall auto-tiling (4-bit bitmask)
types.ts                        (197)   All TypeScript interfaces
constants.ts                    (119)   All constants (merged from 2 original files)
toolUtils.ts                    (28)    Status → tool name mapping
browserAssetLoader.ts           (415)   Browser asset pipeline (PNG → SpriteData)
```

#### 2.2 Ассеты → `public/pixel-office/`

```
characters/char_0..5.png           6× character sprite sheets (112×96 each)
floors/floor_0..8.png              9× floor patterns (16×16 grayscale)
walls/wall_0.png                   1× wall bitmask set (64×128, 16 pieces)
furniture/*/                       30+ items (PNG + manifest.json per item)
furniture-index.json               Furniture ID list
experts-office-layout.json         Custom layout (42×15, copy or create own)
```

#### 2.3 НЕ копировать

```
editor/*                  WYSIWYG layout editor (не нужен в runtime)
components/ToolOverlay.tsx  VS Code HTML overlay
components/OfficeCanvas.tsx  VS Code React wrapper (писать свой)
```

#### 2.4 Скрипт копирования ассетов

`scripts/copy-pixel-assets.sh` — клонирует pixel-agents repo во временную папку и копирует ассеты в `public/pixel-office/`. Полезен при первичном портировании из оригинального repo.

---

### 3. Интеграционный слой — писать с нуля

#### 3.1 React Wrapper (~239 строк)

Ключевой паттерн — **5 useEffect'ов**:

```typescript
import { initializeOffice } from '../pixel-office/browserAssetLoader';
import { startGameLoop } from '../pixel-office/engine/gameLoop';
import { renderFrame } from '../pixel-office/engine/renderer';
import type { OfficeState } from '../pixel-office/engine/officeState';

interface PixelOfficeProps {
  selectedExperts: Set<string>;     // IDs агентов/экспертов
  progressEvents: ProgressEvent[];  // SSE события pipeline
  isProcessing: boolean;            // Запрос в процессе?
}

const ASSET_BASE_PATH = '/pixel-office';
const CONTAINER_HEIGHT = 360;  // px, подобрать под UI
const MAX_CHARACTERS = 10;

// String ID → stable integer (движок принимает только number!)
function expertToInt(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % 100000;
}
```

**Effect 1 — Load (once)**:
```typescript
initializeOffice(ASSET_BASE_PATH).then(office => { officeRef.current = office; });
```

**Effect 2 — Game Loop (when loaded)**:
```typescript
const dpr = window.devicePixelRatio || 1;
const zoom = Math.max(3, Math.floor(dpr) + 1);  // МИНИМУМ 3!

const gridW = office.layout.cols * 16 * zoom;
const gridH = office.layout.rows * 16 * zoom;
canvas.width = gridW;
canvas.height = gridH;

// CSS scaling в контейнер
let displayW = gridW / dpr;
let displayH = gridH / dpr;
if (displayH > CONTAINER_HEIGHT) {
  const scale = CONTAINER_HEIGHT / displayH;
  displayW *= scale;
  displayH = CONTAINER_HEIGHT;
}
canvas.style.width = displayW + 'px';
canvas.style.height = displayH + 'px';
// CSS: imageRendering: 'pixelated'

startGameLoop(canvas, {
  update: (dt) => office.update(dt),
  render: (ctx) => renderFrame(ctx, canvas.width, canvas.height,
    office.tileMap, office.furniture,
    Array.from(office.characters.values()),
    zoom, 0, 0, undefined, undefined,
    office.layout.tileColors ?? undefined,
    office.layout.cols, office.layout.rows),
});
```

**Effect 3 — Sync agents ↔ characters**:
```typescript
// СНАЧАЛА удалить ушедших (освобождает seats для новых)
for (const id of current) {
  if (!desired.includes(id)) office.removeAgent(expertToInt(id));
}
// ПОТОМ добавить новых
for (const id of desired) {
  if (!current.includes(id)) office.addAgent(expertToInt(id));
}
// Активировать/деактивировать
for (const id of desired) {
  office.setAgentActive(expertToInt(id), isProcessing);
  if (isProcessing) office.setAgentTool(expertToInt(id), 'Read');  // default
}
```

**Effect 4b — Cleanup stagger timers on unmount**

**Effect 4c — Animation mapping** (см. §4)

**Mobile gating** — JS `useMediaQuery`, не CSS:
```typescript
const isDesktop = useMediaQuery('(min-width: 768px)');
// React.lazy для code splitting: PixelOffice НЕ грузится на mobile
{isDesktop && <Suspense><PixelOffice ... /></Suspense>}
```

#### 3.2 API OfficeState — 6 методов

```typescript
// Создать персонажа (ID = number!)
addAgent(id: number, preferredPalette?: number, preferredHueShift?: number,
         preferredSeatId?: string, skipSpawnEffect?: boolean,
         folderName?: string): void

// Удалить (с Matrix despawn эффектом)
removeAgent(id: number): void

// Активировать/деактивировать (idle ↔ working)
setAgentActive(id: number, active: boolean): void

// Задать tool (определяет type vs read анимацию)
// READING_TOOLS: 'Read', 'Grep', 'Glob', 'WebFetch', 'WebSearch' → read
// Всё остальное → type
setAgentTool(id: number, tool: string | null): void

// Переместить на другое сиденье
// preferNonPC=true → lounge (кухня/библиотека), исключая sofas
// preferNonPC=false → PC desks
rotateAgentSeat(id: number, preferNonPC?: boolean): boolean

// Гарантировать PC seat (если уже за PC → no-op)
ensurePCSeat(id: number): boolean
```

Внутренние методы (не вызывать из React):
- `reassignSeat(agentId, seatId)` — конкретное сиденье
- `sendToSeat(agentId)` — вернуть к текущему сиденью

---

### 4. Anti-Drone System (pipeline → живой офис)

**Проблема**: pipeline-driven система переключает всех агентов синхронно → строй роботов.

**Решение — 3 уровня**, реализованы В REACT, а не в движке:

#### 4.1 Pipeline → Animation Weights (`pipelineAnimState.ts`, 57 строк)

```typescript
// Фазы, где персонажи ПИШУТ (synthesis)
const TYPE_PHASES = ['reduce', 'comment_synthesis', 'video_synthesis',
                     'meta_synthesis', 'reddit_synthesis'];

// Фазы, где персонажи ЧИТАЮТ (search/analysis)
const READ_PHASES = ['scout', 'map', 'medium_scoring', 'resolve',
                     'language_validation', 'comment_groups',
                     'video_map', 'video_resolve', 'video_validation',
                     'reddit_search'];

// getAnimMix(pipelineState) → { typeWeight: 0-1, readWeight: 0-1 }
// mixToKey(mix) → string bucketed to 20% steps (стабильность)
```

**Адаптация под другой проект**: Заменить списки TYPE_PHASES/READ_PHASES на свои фазы pipeline.

#### 4.2 Proportional Distribution + Stagger

```typescript
const typeSlots = Math.round(mix.typeWeight * total);

// Fisher-Yates shuffle: КТО печатает — рандомно
const indices = Array.from({ length: total }, (_, i) => i);
for (let i = indices.length - 1; i > 0; i--) {
  const j = Math.floor(Math.random() * (i + 1));
  [indices[i], indices[j]] = [indices[j], indices[i]];
}

// Каскадный stagger: 500-1200ms между переключениями
indices.forEach((originalIdx, order) => {
  const delay = order * 500 + Math.random() * 700;
  setTimeout(() => {
    const agentId = expertToInt(experts[originalIdx]);
    const toolName = order < typeSlots ? 'Edit' : 'Read';
    office.setAgentTool(agentId, toolName);
    // + seat rotation (см. ниже)
  }, delay);
});
```

#### 4.3 Seat Rotation (визуальное движение)

При смене mix:
- **Writers**: `rotateAgentSeat(id, false)` (часть) + `ensurePCSeat(id)` (остальные)
- **Readers**: `rotateAgentSeat(id, true)` → lounge seats (кухня/библиотека)
- **First mix** (начало обработки): ВСЕ readers уходят в лаунж
- **Sofas** исключены из lounge-ротации (внутри `rotateAgentSeat`)
- **mixToKey bucketing** (20%): мелкие изменения pipeline НЕ перетриггеривают пересортировку

**Результат**: При каждой смене фаз персонажи плавно, один за другим, перемещаются между PC desks и лаунж-зонами.

---

### 5. Confirmed Pitfalls

**P1: Zoom ≥ 3 обязателен.** На dpr=1 zoom=1-2 даёт смазанные пиксели. Формула: `Math.max(3, Math.floor(dpr) + 1)`. CSS downscale через `imageRendering: pixelated`.

**P2: PNG_ALPHA_THRESHOLD = 2.** В `pngToSpriteData()` прозрачность — `alpha ≤ 2`, НЕ `=== 0`. Иначе artефакты по краям спрайтов.

**P3: Init order критичен.** `buildDynamicCatalog()` ПЕРЕД `addAgent()`. Иначе seat assignment не найдёт стулья (каталог пуст). Порядок:
```
setFloorSprites → setWallSprites → buildDynamicCatalog → setCharacterTemplates → new OfficeState → addAgent
```
Всё инкапсулировано в `initializeOffice()`.

**P4: ID = number, не string.** `addAgent(id: number)`. Если агенты имеют строковые ID → хешировать через `expertToInt()`.

**P5: Constants — один файл.** Оригинал pixel-agents имеет два файла констант (`shared/assets/` + `webview-ui/src/`). В EP уже объединены в один `constants.ts` (119 строк). При копировании из EP → всё ок. При копировании из оригинала → объединить и фиксить import paths.

**P6: React 18 vs 19.** pixel-agents написан на React 19. `useRef` в React 18 требует `null` initial value. Адаптация минимальная (1-2 строки).

**P7: Sitting offset vs zY.** `CHARACTER_SITTING_OFFSET_PX = 6` применяется ТОЛЬКО к draw position, НЕ к zY-сортировке. Если поменять — персонаж "провалится" за стол.

**P8: OfficeState — god object (852 строк).** НЕ рефакторить. Адаптировать минимально — менять только вход (внешние triggers) и выход (callbacks).

**P9: Asset pipeline — 60% работы.** `browserAssetLoader.ts` — самый крупный новый файл (415 строк). Движок скопировать легко. Загрузка спрайтов в браузере — вот где время.

---

### 6. Porting Checklist

```
□ Скопировать 17+2 файлов движка в src/pixel-office/
□ Скопировать ассеты в public/pixel-office/
□ Проверить/адаптировать browserAssetLoader.ts (asset paths)
□ Написать React wrapper:
  □ initializeOffice() + startGameLoop()
  □ Canvas sizing: zoom ≥ 3 + CSS scaling
  □ Sync agents: addAgent/removeAgent/setAgentActive/setAgentTool
□ Написать animation mapper:
  □ Определить TYPE_PHASES и READ_PHASES для своего pipeline
  □ getAnimMix() → proportional distribution
  □ Fisher-Yates + stagger + seat rotation
□ Mobile gating: useMediaQuery (JS, не CSS!) + React.lazy
□ Создать или адаптировать layout JSON (формат см. §9)
□ Тест: 0, 1, 6, 10+ агентов; z-sorting; 60fps DevTools Profiler
```

---

## PART 2: ENGINE REFERENCE

> Для отладки и понимания внутренностей. Не нужен для базового портирования.

---

### 7. Architecture Overview

```
React Component (PixelOffice.tsx)
    ↓ initializeOffice()
browserAssetLoader.ts (415 lines)
    ↓ PNG → SpriteData → singletons
OfficeState (852 lines) ← God Object
    ├── characters: Map<number, Character>
    ├── furniture: FurnitureInstance[]
    ├── tileMap: TileType[][]
    ├── seats: Seat[]
    └── update(dt) → tick characters + furniture animation
        ↓
Game Loop (35 lines)
    ├── update(dt) → Character FSM + physics
    └── render(ctx) → Renderer (693 lines)
        ├── renderTileGrid() — floors + walls (bitmask auto-tiling)
        ├── renderScene() — z-sorted furniture + characters + walls
        └── renderBubbles() — speech bubbles
            ↓
        Canvas 2D (imageRendering: pixelated)
```

**Game Loop**: RAF с delta time, cap 0.1s (`MAX_DELTA_TIME_SEC`). Если вкладка в фоне — персонажи "замерзают" на 100ms, не телепортируются.

**Coordinate System**: `TILE_SIZE = 16px`. Всё в нативных пикселях, не в тайлах. Zoom — целочисленный множитель для отрисовки.

---

### 8. Sprite & Rendering System

#### SpriteData Format
```typescript
type SpriteData = string[][];  // '#RRGGBB' | '#RRGGBBAA' | '' (transparent)
```
Per-pixel hex strings. Позволяет runtime colorization/hue shift чистым JS. Рендерится через `spriteCache.ts`: SpriteData → fillRect per pixel → cached OffscreenCanvas (per zoom level).

#### Asset Pipeline (`browserAssetLoader.ts`)
```
initializeOffice(basePath: string): Promise<OfficeState>
  1. fetch(furniture-index.json)
  2. Promise.all:
     - 9 floors (PNG → SpriteData)
     - 1 wall set (PNG → 16 bitmask pieces via decodeWallPng)
     - 6 characters (PNG → decodeCharacterPng)
     - Layout JSON
     - All furniture (manifest.json + PNGs per item)
  3. Init singletons IN ORDER:
     setFloorSprites → setWallSprites → buildDynamicCatalog → setCharacterTemplates
  4. Parse layout → return new OfficeState(layout)
```

#### Floor Colorization
9 patterns (`floor_0..8.png`), 16×16 grayscale. `colorize.ts` (222 lines): grayscale → HSL с `FloorColor { h, s, b, c, colorize? }`. Два режима: Photoshop-style colorize (grayscale → fixed hue) или HSL adjust (shift original).

#### Wall Auto-Tiling
`wall_0.png` (64×128): 4×4 grid = 16 bitmask variants. Маска: N=1, E=2, S=4, W=8. Стены 16×32px (2 тайла высотой, выступают вверх).

#### Z-Sorting (painter's algorithm)
Всё поверх пола → массив `ZDrawable[]`, сортировка по `zY`:
- Мебель: `zY = row * 16 + spriteHeight`
- Back-facing стулья: `zY = (row + footprintH) * 16 + 1` (ПЕРЕД персонажем)
- Другие стулья: `zY = (row + 1) * 16` (за персонажем)
- Surface items: `zY = max(own, desk_zY + 0.5)`
- Персонажи: `zY = y + 8 + 0.5` (`CHARACTER_Z_SORT_OFFSET = 0.5`)
- Стены: через `getWallInstances()` → FurnitureInstance[]
- Зеркалирование: `translate → scale(-1,1) → drawImage → restore`

---

### 9. Layout JSON Format

```json
{
  "version": 1,
  "cols": 42,
  "rows": 15,
  "layoutRevision": 13,
  "tiles": [255, 255, 0, 0, 1, 1, ...],
  "tileColors": { "row,col": { "h": 25, "s": 48, "b": -43, "c": -88, "colorize": true } },
  "wallColor": { "h": 214, "s": 30, "b": -100, "c": -55 },
  "furniture": [
    { "id": "DESK_FRONT", "rotationIndex": 0, "stateIndex": 0, "col": 2, "row": 12 },
    ...
  ]
}
```

**tiles**: Flat array (row-major), `idx = row * cols + col`. Values: 0=WALL, 1-9=FLOOR (pattern), 255=VOID.

**tileColors**: Per-tile HSL: `colorize: true` → Photoshop-style, `false` → HSL adjust. Key: `"row,col"`.

**furniture**: Каждый item → `id` из `furniture-index.json`, `rotationIndex` (0=front, 1=side...), `stateIndex` (0=off, 1=on).

**Seat generation**: Все стулья (`category='chairs'`) → seats. Facing direction: 1) ориентация стула, 2) соседний стол, 3) DOWN. Multi-tile (sofas) → uid, uid:1, uid:2.

**Blocked tiles**: Furniture footprint → blocked (кроме `backgroundTiles` верхних рядов).

---

### 10. Character System

#### Sprite Sheets
6 персонажей (`char_0..5.png`), каждый 112×96px:
```
     Col: 0     1     2     3     4     5     6
          walk0 walk1 walk2 type0 type1 read0 read1
Row 0:    ↓     ↓     ↓     ↓     ↓     ↓     ↓     (DOWN)
Row 1:    ↑     ↑     ↑     ↑     ↑     ↑     ↑     (UP)
Row 2:    →     →     →     →     →     →     →     (RIGHT)
```
Frame: 16×32px. LEFT = зеркало RIGHT (`scaleX -1`).

**Animation frames**:
- Walk: `[0,1,2,1]` ping-pong, 0.15s/frame
- Type: `[3,4]` toggle, 0.3s/frame
- Read: `[5,6]` toggle, 0.3s/frame
- Idle: frame 1 (стоячая поза)
- Furniture (PC screens): 3 frames, 0.2s/frame

#### FSM (3 states)
```
         ┌─────────┐  isActive=true  ┌─────────┐
         │  IDLE   │ ──────────────→ │  WALK   │
         │(wander) │                 │(to seat)│
         └────┬────┘                 └────┬────┘
              │ random timer               │ arrived
              │ (2-20s pause,              ▼
              │  walk to tile,        ┌─────────┐
              │  repeat 3-6x,        │  TYPE   │
              │  return to seat,     │(seated) │
              │  rest 120-240s)      └────┬────┘
              └────────────────────────────┘
                       isActive=false
```

**IDLE**: 2-20s pause → random walkable tile → BFS pathfind → walk (48 px/sec) → repeat 3-6x → seat → rest 120-240s → loop.

**TYPE**: Seated (+6px Y visual offset, NOT zY). Tool → read or type animation. `setAgentTool('Read')` → read sprite, anything else → type sprite.

**WALK**: BFS path, 48 px/sec. Direction auto-detected. If `isActive` changes mid-walk → repath to seat.

**Active/Inactive transitions**: `setAgentActive(id, false)` → `seatTimer = -1` (sentinel: skip rest, immediate idle). `setAgentActive(id, true)` → pathfind to seat → TYPE.

**Matrix Effect**: 0.3s digital rain on spawn/despawn. Per-column stagger 0-30%. FSM frozen during effect. Seat freed immediately on despawn (не ждёт анимацию).

#### Palettes & Hue Shift
First 6 agents: palettes 0-5 (unique). 7th+: least-used palette + hue shift 45-316°. `adjustSprite()` shifts every pixel hue.

#### Seat Assignment
`findFreeSeat()`: prefer PC-facing seats (electronics within `AUTO_ON_FACING_DEPTH=3` tiles), fallback to any. `rotateAgentSeat(preferNonPC)`: PC vs lounge split, sofas excluded. `ensurePCSeat()`: alias for `rotateAgentSeat(false)`.

#### Sub-agents
Negative IDs (−1, −2...). Spawn near parent on walkable tile. Inherit palette + hue shift. Lookup: `getSubagentId(parentId, toolId)`.

---

### 11. Furniture Catalog

#### Manifest Format (`furniture/{ID}/manifest.json`)
```json
{
  "id": "DESK", "name": "Desk", "category": "desks",
  "rotationGroups": [{
    "sprites": ["DESK_FRONT"],
    "dimensions": { "width": 48, "height": 32 },
    "footprint": { "cols": 3, "rows": 2 },
    "backgroundTiles": 1
  }]
}
```

**Key fields**: `footprint` (walkability), `backgroundTiles` (top rows walkable), `rotationGroups` (front/side/back), `stateGroups` (on/off), `animationFrames` (PC: 3 frames, 0.2s).

**Virtual `:left`**: Side-facing + `mirrorSide=true` → auto-creates mirrored variant.

**Auto-state**: Active seated agent → electronics in facing direction turn ON. Check: `AUTO_ON_FACING_DEPTH=3` ahead + `AUTO_ON_SIDE_DEPTH=2` to sides.

#### Available Furniture (30+ types)

| Category | Items |
|----------|-------|
| Desks | DESK_FRONT, DESK_SIDE, SMALL_TABLE, COFFEE_TABLE, TABLE_FRONT |
| Chairs | CUSHIONED_CHAIR_*, WOODEN_CHAIR_* (front/back/side/left), CUSHIONED_BENCH, WOODEN_BENCH |
| Electronics | PC_FRONT_ON/OFF (animated: 3 frames), PC_SIDE |
| Sofas | SOFA_FRONT, SOFA_BACK, SOFA_SIDE |
| Decor | PLANT, PLANT_2, LARGE_PLANT, CACTUS, POT, HANGING_PLANT |
| Wall | SMALL_PAINTING, SMALL_PAINTING_2, LARGE_PAINTING, CLOCK, WHITEBOARD |
| Storage | BOOKSHELF, DOUBLE_BOOKSHELF |
| Other | BIN |

**License**: MIT (код + ассеты). Персонажи на основе [JIK-A-4 Metro City Pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack).

---

### 12. Constants Reference

```typescript
// Sprites
CHAR_FRAME_W = 16, CHAR_FRAME_H = 32, CHAR_FRAMES_PER_ROW = 7, CHAR_COUNT = 6
PNG_ALPHA_THRESHOLD = 2

// Grid
TILE_SIZE = 16, DEFAULT_COLS = 20, DEFAULT_ROWS = 11, MAX_COLS/ROWS = 64

// Movement
WALK_SPEED_PX_PER_SEC = 48, WALK_FRAME_DURATION_SEC = 0.15, TYPE_FRAME_DURATION_SEC = 0.3

// Wander
WANDER_PAUSE_MIN/MAX_SEC = 2/20, WANDER_MOVES_BEFORE_REST_MIN/MAX = 3/6
SEAT_REST_MIN/MAX_SEC = 120/240

// Matrix Effect
MATRIX_EFFECT_DURATION_SEC = 0.3, MATRIX_TRAIL_LENGTH = 6
MATRIX_SPRITE_COLS = 16, MATRIX_SPRITE_ROWS = 24

// Rendering
CHARACTER_SITTING_OFFSET_PX = 6, CHARACTER_Z_SORT_OFFSET = 0.5
BUBBLE_VERTICAL_OFFSET_PX = 24, BUBBLE_FADE_DURATION_SEC = 0.5

// Palettes
PALETTE_COUNT = 6, HUE_SHIFT_MIN_DEG = 45, HUE_SHIFT_RANGE_DEG = 271

// Furniture
AUTO_ON_FACING_DEPTH = 3, AUTO_ON_SIDE_DEPTH = 2
FURNITURE_ANIM_INTERVAL_SEC = 0.2

// Game
MAX_DELTA_TIME_SEC = 0.1
```
