import React, { useEffect, useMemo, useState } from 'react';
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
  elapsedSeconds: number;
  selectedExperts: Set<string>;
  hasRedditEnabled: boolean;
  progressEvents: ProgressEvent[];
  stats?: QueryDeckStats;
  currentQuery: string;
  error?: string | null;
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
  elapsedSeconds,
  selectedExperts,
  hasRedditEnabled,
  progressEvents,
  stats,
  currentQuery,
  error,
}) => {
  const [draftQuery, setDraftQuery] = useState('');
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => {
    if (error) {
      setIsExpanded(true);
    }
  }, [error]);

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
    setIsExpanded(false);
    onSubmit(query);
  };

  const handleEdit = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setDraftQuery(currentQuery || draftQuery);
    setIsExpanded(true);
  };

  const handleNewQuery = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setDraftQuery('');
    setIsExpanded(true);
  };

  return (
    <section className={clsx('query-deck', isExpanded ? 'expanded' : 'compact')}>
      {isExpanded ? (
        <div className="query-deck-expanded">
          <div className="query-deck-form">
            <QueryForm
              onSubmit={handleSubmit}
              disabled={disabled}
              elapsedSeconds={elapsedSeconds}
              selectedExperts={selectedExperts}
              hasRedditEnabled={hasRedditEnabled}
              value={draftQuery}
              onChange={setDraftQuery}
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
          <span className="query-deck-compact-icon" aria-hidden="true">v</span>
          <span className="query-deck-compact-label">Query</span>
          <span className="query-deck-compact-query">{querySummary}</span>
          <span className={clsx('query-deck-compact-status', error && 'error')}>
            {statusText}
          </span>
          <span className="query-deck-compact-actions">
            <button
              type="button"
              className="query-deck-compact-action"
              onClick={handleEdit}
            >
              Edit
            </button>
            <button
              type="button"
              className="query-deck-compact-action primary"
              onClick={handleNewQuery}
            >
              New
            </button>
          </span>
        </div>
      )}
    </section>
  );
};

export default QueryDeck;
