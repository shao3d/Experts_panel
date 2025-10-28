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
}

/**
 * Query input form component
 */
export const QueryForm: React.FC<QueryFormProps> = ({
  onSubmit,
  disabled = false,
  placeholder = "Ask experts about AI and related...",
  elapsedSeconds = 0
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

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <div style={styles.inputRow}>
        <div style={styles.textareaContainer}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={disabled}
            placeholder={placeholder}
            rows={2}
            style={styles.textarea}
            maxLength={1000}
          />
          <span style={styles.counter}>
            {query.length} / 1000
          </span>
        </div>

        <button
          type="submit"
          disabled={disabled || query.trim().length < 3}
          style={{
            ...styles.button,
            ...(disabled || query.trim().length < 3 ? styles.buttonDisabled : {})
          }}
        >
          {disabled ? `${elapsedSeconds}s` : 'Ask'}
        </button>
      </div>
    </form>
  );
};

// Simple inline styles for MVP
const styles = {
  form: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%'
  },
  inputRow: {
    display: 'flex',
    gap: '10px',
    alignItems: 'stretch',
    flex: 1
  },
  textareaContainer: {
    flex: 1,
    position: 'relative' as const
  },
  textarea: {
    width: '100%',
    height: '100%',
    padding: '12px',
    paddingBottom: '28px',
    fontSize: '14px',
    lineHeight: '1.5',
    border: '2px solid #e0e0e0',
    borderRadius: '8px',
    backgroundColor: 'white',
    color: '#1a1a1a',
    resize: 'none' as const,
    fontFamily: 'inherit',
    minHeight: '90px',
    boxSizing: 'border-box' as const
  },
  counter: {
    position: 'absolute' as const,
    bottom: '8px',
    right: '12px',
    fontSize: '12px',
    color: '#999',
    pointerEvents: 'none' as const
  },
  button: {
    padding: '12px 24px',
    fontSize: '15px',
    fontWeight: '600' as const,
    color: 'white',
    backgroundColor: '#0066cc',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 2px 4px rgba(0, 102, 204, 0.2)',
    minWidth: '80px',
    height: '90px'
  },
  buttonDisabled: {
    backgroundColor: '#d0d0d0',
    color: '#999',
    cursor: 'not-allowed',
    boxShadow: 'none'
  }
};

export default QueryForm;
