/**
 * Configuration for expert display names and order in UI
 * This maps backend expert IDs to UI display names and defines the order
 */

import { ExpertInfo } from '../types/api';

export interface ExpertUIConfig {
  displayNames: Record<string, string>;
  order: string[];
}

/**
 * UI Configuration for Experts Panel
 * Maps backend expert IDs to display names and defines visual order
 */
export const EXPERT_UI_CONFIG: ExpertUIConfig = {
  displayNames: {
    'ai_architect': 'Tech_AIarch',
    'ai_grabli': 'Tech_AIgrabli',
    'akimov': 'Biz_Akimov',
    'neuraldeep': 'Tech_Kovalskii',
    'refat': 'Tech_Refat'
  },
  order: ['refat', 'ai_architect', 'neuraldeep', 'ai_grabli', 'akimov']
};

/**
 * Transform experts list from API to UI representation
 * Applies display name mapping and orders according to UI configuration
 *
 * @param experts - Raw experts list from API
 * @returns Transformed experts list for UI display
 */
export function transformExpertsForUI(experts: ExpertInfo[]): ExpertInfo[] {
  const config = EXPERT_UI_CONFIG;

  // Get experts in the configured order, filtering out any that don't exist
  const orderedExperts = config.order
    .filter(expertId => experts.some(e => e.expert_id === expertId))
    .map(expertId => {
      const expert = experts.find(e => e.expert_id === expertId)!;
      return {
        ...expert,
        display_name: config.displayNames[expertId] || expert.display_name
      };
    });

  // Add any experts not in the configuration (for future compatibility)
  const remainingExperts = experts
    .filter(expert => !config.order.includes(expert.expert_id))
    .map(expert => ({
      ...expert,
      display_name: config.displayNames[expert.expert_id] || expert.display_name
    }));

  return [...orderedExperts, ...remainingExperts];
}