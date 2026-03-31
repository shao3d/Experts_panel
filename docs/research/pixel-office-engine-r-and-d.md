# Pixel Office Engine — R&D Technical Reference

**Цель документа**: Исчерпывающий технический разбор движка pixel-agents для переноса пиксель-арт офиса с анимированными персонажами в произвольный веб-фронтенд. Написан по результатам глубокого исследования исходного кода [pablodelucca/pixel-agents](https://github.com/pablodelucca/pixel-agents) v1.2.0 (MIT license).

**Для кого**: AI-ассистент или разработчик, который интегрирует pixel-office в новый проект. Читай этот документ ПЕРЕД началом работы — он содержит подводные камни, которых нет в README автора.

**Дата исследования**: 2026-03-29
**Версия pixel-agents**: 1.2.0 (commit от ~2026-03-28)

---

## 1. Что это такое (в двух словах)

Pixel-agents — VS Code расширение, визуализирующее AI-агентов как пиксельных персонажей в виртуальном офисе. Под капотом: чистый **Canvas 2D** рендер (без WebGL, без game engine библиотек), ~6000 строк TypeScript, ноль npm runtime-зависимостей. Всё крутится в браузере.

Нас интересует НЕ VS Code интеграция, а **движок рендеринга офиса + система персонажей**. Это ~3200 строк чистого клиентского кода, который можно извлечь и адаптировать.

---

## 2. Архитектура движка — под капотом

### 2.1 Общая схема

```
                   ┌─────────────────────────────────────┐
                   │         OfficeCanvas.tsx             │
                   │  (React компонент с <canvas>)       │
                   │  - requestAnimationFrame loop        │
                   │  - mouse/keyboard input              │
                   │  - resize handling                   │
                   └────────────┬────────────────────────┘
                                │ каждый кадр вызывает
                   ┌────────────▼────────────────────────┐
                   │         OfficeState                  │
                   │  (God Object — центр всего)         │
                   │  - characters[]                      │
                   │  - furniture[]                       │
                   │  - tileMap (walkability)             │
                   │  - seats[]                           │
                   │  - update(deltaTime) → tick all      │
                   └────────────┬────────────────────────┘
                                │ данные для рендера
                   ┌────────────▼────────────────────────┐
                   │         Renderer                     │
                   │  1. clearRect()                      │
                   │  2. renderTileGrid() — пол + стены   │
                   │  3. renderScene() — z-sorted:        │
                   │     мебель + персонажи + стены       │
                   │  4. renderBubbles()                  │
                   └────────────────────────────────────┘
```

### 2.2 Game Loop (engine/gameLoop.ts — 35 строк)

Простейший RAF-loop с delta time:

```typescript
let lastTime = 0;
function frame(time: number) {
  const dt = Math.min((time - lastTime) / 1000, MAX_DELTA_TIME_SEC); // cap: 0.1s
  lastTime = time;
  updateFn(dt);   // OfficeState.update()
  renderFn(ctx);  // Renderer.renderFrame()
  requestAnimationFrame(frame);
}
```

**Нюанс**: `MAX_DELTA_TIME_SEC = 0.1` — если вкладка была в фоне и dt огромный, персонажи не телепортируются. Вместо этого "замёрзли" на 100ms.

### 2.3 Координатная система

- **TILE_SIZE** = 16 пикселей (нативный размер одного тайла)
- Всё в мире измеряется в пикселях нативного размера, не в тайлах
- **Zoom** (целочисленный, 1x-10x) — масштаб для отрисовки на экране
- `defaultZoom()` = `Math.max(1, Math.floor(window.devicePixelRatio))` — обычно 2x на Retina, 1x на обычных экранах
- При рисовании: `ctx.drawImage(cachedSprite, x * zoom, y * zoom)` — все координаты умножаются на zoom

**Подводный камень**: zoom ВСЕГДА целочисленный. Дробный zoom = размытие пикселей. Движок жёстко это контролирует.

### 2.4 Canvas sizing (критический нюанс)

Canvas в pixel-agents рендерит **напрямую в device pixels**. НЕ используется `ctx.scale(dpr)`:
```
canvas.width  = container.clientWidth * devicePixelRatio   // backing store
canvas.style.width  = container.clientWidth + 'px'         // CSS size
// NO ctx.scale(dpr) — рендерим напрямую
```
Zoom — отдельный целочисленный множитель поверх этого. `ResizeObserver` следит за контейнером.

### 2.5 Два файла констант (легко перепутать!)

- **`shared/assets/constants.ts`** — парсинг ассетов: `CHAR_FRAME_W=16`, `CHAR_FRAME_H=32`, `CHAR_FRAMES_PER_ROW=7`, `CHAR_COUNT=6`, `FLOOR_TILE_SIZE=16`, `WALL_PIECE_WIDTH=16`, `PNG_ALPHA_THRESHOLD=2`
- **`webview-ui/src/constants.ts`** — runtime движок: `TILE_SIZE=16`, `MAX_DELTA_TIME_SEC=0.1`, `WALK_SPEED_PX_PER_SEC=48`, `PALETTE_COUNT=6`, `CHARACTER_SITTING_OFFSET_PX=6`, `HUE_SHIFT_MIN_DEG=45`, `HUE_SHIFT_RANGE_DEG=271`, а также zoom-лимиты, camera lerp, bubble timings, wander params

При копировании в свой проект: оба файла нужны, import paths будут разные.

---

## 3. Система спрайтов — ключевая особенность

### 3.1 SpriteData — необычный формат

**Это главное отличие** от обычных 2D-движков. Спрайты хранятся НЕ как Image/HTMLImageElement, а как:

```typescript
type SpriteData = string[][];
// Пример (3x2 спрайт):
[
  ['#FF0000', '#00FF00', ''],        // ряд 0: красный, зелёный, прозрачный
  ['',        '#0000FF', '#FFFFFF']   // ряд 1: прозрачный, синий, белый
]
```

Каждый пиксель = hex-строка `'#RRGGBB'`, `'#RRGGBBAA'`, или `''` (прозрачный).

**Почему так**: Этот формат позволяет per-pixel манипуляции (colorization, hue shift) чистым JS-кодом. Обычный `drawImage` не даёт доступа к отдельным пикселям без `getImageData`.

### 3.2 SpriteCache — как это рендерится

`spriteCache.ts` (77 строк) конвертирует SpriteData в OffscreenCanvas:

```
SpriteData → для каждого пикселя ctx.fillRect(col*zoom, row*zoom, zoom, zoom) → OffscreenCanvas
```

Результат кэшируется по `WeakMap<SpriteData, HTMLCanvasElement>` per zoom level. При рисовании в главный Canvas используется быстрый `drawImage(cachedCanvas, x, y)`.

**Стоимость**: Первый рендер каждого спрайта при каждом зуме — дорогой (fillRect для каждого пикселя). Последующие — дешёвые (drawImage с кэша).

### 3.3 Оригинальный Asset Pipeline (VS Code)

```
PNG файл на диске
  → VS Code extension host читает через Node.js fs
  → pngDecoder.ts парсит через библиотеку `pngjs`
  → Конвертирует в SpriteData (string[][])
  → Отправляет в webview через vscode.postMessage()
  → Webview сохраняет через setFloorSprites() / setWallSprites() / buildDynamicCatalog()
  → При рендере spriteCache конвертирует в OffscreenCanvas
```

### 3.4 Адаптация Asset Pipeline для браузера

**Проблема**: В браузере нет `pngjs`. Нет `fs`. Нет `postMessage` от хоста.

**Решение — два варианта**:

**Вариант A: Runtime конвертация (рекомендуется)**
```typescript
async function pngToSpriteData(url: string): Promise<SpriteData> {
  const img = new Image();
  img.src = url;
  await img.decode();

  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);

  const imageData = ctx.getImageData(0, 0, img.width, img.height);
  const pixels = imageData.data; // Uint8ClampedArray [R,G,B,A, R,G,B,A, ...]

  const sprite: SpriteData = [];
  for (let y = 0; y < img.height; y++) {
    const row: string[] = [];
    for (let x = 0; x < img.width; x++) {
      const i = (y * img.width + x) * 4;
      const a = pixels[i + 3];
      if (a <= 2) { // PNG_ALPHA_THRESHOLD = 2 (совместимость с оригиналом)
        row.push('');
      } else {
        const r = pixels[i].toString(16).padStart(2, '0');
        const g = pixels[i + 1].toString(16).padStart(2, '0');
        const b = pixels[i + 2].toString(16).padStart(2, '0');
        row.push(`#${r}${g}${b}`);
      }
    }
    sprite.push(row);
  }
  return sprite;
}
```

**Плюс**: Работает с любыми PNG, не нужен build step.
**Минус**: ~5-10ms на каждый PNG при загрузке. Для ~20 ассетов = ~100-200ms. Приемлемо.

**Вариант B: Pre-baked JSON (build time)**

Сконвертировать PNG в SpriteData JSON один раз (скриптом) и шипить как `.json`:
```bash
node convert-sprites.js assets/ > sprites.json
```
**Плюс**: Нулевая runtime-стоимость.
**Минус**: JSON с hex-строками больше по размеру, чем PNG. Нужен build step.

**Рекомендация**: Вариант A для первого внедрения, вариант B для оптимизации если нужно.

---

## 4. Рендеринг офиса

### 4.1 Тайловая карта

Офис — 2D-сетка тайлов. Каждый тайл = один из:
- **VOID** (255) — пустота, ничего не рисуется
- **WALL** (0) — стена, рисуется специальным авто-тайлингом
- **FLOOR** (1-9) — пол с паттерном и HSL-колоризацией

Дефолтный офис автора: **21×22 тайла** (10 VOID + 12 видимых). Experts Panel кастомный layout: **42×15 тайлов** (2 VOID + top wall + 10 interior + 2 VOID), 4 комнаты (Kitchen, Work L, Work R, Library).

### 4.2 Пол — HSL-колоризация

9 паттернов пола (`floor_0.png` — `floor_8.png`), каждый 16×16px grayscale. Колоризация в стиле Photoshop:

```
Grayscale luminance → HSL с заданными Hue, Saturation → Brightness/Contrast adjustment
```

Параметры на тайл: `FloorColor = { h: 0-360, s: 0-100, b: -100..100, c: -100..100 }`

**Нюанс**: Колоризация полностью в `colorize.ts` (222 строки). Чистая математика, без DOM-зависимостей. Можно использовать as-is.

### 4.3 Стены — 4-bit auto-tiling

Один PNG (`wall_0.png`): 64×128px, содержит сетку 4×4 = **16 вариантов стены**.

Выбор варианта по 4-bit маске соседей:
```
bit 0 (1): сосед сверху (N)
bit 1 (2): сосед справа (E)
bit 2 (4): сосед снизу (S)
bit 3 (8): сосед слева (W)
```

Пример: стена с соседями сверху и слева = маска 1+8 = 9 → берётся вариант #9 из PNG.

Стены **16×32px** (1 тайл шириной, 2 тайла высотой) — выступают вверх от тайловой ячейки.

### 4.4 Z-Sorting — painter's algorithm

Всё, что нужно рисовать поверх пола (мебель, стены, персонажи), собирается в массив `ZDrawable[]`:

```typescript
interface ZDrawable {
  zY: number;        // координата для сортировки
  draw: () => void;  // функция отрисовки
}
```

Сортировка по `zY` (по возрастанию) = painter's algorithm. Кто ниже на экране — рисуется позже (ближе к камере).

**Точные формулы zY**:
- Мебель (общий случай): `zY = item.row * TILE_SIZE + spriteHeight` (нижний край спрайта)
- Стулья (спинкой, `orientation === 'back'`): `zY = (item.row + footprintH) * TILE_SIZE + 1` — рисуются ПЕРЕД персонажем
- Стулья (остальные): `zY = (item.row + 1) * TILE_SIZE` — ограничены, чтобы персонаж был поверх
- Предметы на столах (surface items): `zY = max(own_zY, desk_zY + 0.5)` — всегда поверх стола
- Персонажи: `zY = character.y + TILE_SIZE/2 + 0.5` (где `CHARACTER_Z_SORT_OFFSET = 0.5`)
- Outline выделенного персонажа: `zY = charZY - 0.001` — рисуется ТУЗ ЖЕ ПОД персонажем
- **Стены**: тоже участвуют в z-sort через `getWallInstances()` — конвертируются в `FurnitureInstance[]`
- Зеркальные предметы: `ctx.translate(fx + width, fy) → ctx.scale(-1, 1) → drawImage → restore`

**Подводный камень**: Z-sorting — НЕ true z-buffer. Один спрайт целиком рисуется поверх другого. Для крупной мебели (стол 48×32) это может дать артефакты, если персонаж стоит рядом. В оригинале это решено точной настройкой zY-офсетов для каждого типа мебели.

**Подводный камень 2**: Sitting offset (+6px) применяется ТОЛЬКО к draw position, НЕ к zY. Если бы сидящий персонаж имел смещённый zY, он мог бы "провалиться" за стол при сортировке.

---

## 5. Система персонажей — самая важная часть

### 5.1 Спрайт-листы

6 персонажей (`char_0.png` — `char_5.png`), каждый **112×96px**:

```
     Col 0   Col 1   Col 2   Col 3   Col 4   Col 5   Col 6
     walk1   walk2   walk3   type1   type2   read1   read2
Row0  ↓       ↓       ↓       ↓       ↓       ↓       ↓      (facing DOWN)
Row1  ↑       ↑       ↑       ↑       ↑       ↑       ↑      (facing UP)
Row2  →       →       →       →       →       →       →      (facing RIGHT)

Каждый кадр: 16×32px (16 wide, 24 sprite + 8 top padding)
LEFT = зеркальное отражение RIGHT (scaleX -1)
```

**Кадры анимации**:
- Walk: кадры 0-3 в движке (**4 кадра** ping-pong: 0→1→2→1→0..., 0.15s/кадр = цикл 0.6s). В спрайт-листе 3 уникальных кадра (0,1,2), но движок зацикливает через 4-кадровую последовательность для плавности. Если делать CSS-only: `steps(3)` даёт 0→1→2→0 (резкий jump), для ping-pong нужен `steps(4)` с кастомными keyframes.
- Type: кадры 3-4 (2 кадра, 0.3s/кадр = цикл 0.6s)
- Read: кадры 5-6 (2 кадра, 0.3s/кадр = цикл 0.6s)
- Idle: используется walk кадр 1 (стоячая поза)
- Furniture animation (PC screens): 3 кадра, 0.2s/кадр = цикл 0.6s

### 5.2 State Machine (FSM)

Три состояния в оригинале:

```
              ┌──────────────────────────┐
              │                          │
              ▼                          │
         ┌─────────┐    isActive=true   ┌─────────┐
         │  IDLE   │ ─────────────────→ │  WALK   │
         │(wander) │                    │(to seat)│
         └────┬────┘                    └────┬────┘
              │                              │
              │ random timer                 │ arrived at seat
              │ (2-20s pause,                │
              │  then pick tile,             ▼
              │  walk there,            ┌─────────┐
              │  repeat 3-6x,           │  TYPE   │
              │  return to seat,        │(seated) │
              │  rest 120-240s)         └────┬────┘
              │                              │
              └──────────────────────────────┘
                        isActive=false
```

**IDLE behaviour** (wander AI):
1. Стоит на месте 2-20 секунд (случайная пауза)
2. Выбирает случайный walkable тайл
3. BFS-pathfind до тайла
4. Идёт туда (48 px/sec)
5. Повторить 3-6 раз
6. Идёт к назначенному сиденью
7. "Отдыхает" 120-240 секунд
8. Goto 1

**TYPE behaviour**:
- Сидит на стуле (visual offset +6px по Y — сдвиг ВНИЗ, чтобы "сесть" в кресло)
- **Важно**: sitting offset влияет ТОЛЬКО на отрисовку, НЕ на zY-сортировку
- Переключается между type и read анимацией в зависимости от типа tool
- Tool mapping: Write/Edit/Bash → type, `READING_TOOLS` set (Read/Grep/Glob/WebFetch/WebSearch) → read

**WALK behaviour**:
- Следует BFS-пути (массив точек)
- Скорость: 48 px/sec (`WALK_SPEED_PX_PER_SEC`)
- Автоматически определяет направление: dx > 0 → RIGHT, dx < 0 → LEFT, dy > 0 → DOWN, dy < 0 → UP
- Прибытие: если расстояние до следующей точки < порога → перейти к следующей точке пути
- В конце пути → переход в TYPE (если active) или IDLE
- Если `isActive` становится true во время WALK → немедленный repath к назначенному сиденью

**Matrix Effect (spawn/despawn)**:
- При создании/удалении персонажа — 0.3s "Matrix-style" пиксельный дождь
- Во время эффекта FSM-обновления **заблокированы** — персонаж "заморожен"
- Персонаж удаляется из `characters` только ПОСЛЕ завершения despawn-эффекта
- Seat освобождается СРАЗУ при despawn (не ждёт анимацию)

**`isActive` flag — жизненный цикл (нюанс)**:
- `setAgentActive(id, false)` → `seatTimer = -1` (sentinel: "поворот закончен, пропустить долгий отдых")
- В FSM: seatTimer=-1 → мгновенный переход в IDLE (без 120-240s отдыха)
- `setAgentActive(id, true)` → pathfind к сиденью → TYPE
- Также триггерит `rebuildFurnitureInstances()` — PC-экраны включаются/выключаются автоматически

### 5.3 Seat Assignment

```typescript
findFreeSeat(): Seat | null {
  // 1. Собирает все тайлы с электроникой (category === 'electronics')
  // 2. Разделяет свободные сиденья на pcSeats (лицом к электронике) и otherSeats
  // 3. PC-facing проверка: сканирует AUTO_ON_FACING_DEPTH=3 тайла вперёд
  //    + AUTO_ON_SIDE_DEPTH=2 тайла в стороны на каждой глубине
  // 4. Предпочитает pcSeats (случайный выбор), fallback на otherSeats
  // 5. Если нет свободных — null (персонаж бродит)
}
```

Seat определяется из мебели: стулья (`category === 'chairs'`), каждый footprint-тайл = отдельное сиденье. Facing direction:
1. Ориентация стула (`front`→DOWN, `back`→UP, `side`→RIGHT, `left`→LEFT)
2. Если нет ориентации — проверить 4 соседних тайла на столы (`deskTiles` set)
3. Default: DOWN

**Sub-agents** (специфика pixel-agents, может не понадобиться):
- Отрицательные ID (начиная с -1, декремент)
- Спавнятся рядом с родителем на ближайшем walkable тайле
- Наследуют палитру и hue shift родителя
- Нельзя вручную переместить или переназначить

### 5.4 BFS Pathfinding (layout/tileMap.ts — 105 строк)

Стандартный BFS по 4-connected сетке:

```typescript
function findPath(start: TilePos, end: TilePos, isWalkable: (x,y) => boolean): TilePos[] {
  // BFS queue, visited set
  // Returns array of tile positions from start to end
  // Returns empty array if no path
}
```

`isWalkable(x, y)` проверяет:
- Тайл не VOID и не WALL
- Тайл не занят мебелью (проверка footprint каждого furniture)
- Исключение: `backgroundTiles` мебели walkable (верхний ряд стола)

**Подводный камень**: BFS работает в координатах тайлов, а movement — в пикселях. Конвертация: `pixelX = tileX * TILE_SIZE`, `pixelY = tileY * TILE_SIZE`. Персонаж идёт от центра одного тайла к центру следующего.

### 5.5 Палитры и hue shift

Первые 6 агентов получают уникальные персонажи (char_0 — char_5). Начиная с 7-го — повтор спрайта с HSL hue rotation:

```typescript
pickDiversePalette(): { palette: number, hueShift: number } {
  if (agentCount <= 6) return { palette: agentCount, hueShift: 0 };
  return { palette: agentCount % 6, hueShift: randomRange(45, 315) };
}
```

Hue shift применяется к SpriteData через `adjustSprite()` — меняет hue каждого пикселя.

**Точная логика `pickDiversePalette()`**: считает сколько раз каждая палитра (0-5) используется НЕ-субагентными персонажами. Выбирает из наименее использованных. Если все использованы одинаково — random. Hue shift: `45 + Math.random() * 271` = диапазон 45°-316°.

### 5.6 Hit-testing персонажей (для кликабельных сцен)

Персонаж спрайт: 16×32px, но click hit-box: `CHARACTER_HIT_HALF_WIDTH=8` × `CHARACTER_HIT_HEIGHT=24` (16×24px — исключая 8px top padding). При сидении hit-box сдвигается на `CHARACTER_SITTING_OFFSET_PX`. Если сцена интерактивная (клик по персонажу = действие), это нужно учитывать.

**Подводный камень**: Hue shift меняет ВСЕ цвета, включая кожу. Результат может выглядеть неестественно (зелёная кожа при shift 120°). Для реальных проектов рекомендуется или не использовать, или ограничить диапазон shift (20-40° для subtle tint).

---

## 6. Мебель — каталог и манифесты

### 6.1 Структура ассетов

Каждый предмет мебели — папка с PNG-файлами и `manifest.json`:

```
assets/furniture/DESK/
  ├── manifest.json
  ├── DESK_FRONT.png      (48×32px)
  └── DESK_SIDE.png       (16×64px)
```

### 6.2 Manifest формат

```json
{
  "id": "DESK",
  "name": "Desk",
  "category": "desks",
  "rotationGroups": [
    {
      "sprites": ["DESK_FRONT"],
      "dimensions": { "width": 48, "height": 32 },
      "footprint": { "cols": 3, "rows": 2 },
      "backgroundTiles": 1
    },
    {
      "sprites": ["DESK_SIDE"],
      "dimensions": { "width": 16, "height": 64 },
      "footprint": { "cols": 1, "rows": 4 },
      "backgroundTiles": 0
    }
  ]
}
```

**Ключевые поля**:
- `footprint` — сколько тайлов мебель занимает (для walkability)
- `backgroundTiles` — сколько верхних рядов footprint walkable (персонаж может "заходить" за стол)
- `rotationGroups` — варианты ориентации (front, side, back)
- `stateGroups` — варианты состояния (PC: on/off)
- `animationFrames` — кадры анимации (PC on: 3 кадра)

### 6.3 Доступные предметы (22 типа)

| Категория | Предметы |
|---|---|
| Столы | DESK, SMALL_TABLE, COFFEE_TABLE, TABLE_FRONT |
| Стулья | CUSHIONED_CHAIR, WOODEN_CHAIR, CUSHIONED_BENCH, WOODEN_BENCH |
| Электроника | PC (анимированный: 3 кадра "on") |
| Декор | PLANT, PLANT_2, LARGE_PLANT, CACTUS, POT, HANGING_PLANT |
| Стены | SMALL_PAINTING, SMALL_PAINTING_2, LARGE_PAINTING, CLOCK, WHITEBOARD |
| Хранение | BOOKSHELF, DOUBLE_BOOKSHELF |
| Прочее | BIN, COFFEE, SOFA |

### 6.4 Лицензия ассетов

Ассеты v1.1.0+ полностью open-source и включены в репозиторий. Персонажи основаны на [JIK-A-4 Metro City Free TopDown Character Pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack). MIT лицензия покрывает код И ассеты.

---

## 7. Layout — формат и дефолтный офис

### 7.1 Layout JSON

```json
{
  "version": 2,
  "gridCols": 21,
  "gridRows": 22,
  "tiles": [[...]], // 2D массив: 255=VOID, 0=WALL, 1-9=FLOOR (pattern index)
  "tileColors": { "row,col": { "h": 25, "s": 48, "b": -43, "c": -88 } },
  "wallColor": { "h": 214, "s": 30, "b": -100, "c": -55 },
  "furniture": [
    { "id": "DESK", "rotationIndex": 0, "stateIndex": 0, "col": 2, "row": 12 },
    ...
  ]
}
```

### 7.2 Дефолтный офис

- **Размер (оригинал)**: 21×22 тайлов (336×352 нативных px)
- **Размер (Experts Panel)**: 42×15 тайлов (672×240 нативных px), CONTAINER_HEIGHT=360px
- **Структура (Experts Panel)**: 4 комнаты с проходами, единая тёплая палитра (h:20-35):
  - Левая: кухня/столовая (FLOOR_3, warm beige) — обеденный стол с 6 стульями, кофемашины, диван
  - Центр-лево: рабочая зона (FLOOR_1, warm oak) — столы, PC, стулья
  - Центр-право: рабочая зона экспертов (FLOOR_2, warm cedar) — 4 рабочих места
  - Правая: библиотека (FLOOR_1, pale honey) — книжные полки, кресла
- **Предметов мебели**: 77 (включая 2 добавленных кухонных стула)
- **Рабочих мест (seats)**: ~20+ (включая кухню и библиотеку)
- **CSS scaling**: Для non-retina (dpr=1) canvas пропорционально масштабируется в контейнер через CSS. `imageRendering: pixelated` сохраняет чёткость.

---

## 8. OfficeCanvas.tsx — React-обёртка (819 строк, нуждается в переписывании)

### 8.1 Что внутри

OfficeCanvas — самый большой файл. Содержит:
- Canvas setup с ResizeObserver
- Game loop binding (startGameLoop/stopGameLoop)
- Mouse events: click (select agent, reassign seat), hover (cursor change), middle-drag (pan), right-click (walk agent to tile), wheel (zoom)
- Editor mode integration (~40% кода — можно удалить)
- Единственный VS Code вызов: `vscode.postMessage({ type: 'saveAgentSeats', seats })`

### 8.2 VS Code fallback (уже встроен!)

```typescript
// vscodeApi.ts
export const vscode = isBrowserRuntime
  ? { postMessage: (msg: unknown) => console.log('[vscode.postMessage]', msg) }
  : acquireVsCodeApi();

// runtime.ts
export const isBrowserRuntime = typeof acquireVsCodeApi !== 'undefined' ? false : true;
```

В браузере `vscode.postMessage` просто логирует в console. Движок УЖЕ работает в browser mode — просто seat assignments не персистятся (а нам и не надо).

### 8.3 Что оставить / что выкинуть при адаптации

| Оставить | Выкинуть |
|---|---|
| Canvas ref + ResizeObserver | Editor mode (isEditing, all editor handlers) |
| Game loop start/stop в useEffect | Zoom scroll (или оставить как опцию) |
| Mouse click → select agent | Middle-button panning |
| Agent hover highlight | Right-click walk-to |
| Seat click → reassign | ToolOverlay integration |
| `unlockAudio()` (Web Audio) | `vscode.postMessage` для persist |

**Ожидаемый размер после очистки**: ~300-350 строк (из 819).

### 8.4 Keyboard events

В OfficeCanvas **нет keyboard handlers** (onKeyDown/onKeyUp). Все input — mouse only. Это упрощает интеграцию.

---

## 9. Интеграция в веб-фронтенд — пошаговый гайд

### 9.1 Что копировать из pixel-agents

**Берём** (~3200 строк, 17 файлов):
```
webview-ui/src/office/
  engine/gameLoop.ts        (35)    — RAF loop
  engine/renderer.ts        (693)   — Canvas отрисовка
  engine/characters.ts      (339)   — FSM персонажей
  engine/officeState.ts     (759)   — центральное состояние
  engine/matrixEffect.ts    (139)   — spawn/despawn эффект
  sprites/spriteCache.ts    (77)    — кэш спрайтов
  sprites/spriteData.ts     (176)   — загрузка character sprites
  layout/tileMap.ts         (105)   — BFS pathfinding
  layout/furnitureCatalog.ts (401)  — каталог мебели
  layout/layoutSerializer.ts (379)  — парсинг layout JSON
  colorize.ts               (222)   — HSL-колоризация
  floorTiles.ts             (74)    — паттерны пола
  wallTiles.ts              (203)   — auto-tiling стен
  types.ts                  (193)   — типы
  toolUtils.ts              (28)    — утилиты
  *.json                    (2шт)   — bubble sprites
```

**Не берём** (~2000 строк):
```
  editor/*                  (1128)  — WYSIWYG редактор
  components/ToolOverlay.tsx (236)  — HTML overlay (VS Code specific)
  components/OfficeCanvas.tsx (819) — берём, но сильно переписываем
```

**Берём из корня проекта**:
```
  shared/assets/constants.ts (~80)  — константы (TILE_SIZE и т.д.)
```

**Ассеты** (из `webview-ui/public/assets/`):
```
  characters/char_0..5.png  (6 файлов, ~5KB каждый)
  floors/floor_0..8.png     (9 файлов, ~1KB каждый)
  walls/wall_0.png          (1 файл, ~2KB)
  furniture/*/              (~10-15 папок с PNG + manifest.json)
  default-layout-1.json     (дефолтный layout)
```

### 9.2 Что нужно переписать

**1. Asset Loader** (новый файл, ~80-100 строк)
- Заменяет VS Code host-side PNG loading
- Загружает PNG через `new Image()` → `canvas.getImageData()` → SpriteData
- Вызывает `setFloorSprites()`, `setWallSprites()`, `buildDynamicCatalog()`
- См. секцию 3.4 для реализации `pngToSpriteData()`

**2. OfficeCanvas wrapper** (новый файл, ~150-200 строк)
- React-компонент с `<canvas ref>`
- Инициализация: загрузить ассеты → создать OfficeState → запустить game loop
- Props: `{ experts, activityState, isActive }`
- Cleanup: остановить game loop в useEffect return

**3. Trigger adapter** (часть OfficeState или отдельный модуль, ~50-80 строк)
- Маппинг внешних событий → character states
- В pixel-agents: JSONL transcript → tool_use → character.isActive/toolType
- В вашем проекте: pipeline_state → animState, или API events → character actions

### 9.3 API OfficeState — точки интеграции

Для подключения к своей системе нужно знать **4 метода** OfficeState:

```typescript
// 1. Создать персонажа (вызвать для каждого эксперта/агента)
officeState.addAgent(id: string, label: string, preferredSeatId?: string);

// 2. Удалить персонажа
officeState.removeAgent(id: string);

// 3. Активировать/деактивировать (начал работать / закончил)
officeState.setAgentActive(id: string, active: boolean);

// 4. Указать тип tool (определяет type vs read анимацию)
officeState.setAgentToolType(id: string, toolName: string);
// toolName из READING_TOOLS → read animation, всё остальное → type animation
```

### 9.4 Последовательность инициализации (КРИТИЧНО)

Порядок вызовов при старте:

```
1. Загрузить PNG ассеты → pngToSpriteData() для каждого
2. setFloorSprites(floorSpriteData[])        — 9 паттернов пола
3. setWallSprites(wallSpriteData)            — 1 стена (16 вариантов в одном PNG)
4. buildDynamicCatalog(furnitureData)         — мебель: {id → {sprites, manifest}}
5. setCharacterTemplates(charSpriteData[])   — 6 персонажей
6. layout = deserializeLayout(layoutJSON)     — парсинг + миграция layout
7. officeState = new OfficeState(layout, ...)  — центральный объект
8. officeState.addAgent(...) для каждого персонажа
9. startGameLoop(officeState.update, renderer.renderFrame)
```

**Подводный камень**: Если вызвать `addAgent()` ДО `buildDynamicCatalog()`, seat assignment не найдёт стулья (каталог пуст). Порядок критичен.

**Подводный камень 2**: `pngToSpriteData()` должен использовать `PNG_ALPHA_THRESHOLD = 2`, а не `alpha === 0`. Пиксели с alpha ≤ 2 считаются прозрачными в оригинале. Исправленная проверка:
```typescript
if (a <= 2) { row.push(''); } // НЕ a === 0
```

### 9.5 Подводные камни интеграции

**Камень 1: SpriteData vs drawImage**
Если вам НЕ НУЖНА runtime-колоризация (кастомные цвета пола/стен), можно обойти SpriteData и рисовать PNG напрямую через `drawImage`. Но придётся переписать `renderer.ts` — он завязан на SpriteData → spriteCache.

**Камень 2: OfficeState — god object**
759 строк, отвечает за всё. При адаптации легко сломать. Рекомендация: НЕ рефакторить, а адаптировать минимально — заменить только вход (triggers) и выход (props/callbacks).

**Камень 3: Furniture manifest loading**
В оригинале манифесты и PNG грузятся через VS Code host. Для браузера нужно:
1. Положить PNG + manifest.json в `public/` (Vite/Webpack копирует as-is)
2. Загрузить manifest через `fetch()`, PNG через `new Image()`
3. Сконвертировать PNG в SpriteData
4. Передать в `buildDynamicCatalog()`

**Камень 4: constants.ts ссылки**
Почти каждый файл импортирует `../constants.ts` или `../../constants.ts` с разной глубиной. При копировании файлов в другую структуру папок — все пути сломаются. Проще: скопировать constants.ts в корень модуля и фикснуть импорты.

**Камень 5: React 18 vs 19**
pixel-agents использует React 19. Основные различия для нас:
- `useRef` в React 19 не требует `null` initial value — minor fix
- `use()` hook — не используется в office/ коде
- Скорее всего, адаптация = 0-2 строки

---

## 10. Проблема "армии дронов" и рандомизация

### 10.1 Почему pixel-agents выглядит живо

В оригинале каждый агент — **независимый Claude Code терминал**. Они органически десинхронизированы: один агент пишет код, другой читает файл, третий ждёт approval. Движок просто отражает реальное состояние.

### 10.2 Проблема при интеграции с внешними системами

Если ваша система имеет **единый pipeline** (все эксперты проходят одни фазы), то все персонажи переключаются одновременно. Визуально — строй роботов.

### 10.3 Решение: per-character рандомизация

Добавить в character update logic:

```typescript
// В объекте каждого персонажа:
interface CharacterExtra {
  transitionDelay: number;    // 0-3000ms — задержка перед сменой активности
  breakInterval: number;      // 8000-20000ms — как часто встаёт "размяться"
  breakDuration: number;      // 2000-5000ms — сколько длится перерыв
  breakTimer: number;         // текущий таймер до перерыва
  isOnBreak: boolean;
}

// При каждом изменении целевого состояния:
function onPipelineStateChange(character, newTargetState) {
  character.transitionDelay = Math.random() * 3000; // 0-3 секунды
}

// В update(dt) каждого персонажа:
function updateCharacter(char, dt) {
  if (char.transitionDelay > 0) {
    char.transitionDelay -= dt * 1000;
    return; // продолжаем текущую активность
  }

  // Micro-breaks: периодически встаёт из-за стола
  if (char.state === 'TYPE' && !char.isOnBreak) {
    char.breakTimer -= dt * 1000;
    if (char.breakTimer <= 0) {
      char.isOnBreak = true;
      char.breakDuration = 2000 + Math.random() * 3000;
      // Переключить в IDLE/WALK ненадолго
    }
  }

  if (char.isOnBreak) {
    char.breakDuration -= dt * 1000;
    if (char.breakDuration <= 0) {
      char.isOnBreak = false;
      char.breakTimer = 8000 + Math.random() * 12000;
      // Вернуться к работе
    }
  }
}
```

**Эффект**: Персонажи реагируют на pipeline с индивидуальной задержкой (0-3с), приходят к столам в разное время (разные расстояния), и периодически берут "перерывы". Ни один не маршируют строем.

---

## 11. Desktop vs Mobile

### 11.1 Desktop (≥768px)

- **Viewport**: 800-1600px ширина main area
- **Зум**: 3x-4x (офис 960-1280px шириной)
- **Полноценный Canvas-офис** с мебелью, ходящие персонажи, z-sorting, BFS

### 11.2 Mobile (<768px) — ОДИН персонаж, без офиса

**Принцип**: на мобилке офис бессмысленен (320px — детали не видны, мебель неразличима). Вместо этого — **один пиксельный персонаж** на белом/светлом фоне с именем. Минималистично и забавно.

**Доступные анимации из спрайт-листа**:
- **Idle**: walk кадр 1 (стоячая поза) — базовое состояние
- **Type** (кадры 3-4): персонаж печатает — для фаз Analysis/Synthesis
- **Read** (кадры 5-6): персонаж читает — для фазы Search
- **Walk** (кадры 0-2): НЕ рекомендуется — ходьба на месте без контекста выглядит тупо

**Дополнительные CSS-анимации поверх спрайта** (для живости без ходьбы):
- Subtle bounce: `@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }` — "подпрыгивание" при idle
- Scale pulse: лёгкое увеличение/уменьшение при смене фазы (transition на 0.3s)

**Реализация**: простой CSS-спрайт компонент (НЕ Canvas). Один `<div>` с `background-image` + `steps()` анимация. Один `<span>` с подписью. Триггеры от `pipeline_state` — те же, что и для desktop (walk→read→type маппинг), просто walk заменяется на idle+bounce.

**Выбор персонажа**: случайный из 6 при каждом рендере, или зафиксированный (например, char_0). Не привязан к конкретному эксперту — на мобилке это "маскот системы", а не представитель эксперта.

```tsx
const isMobile = window.matchMedia('(max-width: 768px)').matches;

{isMobile
  ? <PixelMascot pipelineState={pipelineState} isProcessing={isProcessing} />
  : <Suspense fallback={<div>Loading office...</div>}>
      <PixelOffice experts={selectedExperts} ... />
    </Suspense>
}
```

### 11.3 Объём ресурсов

| Ресурс | Размер | Mobile загрузка |
|---|---|---|
| Движок (JS gzip) | ~19 KB | НЕ грузится (lazy) |
| Furniture PNG | ~50 KB | НЕ грузится |
| Character PNG (**1 шт** для mobile) | ~5 KB | Грузится |
| PixelMascot CSS+TSX | ~2 KB | Грузится |
| **Desktop total** | **~100 KB** | — |
| **Mobile total** | **~7 KB** | — |

---

## 12. Чеклист внедрения

### Фаза 1: Подготовка (~1 час)
- [ ] Скопировать 17 файлов движка в `src/pixel-office/`
- [ ] Скопировать `constants.ts`
- [ ] Скопировать ассеты в `public/assets/`
- [ ] Фикснуть import paths

### Фаза 2: Asset Pipeline (~3 часа)
- [ ] Написать `browserAssetLoader.ts` (PNG → SpriteData)
- [ ] Загрузить и инициализировать floor/wall/furniture sprites
- [ ] Проверить рендер пустого офиса (без персонажей)

### Фаза 3: Canvas Wrapper (~2 часа)
- [ ] Написать React-компонент `PixelOffice.tsx`
- [ ] Интегрировать game loop (start/stop в useEffect)
- [ ] Фиксированный zoom (3x desktop, 2x if needed)
- [ ] Resize handling

### Фаза 4: Trigger Integration (~2 часа)
- [ ] Адаптировать OfficeState: заменить JSONL triggers на props
- [ ] Маппинг внешних событий → character states
- [ ] Добавить per-character рандомизацию (секция 9.3)

### Фаза 5: Layout (~1 час)
- [ ] Кастомный layout JSON (больше столов если нужно >6 персонажей)
- [ ] Или адаптировать дефолтный layout

### Фаза 6: Mobile — PixelMascot (~1 час)
- [ ] Компонент `PixelMascot.tsx`: один персонаж, CSS-спрайт (type/read/idle+bounce)
- [ ] Без ходьбы — idle с subtle bounce вместо walk
- [ ] Один спрайт из char_0..5.png (маскот, не привязан к эксперту)
- [ ] Триггеры от pipeline_state (те же фазы, маппинг walk→idle+bounce)
- [ ] React.lazy() для desktop PixelOffice → mobile не грузит движок

### Фаза 7: Тестирование (~2 часа)
- [ ] Desktop: визуал, z-sorting, character movement
- [ ] Mobile: CSS fallback, bundle size
- [ ] Performance: DevTools Profiler, 60fps проверка
- [ ] Edge cases: 0 экспертов, 1, 6, 18

**Общее время**: ~12 часов (полный рабочий день с хвостиком)

---

## 13. Уроки из Experts Panel (case study)

### Что мы пробовали

1. **CSS-спрайт анимация** (реализовано): 6 PNG спрайт-листов, CSS `steps()` + `background-position`, 3 состояния (walk/type/read) привязаны к pipeline_state. Работает, но статично — персонажи на месте, одинаковая анимация у всех.

2. **CSS drift** (проектировали): Добавить translateX-дрейф для "живости". Решает движение, но не решает z-sorting, мебель, обход препятствий.

3. **Canvas с минимальным движком** (оценивали): ~250-300 строк самописного кода. 80% визуала, но без BFS, z-sorting, furniture catalog.

4. **Полный движок pixel-agents** (исследовали): ~3200 строк + адаптация. 100% визуала, но требует переработки asset pipeline.

### Ключевые выводы

1. **Asset pipeline — 60% работы**. Сам движок скопировать легко. Заставить его загрузить спрайты в браузере — вот где время.

2. **"Армия дронов" — неочевидная проблема**. Pipeline-driven системы дают синхронные переключения. Per-character рандомизация обязательна.

3. **Mobile ≠ Desktop**. Canvas-офис на 320px — бессмысленная красота. Раздельный подход: Canvas-офис на desktop, один CSS-маскот на mobile (без ходьбы — idle+bounce, type, read).

4. **ROI вопрос**. Pixel-office — это polish, не feature. Для loading screen с 10-60 секунд ожидания даже простые CSS-спрайты уже лучше, чем текст "Loading...". Полный офис — вишенка на торте, а не основное блюдо.

---

*Документ подготовлен на основе исследования исходного кода pixel-agents v1.2.0, тестирования CSS-спрайт интеграции, и архитектурного анализа Canvas-подхода.*
