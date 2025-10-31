import React from 'react';
import ProgressSection from './ProgressSection';
import ExpertSelector from './ExpertSelector';
import { ProgressEvent } from '../types/api';

interface Stats {
  totalPosts: number;
  processingTime: number;
  expertCount: number;
}

interface StatsAndSelectorsProps {
  isProcessing: boolean;
  progressEvents: ProgressEvent[];
  stats?: Stats;
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
}

const StatsAndSelectors: React.FC<StatsAndSelectorsProps> = ({
  isProcessing,
  progressEvents,
  stats,
  selectedExperts,
  onExpertsChange,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '10px' }}>
      <ProgressSection
        isProcessing={isProcessing}
        progressEvents={progressEvents}
        stats={stats}
      />
      <ExpertSelector
        selectedExperts={selectedExperts}
        onExpertsChange={onExpertsChange}
        disabled={isProcessing}
      />
    </div>
  );
};

export default StatsAndSelectors;