/**
 * Horizontal expert selection bar component.
 * Displays all experts in a single horizontal row with checkboxes.
 */

import React from 'react';

interface ExpertInfo {
  expert_id: string;
  display_name: string;
  channel_username: string;
}

interface ExpertSelectionBarProps {
  availableExperts: ExpertInfo[];
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
}

/**
 * Horizontal expert selection bar component
 */
const ExpertSelectionBar: React.FC<ExpertSelectionBarProps> = ({
  availableExperts,
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
        {availableExperts.map((expert) => (
          <div key={expert.expert_id} style={styles.expertItem}>
            <label style={{
              ...styles.label,
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.6 : 1
            }}>
              <input
                type="checkbox"
                checked={selectedExperts.has(expert.expert_id)}
                onChange={() => handleToggleExpert(expert.expert_id)}
                disabled={disabled}
                style={{
                  ...styles.checkbox,
                  cursor: disabled ? 'not-allowed' : 'pointer'
                }}
              />
              <a
                href={`https://t.me/${expert.channel_username}`}
                title={`https://t.me/${expert.channel_username}`}
                target="_blank"
                rel="noopener noreferrer"
                style={styles.expertNameLink}
                onClick={(e) => e.stopPropagation()} // Prevent click from toggling checkbox
              >
                {expert.display_name}
              </a>
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
  },
  expertNameLink: {
    fontSize: '14px',
    color: '#495057',
    userSelect: 'none' as const,
    textDecoration: 'none'
  }
};

export default ExpertSelectionBar;