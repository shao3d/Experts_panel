import { describe, it, expect, beforeEach } from 'vitest';

class CharacterStateGuard {
  isActive = false;
  transitionDelay = 0;
  pendingActive: boolean | undefined;

  onExternalStateChange(active: boolean) {
    if (active === this.isActive && this.pendingActive === undefined) return;
    if (active === this.pendingActive) return;
    this.transitionDelay = Math.random() * 2000;
    this.pendingActive = active;
  }

  update(dt: number) {
    if (this.transitionDelay > 0) {
      this.transitionDelay -= dt * 1000;
      if (this.transitionDelay > 0) return false;
    }
    if (this.pendingActive !== undefined) {
      this.isActive = this.pendingActive;
      this.pendingActive = undefined;
      return true;
    }
    return false;
  }
}

describe('onExternalStateChange guard', () => {
  let char: CharacterStateGuard;

  beforeEach(() => {
    char = new CharacterStateGuard();
  });

  it('sets delay on first activation', () => {
    char.onExternalStateChange(true);
    expect(char.transitionDelay).toBeGreaterThan(0);
    expect(char.pendingActive).toBe(true);
  });

  it('ignores repeated call with same value (already active)', () => {
    char.isActive = true;
    char.onExternalStateChange(true);
    expect(char.transitionDelay).toBe(0);
    expect(char.pendingActive).toBeUndefined();
  });

  it('ignores repeated call when pendingActive already matches', () => {
    char.onExternalStateChange(true);
    const firstDelay = char.transitionDelay;
    char.onExternalStateChange(true);
    expect(char.transitionDelay).toBe(firstDelay);
  });

  it('accepts new value after previous pending', () => {
    char.onExternalStateChange(true);
    char.onExternalStateChange(false);
    expect(char.pendingActive).toBe(false);
    expect(char.transitionDelay).toBeGreaterThanOrEqual(0);
  });

  it('sets delay on deactivation', () => {
    char.isActive = true;
    char.onExternalStateChange(false);
    expect(char.transitionDelay).toBeGreaterThan(0);
    expect(char.pendingActive).toBe(false);
  });

  it('does not apply state during delay', () => {
    char.onExternalStateChange(true);
    char.update(0.05);
    if (char.transitionDelay > 0) {
      expect(char.isActive).toBe(false);
    }
  });

  it('applies state after delay expires', () => {
    char.onExternalStateChange(true);
    char.update(3);
    expect(char.isActive).toBe(true);
    expect(char.pendingActive).toBeUndefined();
  });

  it('clears pendingActive after applying', () => {
    char.onExternalStateChange(true);
    char.update(3);
    expect(char.pendingActive).toBeUndefined();
  });

  it('activate → wait → deactivate → wait → final state', () => {
    char.onExternalStateChange(true);
    char.update(3);
    expect(char.isActive).toBe(true);

    char.onExternalStateChange(false);
    expect(char.pendingActive).toBe(false);
    char.update(3);
    expect(char.isActive).toBe(false);
  });

  it('handles rapid true→false before delay expires', () => {
    char.onExternalStateChange(true);
    char.onExternalStateChange(false);
    char.update(3);
    expect(char.isActive).toBe(false);
  });
});
