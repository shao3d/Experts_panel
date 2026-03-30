import type { SpriteData } from './types';
import {
  CHAR_FRAME_H,
  CHAR_FRAME_W,
  CHAR_FRAMES_PER_ROW,
  PNG_ALPHA_THRESHOLD,
  WALL_BITMASK_COUNT,
  WALL_GRID_COLS,
  WALL_PIECE_HEIGHT,
  WALL_PIECE_WIDTH,
} from './constants';
import { setFloorSprites } from './floorTiles';
import { setWallSprites } from './wallTiles';
import { setCharacterTemplates } from './sprites/spriteData';
import { buildDynamicCatalog } from './layout/furnitureCatalog';
import { deserializeLayout } from './layout/layoutSerializer';
import type { LoadedAssetData } from './layout/furnitureCatalog';
import { OfficeState } from './engine/officeState';

// ── PNG → SpriteData ─────────────────────────────────────────

export async function pngToSpriteData(url: string): Promise<SpriteData> {
  const img = new Image();
  img.src = url;
  try {
    await img.decode();
  } catch (e) {
    console.error(`[PixelOffice] Failed to decode image: ${url}`, e);
    throw e;
  }

  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  const { data } = ctx.getImageData(0, 0, img.width, img.height);

  const sprite: SpriteData = [];
  for (let y = 0; y < img.height; y++) {
    const row: string[] = [];
    for (let x = 0; x < img.width; x++) {
      const i = (y * img.width + x) * 4;
      if (data[i + 3] <= PNG_ALPHA_THRESHOLD) {
        row.push('');
      } else {
        row.push(
          '#' +
            data[i].toString(16).padStart(2, '0') +
            data[i + 1].toString(16).padStart(2, '0') +
            data[i + 2].toString(16).padStart(2, '0'),
        );
      }
    }
    sprite.push(row);
  }
  return sprite;
}

// ── Character PNG decoder ─────────────────────────────────────
// Each char PNG: 112×96 (7 frames × 3 direction rows of 16×32)

async function decodeCharacterPng(url: string): Promise<{ down: SpriteData[]; up: SpriteData[]; right: SpriteData[] }> {
  const img = new Image();
  img.src = url;
  try { await img.decode(); } catch (e) { console.error(`[PixelOffice] Failed to decode character: ${url}`, e); throw e; }

  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  const { data, width } = ctx.getImageData(0, 0, img.width, img.height);

  const dirs = ['down', 'up', 'right'] as const;
  const result: { down: SpriteData[]; up: SpriteData[]; right: SpriteData[] } = {
    down: [],
    up: [],
    right: [],
  };

  for (let dirIdx = 0; dirIdx < dirs.length; dirIdx++) {
    const dir = dirs[dirIdx];
    const rowOffsetY = dirIdx * CHAR_FRAME_H;
    const frames: SpriteData[] = [];

    for (let f = 0; f < CHAR_FRAMES_PER_ROW; f++) {
      const frameOffsetX = f * CHAR_FRAME_W;
      const sprite: SpriteData = [];
      for (let y = 0; y < CHAR_FRAME_H; y++) {
        const row: string[] = [];
        for (let x = 0; x < CHAR_FRAME_W; x++) {
          const i = ((rowOffsetY + y) * width + (frameOffsetX + x)) * 4;
          if (data[i + 3] <= PNG_ALPHA_THRESHOLD) {
            row.push('');
          } else {
            row.push(
              '#' +
                data[i].toString(16).padStart(2, '0') +
                data[i + 1].toString(16).padStart(2, '0') +
                data[i + 2].toString(16).padStart(2, '0'),
            );
          }
        }
        sprite.push(row);
      }
      frames.push(sprite);
    }
    result[dir] = frames;
  }

  return result;
}

// ── Wall PNG decoder ──────────────────────────────────────────
// wall_0.png: 64×128 (4×4 grid of 16×32 bitmask pieces)

async function decodeWallPng(url: string): Promise<SpriteData[]> {
  const img = new Image();
  img.src = url;
  try { await img.decode(); } catch (e) { console.error(`[PixelOffice] Failed to decode wall: ${url}`, e); throw e; }

  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  const { data, width } = ctx.getImageData(0, 0, img.width, img.height);

  const sprites: SpriteData[] = [];
  for (let mask = 0; mask < WALL_BITMASK_COUNT; mask++) {
    const ox = (mask % WALL_GRID_COLS) * WALL_PIECE_WIDTH;
    const oy = Math.floor(mask / WALL_GRID_COLS) * WALL_PIECE_HEIGHT;
    const sprite: SpriteData = [];
    for (let y = 0; y < WALL_PIECE_HEIGHT; y++) {
      const row: string[] = [];
      for (let x = 0; x < WALL_PIECE_WIDTH; x++) {
        const i = ((oy + y) * width + (ox + x)) * 4;
        if (data[i + 3] <= PNG_ALPHA_THRESHOLD) {
          row.push('');
        } else {
          row.push(
            '#' +
              data[i].toString(16).padStart(2, '0') +
              data[i + 1].toString(16).padStart(2, '0') +
              data[i + 2].toString(16).padStart(2, '0'),
          );
        }
      }
      sprite.push(row);
    }
    sprites.push(sprite);
  }
  return sprites;
}

// ── Manifest flattening ───────────────────────────────────────
// Recursively flatten nested manifest members into flat asset entries

interface ManifestAsset {
  type: 'asset';
  id: string;
  file: string;
  width: number;
  height: number;
  footprintW: number;
  footprintH: number;
  orientation?: string;
  state?: string;
  frame?: number;
  mirrorSide?: boolean;
}

interface ManifestGroup {
  type: 'group';
  groupType: 'rotation' | 'state' | 'animation';
  rotationScheme?: string;
  orientation?: string;
  state?: string;
  members: ManifestNode[];
}

type ManifestNode = ManifestAsset | ManifestGroup;

interface FurnitureManifest {
  id: string;
  name: string;
  category: string;
  canPlaceOnWalls: boolean;
  canPlaceOnSurfaces: boolean;
  backgroundTiles: number;
  type: 'asset' | 'group';
  file?: string;
  width?: number;
  height?: number;
  footprintW?: number;
  footprintH?: number;
  members?: ManifestNode[];
  rotationScheme?: string;
}

interface FlatAsset {
  id: string;
  label: string;
  category: string;
  file: string;
  width: number;
  height: number;
  footprintW: number;
  footprintH: number;
  isDesk: boolean;
  canPlaceOnWalls: boolean;
  canPlaceOnSurfaces?: boolean;
  backgroundTiles?: number;
  groupId?: string;
  orientation?: string;
  state?: string;
  mirrorSide?: boolean;
  rotationScheme?: string;
  animationGroup?: string;
  frame?: number;
}

interface InheritedProps {
  groupId: string;
  name: string;
  category: string;
  canPlaceOnWalls: boolean;
  canPlaceOnSurfaces: boolean;
  backgroundTiles: number;
  orientation?: string;
  state?: string;
  rotationScheme?: string;
  animationGroup?: string;
}

function flattenNode(node: ManifestNode, inherited: InheritedProps): FlatAsset[] {
  if (node.type === 'asset') {
    const a = node as ManifestAsset;
    const orientation = a.orientation ?? inherited.orientation;
    const state = a.state ?? inherited.state;
    return [{
      id: a.id,
      label: inherited.name,
      category: inherited.category,
      file: a.file,
      width: a.width,
      height: a.height,
      footprintW: a.footprintW,
      footprintH: a.footprintH,
      isDesk: inherited.category === 'desks',
      canPlaceOnWalls: inherited.canPlaceOnWalls,
      canPlaceOnSurfaces: inherited.canPlaceOnSurfaces,
      backgroundTiles: inherited.backgroundTiles,
      groupId: inherited.groupId,
      ...(orientation ? { orientation } : {}),
      ...(state ? { state } : {}),
      ...(a.mirrorSide ? { mirrorSide: true } : {}),
      ...(inherited.rotationScheme ? { rotationScheme: inherited.rotationScheme } : {}),
      ...(inherited.animationGroup ? { animationGroup: inherited.animationGroup } : {}),
      ...(a.frame !== undefined ? { frame: a.frame } : {}),
    }];
  }

  const g = node as ManifestGroup;
  const results: FlatAsset[] = [];

  for (const member of g.members) {
    const child: InheritedProps = { ...inherited };
    if (g.groupType === 'rotation' && g.rotationScheme) {
      child.rotationScheme = g.rotationScheme;
    }
    if (g.groupType === 'state') {
      if (g.orientation) child.orientation = g.orientation;
      if (g.state) child.state = g.state;
    }
    if (g.groupType === 'animation') {
      const orient = g.orientation ?? inherited.orientation ?? '';
      const st = g.state ?? inherited.state ?? '';
      child.animationGroup = `${inherited.groupId}_${orient}_${st}`.toUpperCase();
      if (g.state) child.state = g.state;
    }
    if (g.orientation && !child.orientation) child.orientation = g.orientation;
    results.push(...flattenNode(member, child));
  }
  return results;
}

function flattenManifest(manifest: FurnitureManifest): FlatAsset[] {
  const inherited: InheritedProps = {
    groupId: manifest.id,
    name: manifest.name,
    category: manifest.category,
    canPlaceOnWalls: manifest.canPlaceOnWalls,
    canPlaceOnSurfaces: manifest.canPlaceOnSurfaces,
    backgroundTiles: manifest.backgroundTiles,
    ...(manifest.rotationScheme ? { rotationScheme: manifest.rotationScheme } : {}),
  };

  if (manifest.type === 'asset') {
    return flattenNode(
      {
        type: 'asset',
        id: manifest.id,
        file: manifest.file!,
        width: manifest.width!,
        height: manifest.height!,
        footprintW: manifest.footprintW!,
        footprintH: manifest.footprintH!,
      },
      inherited,
    );
  }

  // Group: wrap members in a virtual group node
  return flattenNode(
    {
      type: 'group',
      groupType: 'rotation',
      rotationScheme: manifest.rotationScheme,
      members: manifest.members ?? [],
    },
    inherited,
  );
}

// ── Furniture loader ──────────────────────────────────────────

async function loadFurnitureItem(
  basePath: string,
  id: string,
): Promise<{ assets: FlatAsset[]; sprites: Record<string, SpriteData> }> {
  const manifestUrl = `${basePath}/furniture/${id}/manifest.json`;
  const manifestResp = await fetch(manifestUrl);
  if (!manifestResp.ok) throw new Error(`Failed to load ${manifestUrl}: ${manifestResp.status}`);
  const manifest: FurnitureManifest = await manifestResp.json();

  const assets = flattenManifest(manifest);

  // Collect unique sprite files from flattened assets
  const fileToId = new Map<string, string>();
  for (const asset of assets) {
    fileToId.set(asset.file, asset.id);
  }

  const sprites: Record<string, SpriteData> = {};
  await Promise.all(
    [...fileToId.entries()].map(async ([file, assetId]) => {
      const url = `${basePath}/furniture/${id}/${file}`;
      const sd = await pngToSpriteData(url);
      sprites[assetId] = sd;
    }),
  );

  return { assets, sprites };
}

// ── Main initializer ──────────────────────────────────────────

export async function initializeOffice(basePath: string): Promise<OfficeState> {
  try {
    // 1. Fetch furniture directory index
    const indexResp = await fetch(`${basePath}/furniture-index.json`);
    if (!indexResp.ok) throw new Error(`Failed to load ${basePath}/furniture-index.json: ${indexResp.status}`);
    const furnitureIds: string[] = await indexResp.json();

    // 2. Load all assets in parallel
    const [floorSprites, wallSprites, characters, layoutJson, ...furnitureResults] =
      await Promise.all([
        // 9 floor patterns (floor_0..8.png)
        Promise.all(
          Array.from({ length: 9 }, (_, i) =>
            pngToSpriteData(`${basePath}/floors/floor_${i}.png`),
          ),
        ),
        // Wall set from wall_0.png
        decodeWallPng(`${basePath}/walls/wall_0.png`),
        // 6 character sprites (char_0..5.png)
        Promise.all(
          Array.from({ length: 6 }, (_, i) =>
            decodeCharacterPng(`${basePath}/characters/char_${i}.png`),
          ),
        ),
        // Custom layout JSON
        fetch(`${basePath}/experts-office-layout.json`).then((r) => {
          if (!r.ok) throw new Error(`Failed to load ${basePath}/experts-office-layout.json: ${r.status}`);
          return r.text();
        }),
        // All furniture items
        ...furnitureIds.map((id) => loadFurnitureItem(basePath, id)),
      ]);

    // 3. Merge furniture catalog and sprites
    const allAssets: FlatAsset[] = [];
    const allSprites: Record<string, SpriteData> = {};
    for (const { assets, sprites } of furnitureResults) {
      allAssets.push(...assets);
      Object.assign(allSprites, sprites);
    }

    // 4. Initialize engine singletons — ORDER IS CRITICAL
    setFloorSprites(floorSprites);           // 1. Floor patterns
    setWallSprites([wallSprites]);            // 2. Wall bitmask set (array of sets)
    buildDynamicCatalog({ catalog: allAssets, sprites: allSprites } as LoadedAssetData);  // 3. Furniture
    setCharacterTemplates(characters);        // 4. Character sprites

    // 5. Parse layout and create OfficeState
    const layout = deserializeLayout(layoutJson);
    const office = new OfficeState(layout ?? undefined);

    return office;
  } catch (err) {
    throw new Error(`PixelOffice asset loading failed: ${err instanceof Error ? err.message : err}`);
  }
}
