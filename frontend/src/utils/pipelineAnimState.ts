import type { ProgressEvent } from '../types/api';

export type AnimState = 'walk' | 'type' | 'read' | 'idle';

type PhaseStatus = 'pending' | 'active' | 'completed' | 'skipped' | 'error';

/** Phases where characters WRITE (synthesis, composing answers) */
const TYPE_PHASES = [
  'reduce', 'comment_synthesis',
  'video_synthesis', 'meta_synthesis',
  'reddit_synthesis',
];

/** Phases where characters READ (searching, analyzing, validating) */
const READ_PHASES = [
  'scout', 'map', 'medium_scoring',
  'resolve', 'language_validation',
  'comment_groups',
  'video_map', 'video_resolve', 'video_validation',
  'reddit_search',
];

export function getLatestPipelineState(
  events: ProgressEvent[],
): Record<string, PhaseStatus> | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const ps = events[i].pipeline_state;
    if (ps) return ps as Record<string, PhaseStatus>;
  }
  return null;
}

export interface AnimMix {
  typeWeight: number;
  readWeight: number;
}

/**
 * Compute proportional animation mix from active pipeline phases.
 * Instead of winner-takes-all, returns the ratio of TYPE vs READ phases.
 */
export function getAnimMix(state: Record<string, PhaseStatus> | null): AnimMix {
  if (!state) return { typeWeight: 0, readWeight: 0 };
  const active = Object.entries(state)
    .filter(([, s]) => s === 'active')
    .map(([p]) => p);
  if (active.length === 0) return { typeWeight: 0, readWeight: 0 };
  const typeCount = active.filter(p => TYPE_PHASES.includes(p)).length;
  const readCount = active.filter(p => READ_PHASES.includes(p)).length;
  const total = typeCount + readCount || 1;
  return { typeWeight: typeCount / total, readWeight: readCount / total };
}

/** Bucket a mix into a stable key (20% increments) to avoid re-triggering on tiny changes */
export function mixToKey(mix: AnimMix): string {
  return `${Math.round(mix.typeWeight * 5)}-${Math.round(mix.readWeight * 5)}`;
}
