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
            <span>{expert.display_name}</span>
          </label>
          
          <a
            href={`https://t.me/${expert.channel_username}`}
            title={`Open @${expert.channel_username} in Telegram`}
            target="_blank"
            rel="noopener noreferrer"
            className="expert-link-icon"
            onClick={(e) => e.stopPropagation()} // Prevent click from toggling checkbox
          >
            ✈️
          </a>
        </div>
      ))}
    </div>
  );
};

export default ExpertSelectionBar;