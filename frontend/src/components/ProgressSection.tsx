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

const ProgressSection: React.FC<ProgressSectionProps> = ({ isProcessing, progressEvents, stats }) => {

  // Define phases for active phase detection
  const phases = [
    { name: 'map', label: 'Map', icon: '🔍' },
    { name: 'resolve', label: 'Resolve', icon: '🔗' },
    { name: 'reduce', label: 'Reduce', icon: '⚡' },
    { name: 'comment_groups', label: 'Comments', icon: '💬' },
    { name: 'final_results', label: 'Final', icon: '🎯' }
  ];

  // Determine phase status based on events
  const getPhaseStatus = (phaseName: string): 'pending' | 'active' | 'completed' => {
    // Special handling for resolve phase - include medium_scoring events
    if (phaseName === 'resolve') {
      const resolveEvents = progressEvents.filter(e => e.phase === 'resolve');
      const scoringEvents = progressEvents.filter(e => e.phase === 'medium_scoring');

      if (resolveEvents.length > 0 || scoringEvents.length > 0) {
        const lastResolve = resolveEvents[resolveEvents.length - 1];
        const lastScoring = scoringEvents[scoringEvents.length - 1];

        // Check if either is still processing
        const resolveActive = lastResolve?.status !== 'completed';
        const scoringActive = lastScoring?.status !== 'completed';

        if (resolveActive || scoringActive) return 'active';
        return 'completed';
      }
      return 'pending';
    }

    // Special handling for final_results phase
    if (phaseName === 'final_results') {
      if (!isProcessing) {
        // Check if all other phases are completed
        const otherPhases = phases.filter(p => p.name !== 'final_results');
        const allCompleted = otherPhases.every(p => getPhaseStatus(p.name) === 'completed');
        return allCompleted ? 'completed' : 'pending';
      }
      // Check if all other phases are completed but we're still processing
      const otherPhases = phases.filter(p => p.name !== 'final_results');
      const allCompleted = otherPhases.every(p => getPhaseStatus(p.name) === 'completed');
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

  // Get contextual description for active phases
  const getActivePhaseMessage = (phaseName: string): string => {
    const messages: Record<string, string> = {
      'map': 'Searching relevant posts...',
      'resolve': 'Analyzing connections...',
      'reduce': 'Generating answers...',
      'comment_groups': 'Finding discussions...',
      'language_validation': 'Validating...',
      'comment_synthesis': 'Extracting insights...',
      'final_results': 'Finishing up...'
    };
    return messages[phaseName] || 'Processing...';
  };

  // Get active expert count from progress events
  const getActiveExpertsCount = (): number => {
    const activeExperts = new Set();
    progressEvents.forEach(event => {
      if (event.data?.expert_id && event.event_type !== 'complete') {
        activeExperts.add(event.data.expert_id);
      }
    });
    return activeExperts.size;
  };

  // Find active phase for contextual description
  const activePhase = phases.find(p => getPhaseStatus(p.name) === 'active');

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
              {activePhase && (
                <div className="stat-group active-phase-text">
                  <span className="loading-icon-small">🔄</span>
                  {' '}{getActivePhaseMessage(activePhase.name)}
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

        {/* Bottom area: Phase progress line (Hidden on mobile header via CSS) */}
        {(progressEvents.length > 0 || isProcessing) && (
          <div className="phase-progress-line">
            <span className="stat-label">Stages:</span>
            {phases.map((phase, index) => {
              const status = getPhaseStatus(phase.name);
              const isLast = index === phases.length - 1;
              
              return (
                <React.Fragment key={phase.name}>
                  <span className={`phase-item ${status}`}>
                    {status === 'completed' ? '✓' : phase.icon}
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
