import React from 'react';

// This could come from an API later
const AVAILABLE_EXPERTS = [
  { id: 'refat', name: 'Refat (Tech & AI)' },
  { id: 'ai_architect', name: 'AI Architect (AI Architecture)' },
  { id: 'neuraldeep', name: 'Neuraldeep (Deep Learning)' },
];

interface ExpertSelectorProps {
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
}

const ExpertSelector: React.FC<ExpertSelectorProps> = ({
  selectedExperts,
  onExpertsChange,
  disabled = false,
}) => {
  const handleCheckboxChange = (expertId: string) => {
    const newSelection = new Set(selectedExperts);
    if (newSelection.has(expertId)) {
      newSelection.delete(expertId);
    } else {
      newSelection.add(expertId);
    }
    onExpertsChange(newSelection);
  };

  return (
    <div style={styles.container}>
      <h4 style={styles.title}>Select experts for your query:</h4>
      {AVAILABLE_EXPERTS.map(expert => (
        <div key={expert.id} style={styles.checkboxRow}>
          <input
            type="checkbox"
            id={`expert-${expert.id}`}
            checked={selectedExperts.has(expert.id)}
            onChange={() => handleCheckboxChange(expert.id)}
            style={styles.checkbox}
            disabled={disabled}
          />
          <label htmlFor={`expert-${expert.id}`} style={styles.label}>
            {expert.name}
          </label>
        </div>
      ))}
    </div>
  );
};

const styles = {
  container: {
    padding: '10px',
    border: '1px solid #dee2e6',
    borderRadius: '8px',
    backgroundColor: '#f8f9fa',
    flexShrink: 0,
  },
  title: {
    marginTop: 0,
    marginBottom: '10px',
    fontSize: '14px',
    fontWeight: '600' as const,
  },
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    marginBottom: '5px',
  },
  checkbox: {
    marginRight: '8px',
  },
  label: {
    fontSize: '14px',
  },
};

export default ExpertSelector;