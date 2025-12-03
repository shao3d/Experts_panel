/**
 * Horizontal expert selection bar component.
 * Displays all experts in a single horizontal row with checkboxes.
 * Supports desktop row and mobile wrapping layouts via CSS.
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
    <div className="expert-bar">
      <span className="expert-bar-title">
        EXPERTS:
      </span>
      
      {availableExperts.map((expert) => (
        <div key={expert.expert_id} className="expert-item">
          <label 
            className="expert-checkbox-label"
            style={{
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.6 : 1
            }}
          >
            <input
              type="checkbox"
              checked={selectedExperts.has(expert.expert_id)}
              onChange={() => handleToggleExpert(expert.expert_id)}
              disabled={disabled}
              style={{
                cursor: disabled ? 'not-allowed' : 'pointer'
              }}
            />
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {expert.display_name}
              <a
                href={`https://t.me/${expert.channel_username}`}
                title={`Open @${expert.channel_username} in Telegram`}
                target="_blank"
                rel="noopener noreferrer"
                className="expert-link-icon"
                onClick={(e) => e.stopPropagation()} // Prevent click from toggling checkbox
                style={{ textDecoration: 'none', display: 'inline-flex' }}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  style={{
                    verticalAlign: 'middle'
                  }}
                >
                  <path
                    d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"
                    fill="#0088cc"
                  />
                </svg>
              </a>
            </span>
          </label>
        </div>
      ))}
    </div>
  );
};

export default ExpertSelectionBar;