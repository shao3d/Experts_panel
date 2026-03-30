import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMediaQuery } from './useMediaQuery';

describe('useMediaQuery', () => {
  let listeners: ((e: MediaQueryListEvent) => void)[];

  beforeEach(() => {
    listeners = [];
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === '(min-width: 768px)',
      addEventListener: vi.fn((_event: string, handler: (e: MediaQueryListEvent) => void) => {
        listeners.push(handler);
      }),
      removeEventListener: vi.fn(),
    }));
  });

  it('returns true when media query matches initially', () => {
    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));
    expect(result.current).toBe(true);
  });

  it('returns false when media query does not match initially', () => {
    const { result } = renderHook(() => useMediaQuery('(max-width: 400px)'));
    expect(result.current).toBe(false);
  });

  it('updates when media query changes', () => {
    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));
    expect(result.current).toBe(true);

    act(() => {
      listeners.forEach(fn => fn({ matches: false } as MediaQueryListEvent));
    });
    expect(result.current).toBe(false);
  });

  it('cleans up listener on unmount', () => {
    const removeListener = vi.fn();
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: removeListener,
    });

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'));
    unmount();
    expect(removeListener).toHaveBeenCalledTimes(1);
  });
});
