/**
 * Query input form component.
 * Simple textarea with submit button for MVP.
 */

import React, { useState, FormEvent } from 'react';

interface QueryFormProps {
  /** Callback when query is submitted */
  onSubmit: (query: string, options?: { use_recent_only?: boolean; include_reddit?: boolean }) => void;

  /** Whether form is disabled during processing */
  disabled?: boolean;

  /** Placeholder text for input */
  placeholder?: string;

  /** Elapsed processing time in seconds */
  elapsedSeconds?: number;

  /** Set of selected expert IDs, used to disable submit button */
  selectedExperts?: Set<string>;
}

/**
 * Query input form component
 */
export const QueryForm: React.FC<QueryFormProps> = ({
  onSubmit,
  disabled = false,
  placeholder = "Ask experts about AI and related...",
  elapsedSeconds = 0,
  selectedExperts = new Set()
}) => {
  const [query, setQuery] = useState('');
  const [useRecentOnly, setUseRecentOnly] = useState(false);
  const [includeReddit, setIncludeReddit] = useState(true);

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();

    const trimmed = query.trim();
    if (trimmed.length < 3) {
      alert('Question must be at least 3 characters');
      return;
    }

    onSubmit(trimmed, { use_recent_only: useRecentOnly, include_reddit: includeReddit });
  };

  const hasAnySource = selectedExperts.size > 0 || includeReddit;
  const isButtonDisabled = disabled || query.trim().length < 3 || !hasAnySource;

  return (
    <form onSubmit={handleSubmit} className="query-form">
      <div className="query-input-row">
        <div className="query-textarea-container">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={disabled}
            placeholder={placeholder}
            rows={2}
            className="query-textarea"
            maxLength={1000}
          />
          <span className="query-counter">
            {query.length} / 1000
          </span>
        </div>

        <button
          type="submit"
          disabled={isButtonDisabled}
          className="query-submit-button"
        >
          {disabled ? `${elapsedSeconds}s` : 'Ask'}
        </button>
      </div>

      <div className="recent-filter-row">
        <label className="recent-filter-label">
          <input
            type="checkbox"
            checked={useRecentOnly}
            onChange={(e) => setUseRecentOnly(e.target.checked)}
            disabled={disabled}
            className="recent-filter-checkbox"
          />
          <span className="recent-filter-text">🕒 Только последние 3 месяца</span>
          <span className="recent-filter-hint">Для свежих новостей</span>
        </label>

        <label className="recent-filter-label reddit-filter-label">
          <input
            type="checkbox"
            checked={includeReddit}
            onChange={(e) => setIncludeReddit(e.target.checked)}
            disabled={disabled}
            className="recent-filter-checkbox"
          />
          <span className="recent-filter-text">👥 Искать на Reddit</span>
          <span className="recent-filter-hint">Сообщества и обсуждения</span>
        </label>
      </div>
    </form>
  );
};

export default QueryForm;