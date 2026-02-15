import React, { useState } from 'react';
import { ExpertInfo } from '../types/api';
import { EXPERT_GROUPS, getExpertDisplayName } from '../config/expertConfig';
import clsx from 'clsx';

interface SidebarProps {
  availableExperts: ExpertInfo[];
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  disabled?: boolean;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  availableExperts,
  selectedExperts,
  onExpertsChange,
  disabled = false,
  className
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const expertMap = new Map(availableExperts.map(e => [e.expert_id, e]));

  const handleToggleExpert = (expertId: string) => {
    if (disabled) return;
    const newSelected = new Set(selectedExperts);
    if (newSelected.has(expertId)) {
      newSelected.delete(expertId);
    } else {
      newSelected.add(expertId);
    }
    onExpertsChange(newSelected);
  };

  const toggleSidebar = () => setIsCollapsed(!isCollapsed);

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

  const getInitials = (name: string) => {
    // Remove "Tech_" or "Biz_" prefix if present (though displayName usually handles this)
    const cleanName = name.replace(/^(Tech_|Biz_)/, '');
    
    // Split by underscore or space
    const parts = cleanName.split(/[_\s]+/);
    
    if (parts.length >= 2) {
      // "AI Arch" -> "AA"
      return (parts[0][0] + parts[1][0]).toUpperCase();
    } else {
      // "Refat" -> "Re"
      return cleanName.substring(0, 2).toUpperCase();
    }
  };

  return (
    <div 
      className={clsx(
        "flex flex-col bg-gray-900 text-gray-300 transition-all duration-300 ease-in-out border-r border-gray-800 shadow-xl z-20",
        isCollapsed ? "w-16" : "w-72",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-center p-4 border-b border-gray-800 h-16 shrink-0 relative">
        {!isCollapsed && (
          <span className="font-bold text-white tracking-wider text-sm uppercase absolute left-4">
            Experts Panel
          </span>
        )}
        <button 
          onClick={toggleSidebar}
          className={clsx(
            "p-1.5 rounded-md hover:bg-gray-800 text-gray-400 transition-colors",
            !isCollapsed && "ml-auto"
          )}
          title={isCollapsed ? "Expand" : "Collapse"}
        >
          {isCollapsed ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="13 17 18 12 13 7"></polyline><polyline points="6 17 11 12 6 7"></polyline></svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="11 17 6 12 11 7"></polyline><polyline points="18 17 13 12 18 7"></polyline></svg>
          )}
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-4 custom-scrollbar">
        {EXPERT_GROUPS.map((group) => {
          const groupExperts = group.expertIds
            .map(id => expertMap.get(id))
            .filter((e): e is ExpertInfo => e !== undefined);

          if (groupExperts.length === 0) return null;
          
          const allGroupSelected = groupExperts.every(e => selectedExperts.has(e.expert_id));
          const someGroupSelected = groupExperts.some(e => selectedExperts.has(e.expert_id));

          return (
            <div key={group.label} className={clsx("mb-6", isCollapsed ? "px-2" : "px-3")}>
              {!isCollapsed && (
                <div 
                  onClick={() => handleToggleGroup(group.expertIds)}
                  className="px-3 mb-2 flex items-center justify-between cursor-pointer group/header hover:text-white transition-colors"
                  title="Click to toggle all"
                >
                  <span className="text-xs font-bold text-gray-500 uppercase tracking-wider group-hover/header:text-gray-300">
                    {group.label}
                  </span>
                  <span className="text-[10px] text-gray-600 group-hover/header:text-gray-400">
                    {allGroupSelected ? 'All' : someGroupSelected ? 'Some' : 'None'}
                  </span>
                </div>
              )}
              {isCollapsed && (
                <div 
                  className="w-8 h-px bg-gray-800 my-3 mx-auto cursor-pointer hover:bg-gray-600" 
                  title={`Toggle ${group.label}`}
                  onClick={() => handleToggleGroup(group.expertIds)}
                />
              )}
              
              <div className="space-y-1">
                {groupExperts.map((expert) => {
                  const isSelected = selectedExperts.has(expert.expert_id);
                  const displayName = getExpertDisplayName(expert.expert_id, expert.display_name);
                  
                  return (
                    <div 
                      key={expert.expert_id}
                      onClick={() => handleToggleExpert(expert.expert_id)}
                      className={clsx(
                        "group flex items-center rounded-lg cursor-pointer transition-all duration-200 relative",
                        isCollapsed ? "justify-center p-2" : "px-3 py-2",
                        !isCollapsed && isSelected && "bg-blue-600/20 text-blue-400",
                        !isCollapsed && !isSelected && "hover:bg-gray-800 text-gray-400 hover:text-gray-200",
                        disabled && "opacity-50 cursor-not-allowed"
                      )}
                      title={displayName}
                    >
                      {/* Collapsed State: Avatar Circle */}
                      {isCollapsed ? (
                         <div className={clsx(
                           "w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold border transition-colors select-none",
                           isSelected 
                             ? "bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-900/50" 
                             : "bg-gray-800 border-gray-700 text-gray-500 group-hover:border-gray-500 group-hover:text-gray-300"
                         )}>
                           {getInitials(displayName)}
                         </div>
                      ) : (
                        /* Expanded State: Checkbox + Name */
                        <>
                          <div className={clsx(
                            "shrink-0 flex items-center justify-center border rounded transition-colors w-4 h-4 mr-3",
                            isSelected 
                              ? "bg-blue-600 border-blue-600" 
                              : "border-gray-600 group-hover:border-gray-500 bg-transparent"
                          )}>
                            {isSelected && (
                              <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>

                          <div className="flex flex-col truncate">
                            <span className={clsx(
                              "text-sm font-medium truncate",
                              isSelected ? "text-white" : "text-gray-300"
                            )}>
                              {displayName}
                            </span>
                            {expert.stats && (
                              <span className="text-[10px] text-gray-600">
                                {expert.stats.posts_count} posts
                              </span>
                            )}
                          </div>
                          
                          {/* Telegram Link */}
                          <a
                            href={`https://t.me/${expert.channel_username}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="ml-auto opacity-0 group-hover:opacity-100 text-gray-500 hover:text-blue-400 p-1"
                            title="Open Telegram"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                              <polyline points="15 3 21 3 21 9"></polyline>
                              <line x1="10" y1="14" x2="21" y2="3"></line>
                            </svg>
                          </a>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
         {!isCollapsed ? (
           <div className="flex flex-col gap-1">
             <span>Gemini 2.5/3.0 Powered</span>
             <span>v2.1 Production</span>
           </div>
         ) : (
           <div className="text-center font-bold">AI</div>
         )}
      </div>
    </div>
  );
};