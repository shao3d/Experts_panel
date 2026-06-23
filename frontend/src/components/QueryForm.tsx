/**
 * Query input form component.
 * Simple textarea with submit button for MVP.
 */

import React, { useEffect, useState, FormEvent } from 'react';

interface QueryFormProps {
  /** Callback when query is submitted */
  onSubmit: (query: string) => void;

  /** Whether form is disabled during processing */
  disabled?: boolean;

  /** Placeholder text for input */
  placeholder?: string;

  /** Set of selected expert IDs, used to disable submit button */
  selectedExperts?: Set<string>;

  /** Whether Reddit search is enabled (for submit button validation) */
  hasRedditEnabled?: boolean;

  /** Controlled query value, used by the collapsible query deck */
  value?: string;

  /** Controlled query change handler */
  onChange?: (value: string) => void;

  /** Callback when active query should be stopped */
  onStop?: () => void;

  /** Token used to clear uncontrolled query value */
  resetToken?: number;
}

/**
 * Query input form component
 */
export const QueryForm: React.FC<QueryFormProps> = ({
  onSubmit,
  disabled = false,
  placeholder = "Ask experts about AI and related...",
  selectedExperts = new Set(),
  hasRedditEnabled = true,
  value,
  onChange,
  onStop,
  resetToken
}) => {
  const [internalQuery, setInternalQuery] = useState('');
  const query = value ?? internalQuery;
  const setQuery = onChange ?? setInternalQuery;

  useEffect(() => {
    if (value === undefined) {
      setInternalQuery('');
    }
  }, [resetToken, value]);

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();

    if (disabled) {
      onStop?.();
      return;
    }

    const trimmed = query.trim();
    if (trimmed.length < 3) {
      alert('Question must be at least 3 characters');
      return;
    }

    onSubmit(trimmed);
  };

  const hasAnySource = selectedExperts.size > 0 || hasRedditEnabled;
  const isButtonDisabled = !disabled && (query.trim().length < 3 || !hasAnySource);
  const submitLabel = disabled ? 'Stop' : 'Ask';
  const submitAriaLabel = disabled ? 'Stop current search' : 'Ask experts';

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
          className={`query-submit-button h-full ${disabled ? 'stop' : ''}`}
          aria-label={submitAriaLabel}
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
};

export default QueryForm;
