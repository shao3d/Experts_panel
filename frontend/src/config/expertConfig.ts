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
 * Source-of-truth for experts hidden from UI selection surfaces
 * (Sidebar, Mobile drawer, and default selection set).
 *
 * - Hidden ids are NOT rendered in any selection group.
 * - Hidden ids are NOT included in the default-selected set on app boot.
 * - Backend is NOT affected: requests that explicitly target a hidden expert
 *   (e.g. via URL/API) still work, since the backend pipeline is unchanged.
 *
 * Add an id here to hide it everywhere; remove it to restore.
 */
export const HIDDEN_EXPERT_IDS: ReadonlySet<string> = new Set(['video_hub']);

export const isExpertHidden = (expertId: string): boolean =>
  HIDDEN_EXPERT_IDS.has(expertId);

/**
 * Expert Groups Definition (Used in Sidebar and Mobile Selection)
 */
export const EXPERT_GROUPS: ExpertGroup[] = [
  { label: 'Tech', expertIds: ['ai_architect', 'neuraldeep', 'ilia_izmailov', 'polyakov', 'etechlead', 'rodion_mostovoy', 'glebkudr', 'ostrikov', 'pashazloy', 'sergei_notevskii', 'deksden_notes'] },
  { label: 'Tech & Business', expertIds: ['ai_grabli', 'refat', 'akimov', 'llm_under_hood', 'elkornacio', 'doronin', 'vlad_kooklev', 'air_ai', 'silicbag', 'kornish', 'aimasters_me'] },
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
    'vlad_kooklev': 'Kooklev',
    'etechlead': 'Etechlead',
    'rodion_mostovoy': 'Rodion',
    'glebkudr': 'Glebkudr',
    'video_hub': 'Video_Hub',
    'air_ai': 'Air',
    'ostrikov': 'Ostrikov',
    'silicbag': 'SilicBag',
    'kornish': 'Kornishev',
    'pashazloy': 'PashaZloy',
    'aimasters_me': 'Aimasters',
    'sergei_notevskii': 'Notevskii',
    'deksden_notes': 'DEKSDEN'
  },
  // Order used for sorting results
  order: ['refat', 'ai_architect', 'neuraldeep', 'ai_grabli', 'akimov', 'llm_under_hood', 'elkornacio', 'ilia_izmailov', 'polyakov', 'doronin', 'vlad_kooklev', 'etechlead', 'rodion_mostovoy', 'glebkudr', 'air_ai', 'ostrikov', 'silicbag', 'kornish', 'pashazloy', 'aimasters_me', 'sergei_notevskii', 'deksden_notes', 'video_hub']
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
