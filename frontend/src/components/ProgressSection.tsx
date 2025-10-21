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

  // Track elapsed time
  const [startTime, setStartTime] = React.useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);

  React.useEffect(() => {
    if (isProcessing && !startTime) {
      setStartTime(Date.now());
    }
    if (!isProcessing) {
      setStartTime(null);
      setElapsedSeconds(0);
    }
  }, [isProcessing]);

  React.useEffect(() => {
    if (!isProcessing || !startTime) return;

    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [isProcessing, startTime]);

  // Determine phase status based on events
  const getPhaseStatus = (phaseName: string): 'pending' | 'active' | 'completed' => {
    const phaseEvents = progressEvents.filter(e => e.phase === phaseName);
    if (phaseEvents.length === 0) return 'pending';

    const lastEvent = phaseEvents[phaseEvents.length - 1];
    if (lastEvent.event_type === 'phase_complete' || lastEvent.status === 'completed') {
      return 'completed';
    }
    return 'active';
  };

  // Render compact phase progress line with checkboxes
  const renderPhaseProgressLine = () => {
    if (progressEvents.length === 0 && !isProcessing) return null;

    const phases = [
      { name: 'map', label: 'Map', icon: '🔍' },
      { name: 'resolve', label: 'Resolve', icon: '🔗' },
      { name: 'reduce', label: 'Reduce', icon: '⚡' },
      { name: 'comment_groups', label: 'Comments', icon: '💬' }
    ];

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
                {status === 'completed' ? '✓' : status === 'active' ? phase.icon : phase.icon}
                {' '}{phase.label}
              </span>
              {!isLast && <span style={{ color: '#dee2e6' }}>→</span>}
            </React.Fragment>
          );
        })}

        {isProcessing && (
          <span style={{ color: '#6c757d', marginLeft: '8px' }}>
            ({elapsedSeconds} seconds)
          </span>
        )}
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
                <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#212529' }}>{stats.totalPosts}</span>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>posts</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#212529' }}>
                  {stats.processingTime.toFixed(1)}
                </span>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>seconds</span>
              </div>
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