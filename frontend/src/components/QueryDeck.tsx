import React, { useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import QueryForm from './QueryForm';
import ProgressSection from './ProgressSection';
import { ProgressEvent } from '../types/api';

interface QueryDeckStats {
  totalPosts: number;
  processingTime: number;
  expertCount?: number;
}

interface QueryDeckProps {
  onSubmit: (query: string) => void;
  disabled: boolean;
  selectedExperts: Set<string>;
  hasRedditEnabled: boolean;
  progressEvents: ProgressEvent[];
  stats?: QueryDeckStats;
  currentQuery: string;
  error?: string | null;
  onStop?: () => void;
}

const PHASE_LABELS: Record<string, string> = {
  scout: 'Searching',
  map: 'Scoring',
  medium_scoring: 'Reranking',
  resolve: 'Expanding context',
  reduce: 'Generating answers',
  language_validation: 'Validating',
  comment_groups: 'Finding discussions',
  comment_synthesis: 'Extracting insights',
  video_map: 'Scoring video',
  video_resolve: 'Expanding video',
  video_synthesis: 'Video synthesis',
  video_validation: 'Video validation',
  meta_synthesis: 'Cross-expert synthesis',
  reddit_search: 'Searching Reddit',
  reddit_synthesis: 'Reddit synthesis',
};

function getActivePhaseLabel(progressEvents: ProgressEvent[]): string | null {
  for (let i = progressEvents.length - 1; i >= 0; i--) {
    const state = progressEvents[i].pipeline_state;
    if (!state) continue;

    const activePhase = Object.entries(state).find(([, status]) => status === 'active')?.[0];
    if (activePhase) {
      return PHASE_LABELS[activePhase] || progressEvents[i].message || 'Processing';
    }
  }

  const latest = progressEvents[progressEvents.length - 1];
  if (!latest) return null;
  return PHASE_LABELS[latest.phase] || latest.message || null;
}

const QueryDeck: React.FC<QueryDeckProps> = ({
  onSubmit,
  disabled,
  selectedExperts,
  hasRedditEnabled,
  progressEvents,
  stats,
  currentQuery,
  error,
  onStop,
}) => {
  const [draftQuery, setDraftQuery] = useState('');
  const [isExpanded, setIsExpanded] = useState(true);
  const wasProcessingRef = useRef(false);

  useEffect(() => {
    if (error) {
      setIsExpanded(true);
    }
  }, [error]);

  useEffect(() => {
    if (wasProcessingRef.current && !disabled && !error && (currentQuery || stats)) {
      setIsExpanded(false);
    }

    wasProcessingRef.current = disabled;
  }, [currentQuery, disabled, error, stats]);

  const statusText = useMemo(() => {
    if (error) return 'Needs attention';
    if (disabled) return getActivePhaseLabel(progressEvents) || 'Processing';
    if (stats) {
      const expertText = stats.expertCount ? `${stats.expertCount} experts` : 'Experts';
      return `${expertText} / ${stats.totalPosts} posts / ${stats.processingTime.toFixed(1)}s`;
    }
    return 'Ready';
  }, [disabled, error, progressEvents, stats]);

  const querySummary = currentQuery || draftQuery || 'Ready for a new query';

  const handleSubmit = (query: string) => {
    setDraftQuery(query);
    setIsExpanded(true);
    onSubmit(query);
  };

  const handleStop = () => {
    setDraftQuery('');
    setIsExpanded(true);
    onStop?.();
  };

  return (
    <section className={clsx('query-deck', isExpanded ? 'expanded' : 'compact')}>
      {isExpanded ? (
        <div className="query-deck-expanded">
          <div className="query-deck-form">
            <QueryForm
              onSubmit={handleSubmit}
              disabled={disabled}
              selectedExperts={selectedExperts}
              hasRedditEnabled={hasRedditEnabled}
              value={draftQuery}
              onChange={setDraftQuery}
              onStop={handleStop}
            />
          </div>

          <div className="query-deck-progress">
            <ProgressSection
              isProcessing={disabled}
              progressEvents={progressEvents}
              stats={stats}
            />
          </div>

          {(currentQuery || stats || disabled) && (
            <button
              type="button"
              className="query-deck-collapse"
              onClick={() => setIsExpanded(false)}
              aria-label="Collapse query panel"
              title="Collapse"
            >
              <span aria-hidden="true">^</span>
            </button>
          )}
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          className="query-deck-compact"
          onClick={() => setIsExpanded(true)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setIsExpanded(true);
            }
          }}
          aria-label="Expand query panel"
        >
          <span className="query-deck-compact-label">Query</span>
          <span className="query-deck-compact-query">{querySummary}</span>
          <span className={clsx('query-deck-compact-status', error && 'error')}>
            {statusText}
          </span>
          <span className="query-deck-compact-icon" aria-hidden="true">v</span>
        </div>
      )}
    </section>
  );
};

export default QueryDeck;
