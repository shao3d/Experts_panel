/**
 * Grouped expert selection bar component (Mobile View).
 * Displays experts in two category rows.
 * Supports "Select All" functionality by clicking group labels.
 */

import React from 'react';
import { ExpertInfo } from '../types/api';
import { EXPERT_GROUPS, getExpertDisplayName } from '../config/expertConfig';

interface ExpertSelectionBarProps {
  availableExperts: ExpertInfo[];
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
}

/**
 * Grouped expert selection bar component
 */
const ExpertSelectionBar: React.FC<ExpertSelectionBarProps> = ({
  availableExperts,
  selectedExperts,
  onExpertsChange,
  disabled = false
}) => {
  
  const handleToggleExpert = (expertId: string): void => {
    if (disabled) return;
    const newSelected = new Set(selectedExperts);
    if (newSelected.has(expertId)) {
      newSelected.delete(expertId);
    } else {
      newSelected.add(expertId);
    }
    onExpertsChange(newSelected);
  };

  const handleToggleGroup = (groupIds: string[]) => {
    if (disabled) return;
    const allSelected = groupIds.every(id => selectedExperts.has(id));
    const newSelected = new Set(selectedExperts);
    
    if (allSelected) {
      // Deselect all
      groupIds.forEach(id => newSelected.delete(id));
    } else {
      // Select all
      groupIds.forEach(id => newSelected.add(id));
    }
    onExpertsChange(newSelected);
  };

  /**
   * Render a single expert checkbox item
   */
  const renderExpertItem = (expert: ExpertInfo) => (
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
          {getExpertDisplayName(expert.expert_id, expert.display_name)}
          {expert.stats && (
            <span style={{ fontSize: '0.75em', color: '#6c757d', marginLeft: '2px' }}>
              {expert.stats.posts_count}/{expert.stats.comments_count}
            </span>
          )}
          <a
            href={`https://t.me/${expert.channel_username}`}
            title={`Open @${expert.channel_username} in Telegram`}
            target="_blank"
            rel="noopener noreferrer"
            className="expert-link-icon"
            onClick={(e) => e.stopPropagation()}
            style={{ textDecoration: 'none', display: 'inline-flex' }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              style={{ verticalAlign: 'middle' }}
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
  );

  // Create a map for quick expert lookup
  const expertMap = new Map(availableExperts.map(e => [e.expert_id, e]));

  return (
    <div className="expert-bar-grouped">
      {EXPERT_GROUPS.map((group) => {
        // Filter to only include experts that exist in availableExperts
        const groupExperts = group.expertIds
          .map(id => expertMap.get(id))
          .filter((e): e is ExpertInfo => e !== undefined);

        if (groupExperts.length === 0) return null;

        const allGroupSelected = groupExperts.every(e => selectedExperts.has(e.expert_id));

        return (
          <div key={group.label} className="expert-group-row">
            <span 
              className="expert-group-label" 
              onClick={() => handleToggleGroup(group.expertIds)}
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
              title="Click to toggle group"
            >
              {group.label}
              <span style={{ fontSize: '10px', opacity: 0.6, fontWeight: 'normal' }}>
                {allGroupSelected ? '(All)' : '(Select)'}
              </span>
            </span>
            <div className="expert-group-items">
              {groupExperts.map(renderExpertItem)}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ExpertSelectionBar;