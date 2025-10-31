/**
 * Horizontal expert selection bar component.
 * Displays all experts in a single horizontal row with checkboxes.
 */

import React from 'react';

interface ExpertSelectionBarProps {
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
}

// Available experts configuration
const AVAILABLE_EXPERTS = [
  { id: 'refat', name: 'Refat Talks: Tech & AI', description: '' },
  { id: 'ai_architect', name: 'AI Architect | AI Coding', description: '' },
  { id: 'neuraldeep', name: 'Neural Kovalskii', description: '' }
];

/**
 * Horizontal expert selection bar component
 */
const ExpertSelectionBar: React.FC<ExpertSelectionBarProps> = ({
  selectedExperts,
  onExpertsChange,
  disabled = false
}) => {
  /**
   * Toggle expert selection
   */
  const handleToggleExpert = (expertId: string): void => {
    const newSelected = new Set(selectedExperts);
    if (newSelected.has(expertId)) {
      newSelected.delete(expertId);
    } else {
      newSelected.add(expertId);
    }
    onExpertsChange(newSelected);
  };

  return (
    <div style={styles.container}>
      <div style={styles.expertsRow}>
        <span style={styles.title}>EXPERTS:</span>
        {AVAILABLE_EXPERTS.map((expert) => (
          <div key={expert.id} style={styles.expertItem}>
            <label style={{
              ...styles.label,
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.6 : 1
            }}>
              <input
                type="checkbox"
                checked={selectedExperts.has(expert.id)}
                onChange={() => handleToggleExpert(expert.id)}
                disabled={disabled}
                style={{
                  ...styles.checkbox,
                  cursor: disabled ? 'not-allowed' : 'pointer'
                }}
              />
              <span style={styles.expertName}>
                {expert.name}
              </span>
            </label>
          </div>
        ))}
      </div>
    </div>
  );
};

// Styles for the horizontal expert selection bar
const styles = {
  container: {
    width: '100%',
    backgroundColor: 'white',
    borderTop: '1px solid #dee2e6',
    padding: '12px 20px',
    boxSizing: 'border-box' as const
  },
  header: {
    marginBottom: '8px'
  },
  title: {
    fontSize: '13px',
    fontWeight: '600' as const,
    color: '#495057',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px'
  },
  expertsRow: {
    display: 'flex',
    gap: '24px',
    alignItems: 'center',
    flexWrap: 'wrap' as const
  },
  expertItem: {
    display: 'flex',
    alignItems: 'center'
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer'
  },
  checkbox: {
    margin: 0,
    cursor: 'pointer'
  },
  expertName: {
    fontSize: '14px',
    color: '#495057',
    userSelect: 'none' as const
  }
};

export default ExpertSelectionBar;