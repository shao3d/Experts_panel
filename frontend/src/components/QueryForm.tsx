/**
 * Query input form component.
 * Simple textarea with submit button for MVP.
 */

import React, { useState, FormEvent } from 'react';

interface QueryFormProps {
  /** Callback when query is submitted */
  onSubmit: (query: string) => void;

  /** Whether form is disabled during processing */
  disabled?: boolean;

  /** Placeholder text for input */
  placeholder?: string;

  /** Elapsed processing time in seconds */
  elapsedSeconds?: number;

  /** Set of selected expert IDs, used to disable submit button */
  selectedExperts?: Set<string>;

  /** Whether Reddit search is enabled (for submit button validation) */
  hasRedditEnabled?: boolean;
}

/**
 * Query input form component
 */
export const QueryForm: React.FC<QueryFormProps> = ({
  onSubmit,
  disabled = false,
  placeholder = "Ask experts about AI and related...",
  elapsedSeconds = 0,
  selectedExperts = new Set(),
  hasRedditEnabled = true
}) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();

    const trimmed = query.trim();
    if (trimmed.length < 3) {
      alert('Question must be at least 3 characters');
      return;
    }

    onSubmit(trimmed);
  };

  const hasAnySource = selectedExperts.size > 0 || hasRedditEnabled;
  const isButtonDisabled = disabled || query.trim().length < 3 || !hasAnySource;

  return (
    <form onSubmit={handleSubmit} className="query-form h-full">
      <div className="query-input-row h-full">
        <div className="query-textarea-container h-full">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={disabled}
            placeholder={placeholder}
            className="query-textarea h-full min-h-[100px] resize-none"
            maxLength={1000}
          />
          <span className="query-counter">
            {query.length} / 1000
          </span>
        </div>

        <button
          type="submit"
          disabled={isButtonDisabled}
          className="query-submit-button h-full"
        >
          {disabled ? `${elapsedSeconds}s` : 'Ask'}
        </button>
      </div>
    </form>
  );
};

export default QueryForm;