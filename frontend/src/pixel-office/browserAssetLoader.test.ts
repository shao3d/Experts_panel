import { describe, it, expect, vi, beforeEach } from 'vitest';
import { pngToSpriteData } from './browserAssetLoader';

function mockImageAndCanvas(pixelData: number[], width: number, height: number) {
  // Arrow functions can't be constructors — use a regular function mock
  globalThis.Image = vi.fn(function(this: Record<string, unknown>) {
    this.src = '';
    this.width = width;
    this.height = height;
    this.decode = () => Promise.resolve();
  }) as unknown as typeof Image;

  const mockCtx = {
    drawImage: vi.fn(),
    getImageData: vi.fn().mockReturnValue({
      data: new Uint8ClampedArray(pixelData),
    }),
  };

  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    mockCtx as unknown as CanvasRenderingContext2D,
  );
}

describe('pngToSpriteData', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('treats alpha=0 as transparent', async () => {
    mockImageAndCanvas([255, 0, 0, 0], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('');
  });

  it('treats alpha=1 as transparent (below threshold)', async () => {
    mockImageAndCanvas([255, 0, 0, 1], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('');
  });

  it('treats alpha=2 as transparent (AT threshold — PNG_ALPHA_THRESHOLD=2)', async () => {
    mockImageAndCanvas([255, 0, 0, 2], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('');
  });

  it('treats alpha=3 as opaque (ABOVE threshold)', async () => {
    mockImageAndCanvas([255, 0, 0, 3], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#ff0000');
  });

  it('treats alpha=255 as opaque', async () => {
    mockImageAndCanvas([0, 128, 255, 255], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#0080ff');
  });

  it('converts RGB to lowercase hex with # prefix', async () => {
    mockImageAndCanvas([255, 255, 255, 255], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#ffffff');
  });

  it('zero-pads single-digit hex values (R=0, G=0, B=10)', async () => {
    mockImageAndCanvas([0, 0, 10, 255], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#00000a');
  });

  it('handles pure black (0,0,0)', async () => {
    mockImageAndCanvas([0, 0, 0, 255], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#000000');
  });

  it('handles mid-values correctly (128, 64, 32)', async () => {
    mockImageAndCanvas([128, 64, 32, 255], 1, 1);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite[0][0]).toBe('#804020');
  });

  it('returns 2D array matching image dimensions (2×2)', async () => {
    mockImageAndCanvas([
      255, 0, 0, 255,    0, 255, 0, 255,
      0, 0, 255, 255,    0, 0, 0, 0,
    ], 2, 2);
    const sprite = await pngToSpriteData('/test.png');
    expect(sprite).toHaveLength(2);
    expect(sprite[0]).toHaveLength(2);
    expect(sprite[1]).toHaveLength(2);
    expect(sprite[0][0]).toBe('#ff0000');
    expect(sprite[0][1]).toBe('#00ff00');
    expect(sprite[1][0]).toBe('#0000ff');
    expect(sprite[1][1]).toBe('');
  });
});
