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
      'resolve': 'Analyzing connections and scoring medium posts...',
      'reduce': 'Generating comprehensive answer...',
      'comment_groups': 'Finding relevant discussions...',
      'language_validation': 'Validating response language...',
      'comment_synthesis': 'Extracting discussion insights...',
      'final_results': 'Assembling expert responses...'
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

  // Define phases for active phase detection
  const phases = [
    { name: 'map', label: 'Map', icon: '🔍' },
    { name: 'resolve', label: 'Resolve', icon: '🔗' },
    { name: 'reduce', label: 'Reduce', icon: '⚡' },
    { name: 'comment_groups', label: 'Comments', icon: '💬' },
    { name: 'final_results', label: 'Final', icon: '🎯' }
  ];

  // Find active phase for contextual description
  const activePhase = phases.find(p => getPhaseStatus(p.name) === 'active');

  // Render compact phase progress line with checkboxes
  const renderPhaseProgressLine = () => {
    if (progressEvents.length === 0 && !isProcessing) return null;

    return (
      <div style={{
        display: 'flex',
        gap: '8px',
        flexWrap: 'wrap',
        alignItems: 'center',
        fontSize: '14px',
      }}>
        <span style={{ fontSize: '14px', color: '#495057', fontWeight: '500' }}>Stages:</span>

        {phases.map((phase, index) => {
          const status = getPhaseStatus(phase.name);
          const isLast = index === phases.length - 1;

          return (
            <React.Fragment key={phase.name}>
              <span style={{
                color: status === 'completed' ? '#28a745' :
                       status === 'active' ? '#0066cc' : '#adb5bd',
                fontWeight: status === 'active' ? 'bold' : 'normal'
              }}>
                {status === 'completed' ? '✓' :
                 status === 'active' ? phase.icon : phase.icon}
                {' '}{phase.label}
              </span>
              {!isLast && <span style={{ color: '#dee2e6' }}>→</span>}
            </React.Fragment>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{
      backgroundColor: 'white',
      borderRadius: '8px',
      border: '1px solid #dee2e6',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Content */}
      <div style={{
        padding: '16px',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '12px',
      }}>
        {/* Top area: Final stats (only when complete) or empty space */}
        <div>
          {!isProcessing && stats && (
            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px', color: '#495057', fontWeight: '500' }}>Statistics:</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#212529' }}>{stats.totalPosts}</span>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>posts</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#212529' }}>
                  {stats.processingTime.toFixed(1)}
                </span>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>seconds</span>
              </div>
            </div>
          )}
          {isProcessing && (
            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: '14px', color: '#495057', fontWeight: '500' }}>
                  Processing {getActiveExpertsCount()} experts:
                </span>
              </div>
              {activePhase && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '14px', color: '#0066cc' }}>
                    {getActivePhaseMessage(activePhase.name)}
                  </span>
                </div>
              )}
            </div>
          )}
          {!isProcessing && !stats && progressEvents.length === 0 && (
            <div style={{ color: '#6c757d', fontSize: '14px' }}>
              Ready to process queries
            </div>
          )}
        </div>

        {/* Bottom area: Phase progress line (always at bottom when active) */}
        {renderPhaseProgressLine()}
      </div>
    </div>
  );
};

export default ProgressSection;