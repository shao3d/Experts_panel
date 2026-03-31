import { describe, it, expect } from 'vitest';
import { getLatestPipelineState, getAnimMix, mixToKey } from './pipelineAnimState';
import type { ProgressEvent } from '../types/api';

// === getLatestPipelineState ===

describe('getLatestPipelineState', () => {
  it('returns null for empty events array', () => {
    expect(getLatestPipelineState([])).toBeNull();
  });

  it('returns null when no events have pipeline_state', () => {
    const events: ProgressEvent[] = [
      { event_type: 'progress', phase: 'scout', status: 'running', message: '' },
      { event_type: 'progress', phase: 'map', status: 'running', message: '' },
    ];
    expect(getLatestPipelineState(events)).toBeNull();
  });

  it('returns the LAST pipeline_state (not first)', () => {
    const events: ProgressEvent[] = [
      { event_type: 'progress', phase: 'scout', status: '', message: '',
        pipeline_state: { scout: 'active', map: 'pending' } },
      { event_type: 'progress', phase: 'map', status: '', message: '',
        pipeline_state: { scout: 'completed', map: 'active' } },
    ];
    const result = getLatestPipelineState(events);
    expect(result).toEqual({ scout: 'completed', map: 'active' });
  });

  it('skips events without pipeline_state and returns most recent one', () => {
    const events: ProgressEvent[] = [
      { event_type: 'progress', phase: 'scout', status: '', message: '',
        pipeline_state: { scout: 'active' } },
      { event_type: 'progress', phase: 'map', status: '', message: '' },
    ];
    const result = getLatestPipelineState(events);
    expect(result).toEqual({ scout: 'active' });
  });

  it('handles single event with pipeline_state', () => {
    const events: ProgressEvent[] = [
      { event_type: 'phase_start', phase: 'scout', status: '', message: '',
        pipeline_state: { scout: 'active' } },
    ];
    expect(getLatestPipelineState(events)).toEqual({ scout: 'active' });
  });
});

// === getAnimMix ===

describe('getAnimMix', () => {
  it('returns zero weights when state is null', () => {
    expect(getAnimMix(null)).toEqual({ typeWeight: 0, readWeight: 0 });
  });

  it('returns zero weights when no phases are active', () => {
    expect(getAnimMix({ scout: 'pending', map: 'pending' }))
      .toEqual({ typeWeight: 0, readWeight: 0 });
  });

  it('returns zero weights when all phases completed', () => {
    expect(getAnimMix({ scout: 'completed', reduce: 'completed' }))
      .toEqual({ typeWeight: 0, readWeight: 0 });
  });

  // READ phases (searching, analyzing, validating)
  it('returns 100% read for scout (analyzing query)', () => {
    const mix = getAnimMix({ scout: 'active' });
    expect(mix.readWeight).toBe(1);
    expect(mix.typeWeight).toBe(0);
  });

  it('returns 100% read for map (reading posts)', () => {
    const mix = getAnimMix({ map: 'active' });
    expect(mix.readWeight).toBe(1);
    expect(mix.typeWeight).toBe(0);
  });

  it('returns 100% read for medium_scoring', () => {
    const mix = getAnimMix({ medium_scoring: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  it('returns 100% read for resolve (loading context)', () => {
    const mix = getAnimMix({ resolve: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  it('returns 100% read for video_map (watching video)', () => {
    const mix = getAnimMix({ video_map: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  it('returns 100% read for reddit_search', () => {
    const mix = getAnimMix({ reddit_search: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  it('returns 100% read for language_validation (proofreading)', () => {
    const mix = getAnimMix({ language_validation: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  it('returns 100% read for comment_groups (reading discussions)', () => {
    const mix = getAnimMix({ comment_groups: 'active' });
    expect(mix.readWeight).toBe(1);
  });

  // TYPE phases (writing, synthesis)
  it('returns 100% type for reduce (writing answer)', () => {
    const mix = getAnimMix({ reduce: 'active' });
    expect(mix.typeWeight).toBe(1);
    expect(mix.readWeight).toBe(0);
  });

  it('returns 100% type for comment_synthesis (writing insights)', () => {
    const mix = getAnimMix({ comment_synthesis: 'active' });
    expect(mix.typeWeight).toBe(1);
  });

  it('returns 100% type for meta_synthesis (writing analysis)', () => {
    const mix = getAnimMix({ meta_synthesis: 'active' });
    expect(mix.typeWeight).toBe(1);
  });

  it('returns 100% type for video_synthesis', () => {
    const mix = getAnimMix({ video_synthesis: 'active' });
    expect(mix.typeWeight).toBe(1);
  });

  it('returns 100% type for reddit_synthesis', () => {
    const mix = getAnimMix({ reddit_synthesis: 'active' });
    expect(mix.typeWeight).toBe(1);
  });

  // Mixed phases (parallel pipeline)
  it('returns 50/50 when one type and one read phase active', () => {
    const mix = getAnimMix({ reduce: 'active', map: 'active' });
    expect(mix.typeWeight).toBe(0.5);
    expect(mix.readWeight).toBe(0.5);
  });

  it('returns proportional weights for multiple mixed phases', () => {
    // 1 type (reduce) + 2 read (map, scout) = 33% type, 67% read
    const mix = getAnimMix({
      reduce: 'active',
      map: 'active',
      scout: 'active',
    });
    expect(mix.typeWeight).toBeCloseTo(1 / 3);
    expect(mix.readWeight).toBeCloseTo(2 / 3);
  });

  it('ignores non-active phases in weight calculation', () => {
    const mix = getAnimMix({
      scout: 'completed',
      map: 'completed',
      reduce: 'active',
    });
    expect(mix.typeWeight).toBe(1);
    expect(mix.readWeight).toBe(0);
  });

  it('returns zero weights for unknown active phases', () => {
    expect(getAnimMix({ some_future_phase: 'active' }))
      .toEqual({ typeWeight: 0, readWeight: 0 });
  });
});

// === mixToKey ===

describe('mixToKey', () => {
  it('buckets into 20% increments', () => {
    expect(mixToKey({ typeWeight: 0, readWeight: 1 })).toBe('0-5');
    expect(mixToKey({ typeWeight: 1, readWeight: 0 })).toBe('5-0');
    expect(mixToKey({ typeWeight: 0.5, readWeight: 0.5 })).toBe('3-3');
  });

  it('returns same key for similar mixes (within bucket)', () => {
    const key1 = mixToKey({ typeWeight: 0.32, readWeight: 0.68 });
    const key2 = mixToKey({ typeWeight: 0.35, readWeight: 0.65 });
    expect(key1).toBe(key2);
  });

  it('returns different keys for significantly different mixes', () => {
    const key1 = mixToKey({ typeWeight: 0.2, readWeight: 0.8 });
    const key2 = mixToKey({ typeWeight: 0.8, readWeight: 0.2 });
    expect(key1).not.toBe(key2);
  });
});
