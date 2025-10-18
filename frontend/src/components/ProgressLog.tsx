/**
 * Progress log component for displaying SSE events.
 * Shows real-time processing status during query.
 */

import React from 'react';
import { ProgressEvent } from '../types/api';

interface ProgressLogProps {
  /** Array of progress events to display */
  events: ProgressEvent[];

  /** Whether processing is still ongoing */
  isProcessing: boolean;
}

/**
 * Progress log component showing SSE events
 */
export const ProgressLog: React.FC<ProgressLogProps> = ({
  events,
  isProcessing
}) => {
  if (events.length === 0 && !isProcessing) {
    return null;
  }

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>
        {isProcessing ? '⚙️ Обработка запроса...' : '✅ Обработка завершена'}
      </h3>

      <div style={styles.logContainer}>
        {events.map((event, index) => (
          <div key={index} style={styles.logEntry}>
            <span style={styles.phase}>
              {getPhaseIcon(event.phase)} {event.phase}
            </span>
            <span style={styles.message}>
              {event.message}
            </span>
            {event.data && (
              <span style={styles.data}>
                {formatEventData(event.data)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * Get emoji icon for phase
 */
function getPhaseIcon(phase: string): string {
  const icons: Record<string, string> = {
    'map': '🗺️',
    'resolve': '🔗',
    'reduce': '📝',
    'final': '🎯'
  };
  return icons[phase] || '•';
}

/**
 * Format event data for display
 */
function formatEventData(data: Record<string, any>): string {
  const parts: string[] = [];

  if (data.relevant_count !== undefined) {
    parts.push(`${data.relevant_count} релевантных`);
  }
  if (data.enriched_count !== undefined) {
    parts.push(`${data.enriched_count} обогащённых`);
  }
  if (data.links_followed !== undefined) {
    parts.push(`${data.links_followed} связей`);
  }
  if (data.confidence) {
    parts.push(`confidence: ${data.confidence}`);
  }

  return parts.length > 0 ? `(${parts.join(', ')})` : '';
}

// Simple inline styles for MVP
const styles = {
  container: {
    marginBottom: '24px',
    padding: '16px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px',
    border: '1px solid #e0e0e0'
  },
  title: {
    margin: '0 0 12px 0',
    fontSize: '18px',
    fontWeight: '600' as const
  },
  logContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '8px',
    maxHeight: '300px',
    overflowY: 'auto' as const
  },
  logEntry: {
    display: 'flex',
    gap: '12px',
    padding: '8px',
    backgroundColor: 'white',
    borderRadius: '4px',
    fontSize: '14px',
    lineHeight: '1.4'
  },
  phase: {
    fontWeight: '600' as const,
    color: '#667eea',
    minWidth: '100px'
  },
  message: {
    flex: '1',
    color: '#333'
  },
  data: {
    color: '#666',
    fontSize: '13px'
  }
};

export default ProgressLog;
