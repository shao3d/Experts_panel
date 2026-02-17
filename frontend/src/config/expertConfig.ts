/**
 * Configuration for expert display names, order, and grouping in UI
 * This centralizes all UI-related expert configuration
 */

import { ExpertInfo } from '../types/api';

export interface ExpertUIConfig {
  displayNames: Record<string, string>;
  order: string[];
}

export interface ExpertGroup {
  label: string;
  expertIds: string[];
}

/**
 * Expert Groups Definition (Used in Sidebar and Mobile Selection)
 */
export const EXPERT_GROUPS: ExpertGroup[] = [
  { label: 'Tech', expertIds: ['ai_architect', 'neuraldeep', 'ilia_izmailov', 'polyakov', 'etechlead', 'glebkudr'] },
  { label: 'Tech & Business', expertIds: ['ai_grabli', 'refat', 'akimov', 'llm_under_hood', 'elkornacio', 'doronin', 'air_ai'] },
  { label: 'Knowledge Hub', expertIds: ['video_hub'] },
];

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
    'refat': 'Tech_Refat',
    'llm_under_hood': 'Rinat',
    'elkornacio': 'Elkornacio',
    'ilia_izmailov': 'Ilia',
    'polyakov': 'Polyakov',
    'doronin': 'Doronin',
    'etechlead': 'Etechlead',
    'glebkudr': 'Glebkudr',
    'video_hub': 'Video_Hub',
    'air_ai': 'Air'
  },
  // Order used for sorting results
  order: ['refat', 'ai_architect', 'neuraldeep', 'ai_grabli', 'akimov', 'llm_under_hood', 'elkornacio', 'ilia_izmailov', 'polyakov', 'doronin', 'etechlead', 'glebkudr', 'video_hub', 'air_ai']
};

/**
 * Helper to get display name for an expert
 */
export const getExpertDisplayName = (expertId: string, defaultName?: string): string => {
  // Try to find in custom mapping first
  if (EXPERT_UI_CONFIG.displayNames[expertId]) {
    // Clean up internal names for display if needed (e.g. remove "Tech_" prefix if desired, 
    // but for now we use the mapping as is)
    const mappedName = EXPERT_UI_CONFIG.displayNames[expertId];
    // Map specific short names for UI consistency if they differ from the config above
    // This allows using the full config names for sorting but shorter names for Sidebar
    const shortNames: Record<string, string> = {
      'Tech_AIarch': 'AI_Arch',
      'Tech_Kovalskii': 'Kovalskii',
      'Tech_AIgrabli': 'AI_Grabli',
      'Tech_Refat': 'Refat',
      'Biz_Akimov': 'Akimov'
    };
    return shortNames[mappedName] || mappedName;
  }
  return defaultName || expertId;
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