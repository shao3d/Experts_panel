import type { ProgressEvent } from '../types/api';

export type AnimState = 'walk' | 'type' | 'read' | 'idle';

type PhaseStatus = 'pending' | 'active' | 'completed' | 'skipped' | 'error';

const TYPE_PHASES = [
  'video_map', 'video_resolve', 'video_synthesis', 'video_validation',
  'meta_synthesis', 'reddit_search', 'reddit_synthesis',
];
const READ_PHASES = [
  'resolve', 'reduce', 'language_validation',
  'comment_groups', 'comment_synthesis',
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

export function getAnimState(state: Record<string, PhaseStatus> | null): AnimState {
  if (!state) return 'walk';
  const active = Object.entries(state)
    .filter(([, s]) => s === 'active')
    .map(([p]) => p);
  if (active.length === 0) return 'walk';
  if (active.some(p => TYPE_PHASES.includes(p))) return 'type';
  if (active.some(p => READ_PHASES.includes(p))) return 'read';
  return 'walk';
}

export function animStateToToolName(anim: AnimState): string {
  return anim === 'read' ? 'Read' : 'Edit';
}
