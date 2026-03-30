import { describe, it, expect } from 'vitest';
import { getLatestPipelineState, getAnimState, animStateToToolName } from './pipelineAnimState';
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

// === getAnimState ===

describe('getAnimState', () => {
  it('returns walk when state is null (no pipeline data yet)', () => {
    expect(getAnimState(null)).toBe('walk');
  });

  it('returns walk when no phases are active (all pending)', () => {
    expect(getAnimState({ scout: 'pending', map: 'pending' })).toBe('walk');
  });

  it('returns walk when all phases completed', () => {
    expect(getAnimState({
      scout: 'completed', map: 'completed', resolve: 'completed',
    })).toBe('walk');
  });

  it('returns walk when all phases skipped', () => {
    expect(getAnimState({
      reddit_search: 'skipped', reddit_synthesis: 'skipped',
    })).toBe('walk');
  });

  it('returns type when video_synthesis is active', () => {
    expect(getAnimState({ video_synthesis: 'active', scout: 'completed' })).toBe('type');
  });

  it('returns type when meta_synthesis is active', () => {
    expect(getAnimState({ meta_synthesis: 'active' })).toBe('type');
  });

  it('returns type when reddit_search is active', () => {
    expect(getAnimState({ reddit_search: 'active' })).toBe('type');
  });

  it('returns type when reddit_synthesis is active', () => {
    expect(getAnimState({ reddit_synthesis: 'active' })).toBe('type');
  });

  it('returns type for all video phases', () => {
    for (const phase of ['video_map', 'video_resolve', 'video_synthesis', 'video_validation']) {
      expect(getAnimState({ [phase]: 'active' })).toBe('type');
    }
  });

  it('returns read when resolve is active', () => {
    expect(getAnimState({ resolve: 'active' })).toBe('read');
  });

  it('returns read when reduce is active', () => {
    expect(getAnimState({ reduce: 'active' })).toBe('read');
  });

  it('returns read when language_validation is active', () => {
    expect(getAnimState({ language_validation: 'active' })).toBe('read');
  });

  it('returns read when comment_groups is active', () => {
    expect(getAnimState({ comment_groups: 'active' })).toBe('read');
  });

  it('returns read when comment_synthesis is active', () => {
    expect(getAnimState({ comment_synthesis: 'active' })).toBe('read');
  });

  it('returns type when both type and read phases are active', () => {
    expect(getAnimState({
      video_synthesis: 'active',
      resolve: 'active',
    })).toBe('type');
  });

  it('returns walk when active phase is not in type or read lists (e.g. scout)', () => {
    expect(getAnimState({ scout: 'active' })).toBe('walk');
  });

  it('returns walk when active phase is map', () => {
    expect(getAnimState({ map: 'active' })).toBe('walk');
  });

  it('returns walk when active phase is medium_scoring', () => {
    expect(getAnimState({ medium_scoring: 'active' })).toBe('walk');
  });

  it('returns walk when phase has error status (not active)', () => {
    expect(getAnimState({ video_synthesis: 'error' })).toBe('walk');
  });

  it('returns read when multiple read phases active simultaneously', () => {
    expect(getAnimState({
      resolve: 'active',
      comment_groups: 'active',
    })).toBe('read');
  });

  it('returns read when unknown + read phases both active (scout + resolve)', () => {
    expect(getAnimState({
      scout: 'active',
      resolve: 'active',
    })).toBe('read');
  });

  it('returns type when unknown + type phases both active (map + video_synthesis)', () => {
    expect(getAnimState({
      map: 'active',
      video_synthesis: 'active',
    })).toBe('type');
  });
});

// === animStateToToolName ===

describe('animStateToToolName', () => {
  it('maps read → Read (engine READING_TOOLS set)', () => {
    expect(animStateToToolName('read')).toBe('Read');
  });

  it('maps type → Edit', () => {
    expect(animStateToToolName('type')).toBe('Edit');
  });

  it('maps walk → Edit (default)', () => {
    expect(animStateToToolName('walk')).toBe('Edit');
  });

  it('maps idle → Edit (default)', () => {
    expect(animStateToToolName('idle')).toBe('Edit');
  });
});
