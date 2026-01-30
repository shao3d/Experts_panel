/**
 * Grouped expert selection bar component.
 * Displays experts in two category rows: TechExperts and Tech&BizExperts.
 * Supports desktop row and mobile wrapping layouts via CSS.
 */

import React from 'react';
import { ExpertInfo } from '../types/api';

interface ExpertSelectionBarProps {
  availableExperts: ExpertInfo[];
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
}

/**
 * Frontend display name overrides (short, clean names for UI)
 */
const DISPLAY_NAME_MAP: Record<string, string> = {
  'ai_architect': 'AI_Arch',
  'neuraldeep': 'Kovalskii',
  'ai_grabli': 'AI_Grabli',
  'refat': 'Refat',
  'akimov': 'Akimov',
  'llm_under_hood': 'Rinat',
  'elkornacio': 'Elkornacio',
  'ilia_izmailov': 'Ilia',
  'polyakov': 'Polyakov',
  'doronin': 'Doronin',
};

/**
 * Expert category groups
 */
const EXPERT_GROUPS: { label: string; expertIds: string[] }[] = [
  { label: 'TechExperts', expertIds: ['ai_architect', 'neuraldeep', 'ilia_izmailov', 'polyakov'] },
  { label: 'Tech&BizExperts', expertIds: ['ai_grabli', 'refat', 'akimov', 'llm_under_hood', 'elkornacio', 'doronin'] },
];

/**
 * Get display name for expert (frontend override or fallback to backend name)
 */
const getDisplayName = (expert: ExpertInfo): string => {
  return DISPLAY_NAME_MAP[expert.expert_id] || expert.display_name;
};

/**
 * Grouped expert selection bar component
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
          {getDisplayName(expert)}
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

        return (
          <div key={group.label} className="expert-group-row">
            <span className="expert-group-label">{group.label}:</span>
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