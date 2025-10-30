import React from 'react';

export interface Expert {
  id: string;
  name: string;
  description: string;
}

export const experts: Expert[] = [
  { id: 'refat', name: 'Refat', description: 'Tech & AI' },
  { id: 'ai_architect', name: 'AI Architect', description: 'AI Architecture' },
  { id: 'neuraldeep', name: 'Neuraldeep', description: 'Deep Learning' },
];

interface ExpertSelectorProps {
  selectedExperts: string[];
  onSelectionChange: (selected: string[]) => void;
}

export const ExpertSelector: React.FC<ExpertSelectorProps> = ({
  selectedExperts,
  onSelectionChange,
}) => {
  const handleCheckboxChange = (expertId: string) => {
    const newSelection = selectedExperts.includes(expertId)
      ? selectedExperts.filter((id) => id !== expertId)
      : [...selectedExperts, expertId];
    onSelectionChange(newSelection);
  };

  return (
    <div style={styles.container}>
      <div style={styles.expertsList}>
        {experts.map((expert) => (
          <label key={expert.id} style={styles.expertItem}>
            <input
              type="checkbox"
              checked={selectedExperts.includes(expert.id)}
              onChange={() => handleCheckboxChange(expert.id)}
              style={styles.checkbox}
            />
            {expert.name}
          </label>
        ))}
      </div>
    </div>
  );
};

const styles = {
  container: {
    paddingTop: '10px',
  },
  expertsList: {
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap' as const,
    alignItems: 'center',
  },
  expertItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    userSelect: 'none' as const,
  },
  checkbox: {
    cursor: 'pointer',
    width: '16px',
    height: '16px',
  },
};

export default ExpertSelector;