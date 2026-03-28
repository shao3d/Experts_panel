import React from 'react';
import { ProgressEvent } from '../types/api';

interface ProgressSectionProps {
  isProcessing: boolean;
  progressEvents: ProgressEvent[];
  stats?: {
    totalPosts: number;
    processingTime: number;
    expertCount?: number;
  };
}

type PhaseStatus = 'pending' | 'active' | 'completed' | 'skipped' | 'error';

// Smart Grouping: maps backend phases to UI groups
const PIPELINE_GROUPS = [
  { id: 'search', label: 'Search', icon: '🔍',
    phases: ['scout', 'map', 'medium_scoring'] },
  { id: 'analysis', label: 'Analysis', icon: '🔗',
    phases: ['resolve', 'reduce', 'language_validation'] },
  { id: 'insights', label: 'Insights', icon: '💬',
    phases: ['comment_groups', 'comment_synthesis'] },
  { id: 'video', label: 'Video', icon: '🎥',
    phases: ['video_map', 'video_resolve', 'video_synthesis', 'video_validation'] },
  { id: 'meta', label: 'Synthesis', icon: '🧠',
    phases: ['meta_synthesis'] },
  { id: 'reddit', label: 'Reddit', icon: '🌐',
    phases: ['reddit_search', 'reddit_synthesis'] },
];

// Sub-phase messages for the status text
const PHASE_MESSAGES: Record<string, string> = {
  'scout': 'AI Scout searching...',
  'map': 'Scoring post relevance...',
  'medium_scoring': 'Reranking candidates...',
  'resolve': 'Expanding context...',
  'reduce': 'Generating answers...',
  'language_validation': 'Validating language...',
  'comment_groups': 'Finding discussions...',
  'comment_synthesis': 'Extracting insights...',
  'video_map': 'Scoring video segments...',
  'video_resolve': 'Expanding video threads...',
  'video_synthesis': 'Digital twin synthesis...',
  'video_validation': 'Style translation...',
  'meta_synthesis': 'Cross-expert analysis...',
  'reddit_search': 'Searching Reddit...',
  'reddit_synthesis': 'Analyzing discussions...',
};

// Legacy phase messages (for old backends without pipeline_state)
const LEGACY_PHASE_MESSAGES: Record<string, string> = {
  'map': 'Searching relevant posts...',
  'resolve': 'Analyzing connections...',
  'reduce': 'Generating answers...',
  'comment_groups': 'Finding discussions...',
  'final_results': 'Finishing up...',
};

const ProgressSection: React.FC<ProgressSectionProps> = ({ isProcessing, progressEvents, stats }) => {

  // --- Smart Grouping (new pipeline_state-based logic) ---

  // Find the latest event with pipeline_state (walk backward)
  const getLatestPipelineState = (): Record<string, PhaseStatus> | null => {
    for (let i = progressEvents.length - 1; i >= 0; i--) {
      if (progressEvents[i].pipeline_state) {
        return progressEvents[i].pipeline_state as Record<string, PhaseStatus>;
      }
    }
    return null;
  };

  const latestState = getLatestPipelineState();

  // Compute visible groups and their statuses from pipeline_state
  const getVisibleGroups = () => {
    if (!latestState) return [];

    return PIPELINE_GROUPS
      .filter(g => g.phases.some(p => p in latestState))
      .map(g => {
        const statuses = g.phases
          .filter(p => p in latestState)
          .map(p => latestState[p]);

        const hasActive = statuses.some(s => s === 'active');
        const allDone = statuses.every(s => s === 'completed' || s === 'skipped');
        const hasCompleted = statuses.some(s => s === 'completed' || s === 'skipped');
        const hasPending = statuses.some(s => s === 'pending');
        const hasError = statuses.some(s => s === 'error');

        let status: PhaseStatus;
        if (hasActive || (hasCompleted && hasPending)) status = 'active';
        else if (allDone) status = 'completed';
        else if (hasError) status = 'error';
        else status = 'pending';

        return { ...g, status };
      });
  };

  // Find active sub-phase message for status text
  const getActivePhaseMessageNew = (): string | null => {
    if (!latestState) return null;
    for (const group of PIPELINE_GROUPS) {
      for (const phase of group.phases) {
        if (latestState[phase] === 'active') {
          return PHASE_MESSAGES[phase] || 'Processing...';
        }
      }
    }
    return null;
  };

  const visibleGroups = getVisibleGroups();
  // Only fall back to legacy after receiving several events without pipeline_state
  // (prevents 1-frame flicker between "start" event and first event with state)
  const useLegacy = visibleGroups.length === 0 && progressEvents.length > 3;

  // --- Legacy logic (for backends without pipeline_state) ---

  const legacyPhases = [
    { name: 'map', label: 'Map', icon: '🔍' },
    { name: 'resolve', label: 'Resolve', icon: '🔗' },
    { name: 'reduce', label: 'Reduce', icon: '⚡' },
    { name: 'comment_groups', label: 'Comments', icon: '💬' },
    { name: 'final_results', label: 'Final', icon: '🎯' }
  ];

  const getLegacyPhaseStatus = (phaseName: string): PhaseStatus => {
    if (phaseName === 'resolve') {
      const resolveEvents = progressEvents.filter(e => e.phase === 'resolve');
      const scoringEvents = progressEvents.filter(e => e.phase === 'medium_scoring');
      if (resolveEvents.length > 0 || scoringEvents.length > 0) {
        const lastResolve = resolveEvents[resolveEvents.length - 1];
        const lastScoring = scoringEvents[scoringEvents.length - 1];
        const resolveActive = lastResolve?.status !== 'completed';
        const scoringActive = lastScoring?.status !== 'completed';
        if (resolveActive || scoringActive) return 'active';
        return 'completed';
      }
      return 'pending';
    }
    if (phaseName === 'final_results') {
      if (!isProcessing) {
        const otherPhases = legacyPhases.filter(p => p.name !== 'final_results');
        const allCompleted = otherPhases.every(p => getLegacyPhaseStatus(p.name) === 'completed');
        return allCompleted ? 'completed' : 'pending';
      }
      const otherPhases = legacyPhases.filter(p => p.name !== 'final_results');
      const allCompleted = otherPhases.every(p => getLegacyPhaseStatus(p.name) === 'completed');
      return allCompleted ? 'active' : 'pending';
    }
    const phaseEvents = progressEvents.filter(e => e.phase === phaseName);
    if (phaseEvents.length === 0) return 'pending';
    const lastEvent = phaseEvents[phaseEvents.length - 1];
    if (lastEvent.event_type === 'phase_complete' || lastEvent.status === 'completed') {
      return 'completed';
    }
    return 'active';
  };

  // --- Shared rendering helpers ---

  const getActiveExpertsCount = (): number => {
    const activeExperts = new Set();
    progressEvents.forEach(event => {
      if (event.data?.expert_id && event.event_type !== 'complete') {
        activeExperts.add(event.data.expert_id);
      }
    });
    return activeExperts.size;
  };

  // Active phase message (new or legacy)
  const activePhaseMessage = useLegacy
    ? (() => {
        const active = legacyPhases.find(p => getLegacyPhaseStatus(p.name) === 'active');
        return active ? (LEGACY_PHASE_MESSAGES[active.name] || 'Processing...') : null;
      })()
    : getActivePhaseMessageNew();

  // Which phase items to render
  const renderPhases = useLegacy
    ? legacyPhases.map(p => ({ ...p, id: p.name, status: getLegacyPhaseStatus(p.name) }))
    : visibleGroups;

  return (
    <div className="progress-section">
      <div className="progress-content">
        {/* Top area: Stats or Status Message */}
        <div>
          {!isProcessing && stats && (
            <div className="progress-stats-row">
              <div className="stat-group">
                <span className="stat-label">Statistics:</span>
              </div>
              <div className="stat-group">
                <span className="stat-value">{stats.totalPosts}</span>
                <span className="stat-unit"> posts</span>
              </div>
              <div className="stat-group">
                <span className="stat-value">{stats.processingTime.toFixed(1)}</span>
                <span className="stat-unit"> s</span>
              </div>
            </div>
          )}

          {isProcessing && (
            <div className="progress-stats-row">
              <div className="stat-group">
                <span className="stat-label">
                  Processing {getActiveExpertsCount()} experts:
                </span>
              </div>
              {activePhaseMessage && (
                <div className="stat-group active-phase-text">
                  <span className="loading-icon-small">🔄</span>
                  {' '}{activePhaseMessage}
                </div>
              )}
            </div>
          )}

          {!isProcessing && !stats && progressEvents.length === 0 && (
            <div className="stat-unit">
              Ready to process queries
            </div>
          )}
        </div>

        {/* Bottom area: Phase progress line */}
        {renderPhases.length > 0 && (
          <div className="phase-progress-line">
            <span className="stat-label">Stages:</span>
            {renderPhases.map((phase, index) => {
              const isLast = index === renderPhases.length - 1;

              return (
                <React.Fragment key={phase.id}>
                  <span className={`phase-item ${phase.status}`}>
                    {phase.status === 'completed' ? '✓' : phase.icon}
                    {' '}{phase.label}
                  </span>
                  {!isLast && <span className="phase-separator">→</span>}
                </React.Fragment>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressSection;
