import React, { useState } from 'react';
import { ExpertInfo } from '../types/api';
import { EXPERT_GROUPS, getExpertDisplayName } from '../config/expertConfig';
import clsx from 'clsx';

interface SidebarProps {
  availableExperts: ExpertInfo[];
  selectedExperts: Set<string>;
  onExpertsChange: (selected: Set<string>) => void;
  useRecentOnly: boolean;
  onUseRecentOnlyChange: (value: boolean) => void;
  includeReddit: boolean;
  onIncludeRedditChange: (value: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  availableExperts,
  selectedExperts,
  onExpertsChange,
  useRecentOnly,
  onUseRecentOnlyChange,
  includeReddit,
  onIncludeRedditChange,
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
    // Remove "Tech_" or "Biz_" prefix if present
    const cleanName = name.replace(/^(Tech_|Biz_)/, '');
    
    // Split by underscore or space
    const parts = cleanName.split(/[_\s]+/);
    
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    } else {
      return cleanName.substring(0, 2).toUpperCase();
    }
  };

  return (
    <div 
      className={clsx(
        "flex flex-col bg-white text-gray-700 transition-all duration-300 ease-in-out border-r border-gray-200 shadow-sm z-20",
        isCollapsed ? "w-16" : "w-72",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-100 h-16 shrink-0">
        {!isCollapsed && (
          <span className="font-bold text-gray-800 tracking-wider text-sm uppercase">
            Experts Panel
          </span>
        )}
        <button 
          onClick={toggleSidebar}
          className={clsx(
            "p-1.5 rounded-md hover:bg-gray-100 text-gray-500 transition-colors",
            isCollapsed ? "mx-auto" : "ml-auto"
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
        
        {/* Search Options Section */}
        <div className={clsx("mb-6", isCollapsed ? "px-2" : "px-4")}>
          {!isCollapsed && (
            <div className="mb-3 text-xs font-bold text-gray-400 uppercase tracking-wider">
              Search Options
            </div>
          )}
          
          <div className="flex flex-col gap-2">
            {/* Recent Only Toggle */}
            <div 
              className={clsx(
                "flex items-center rounded-lg cursor-pointer transition-colors group",
                isCollapsed ? "justify-center p-2" : "px-3 py-2",
                useRecentOnly ? "bg-blue-50 text-blue-700" : "hover:bg-gray-50 text-gray-600"
              )}
              onClick={() => !disabled && onUseRecentOnlyChange(!useRecentOnly)}
              title={isCollapsed ? "Recent posts only (3 months)" : undefined}
            >
              <div className={clsx("shrink-0", isCollapsed ? "" : "mr-3")}>
                {useRecentOnly ? (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-gray-400 group-hover:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
              {!isCollapsed && (
                <div className="flex flex-col">
                  <span className="text-sm font-medium">Recent Only</span>
                  <span className="text-[10px] opacity-70">Last 3 months</span>
                </div>
              )}
              {/* Toggle Switch (Desktop) */}
              {!isCollapsed && (
                <div className={clsx(
                  "ml-auto w-9 h-5 rounded-full relative transition-colors duration-200 ease-in-out",
                  useRecentOnly ? "bg-blue-500" : "bg-gray-300"
                )}>
                  <div className={clsx(
                    "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out",
                    useRecentOnly ? "translate-x-4" : "translate-x-0"
                  )} />
                </div>
              )}
            </div>

            {/* Reddit Toggle */}
            <div 
              className={clsx(
                "flex items-center rounded-lg cursor-pointer transition-colors group",
                isCollapsed ? "justify-center p-2" : "px-3 py-2",
                includeReddit ? "bg-orange-50 text-orange-700" : "hover:bg-gray-50 text-gray-600"
              )}
              onClick={() => !disabled && onIncludeRedditChange(!includeReddit)}
              title={isCollapsed ? "Search Reddit" : undefined}
            >
              <div className={clsx("shrink-0", isCollapsed ? "" : "mr-3")}>
                {includeReddit ? (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-gray-400 group-hover:text-gray-500" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
                  </svg>
                )}
              </div>
              {!isCollapsed && (
                <div className="flex flex-col">
                  <span className="text-sm font-medium">Reddit</span>
                  <span className="text-[10px] opacity-70">Community</span>
                </div>
              )}
              {/* Toggle Switch (Desktop) */}
              {!isCollapsed && (
                <div className={clsx(
                  "ml-auto w-9 h-5 rounded-full relative transition-colors duration-200 ease-in-out",
                  includeReddit ? "bg-orange-500" : "bg-gray-300"
                )}>
                  <div className={clsx(
                    "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out",
                    includeReddit ? "translate-x-4" : "translate-x-0"
                  )} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Experts List */}
        {EXPERT_GROUPS.map((group) => {
          const groupExperts = group.expertIds
            .map(id => expertMap.get(id))
            .filter((e): e is ExpertInfo => e !== undefined);

          if (groupExperts.length === 0) return null;
          
          const allGroupSelected = groupExperts.every(e => selectedExperts.has(e.expert_id));

          return (
            <div key={group.label} className={clsx("mb-6", isCollapsed ? "px-2" : "px-4")}>
              {!isCollapsed && (
                <div 
                  onClick={() => handleToggleGroup(group.expertIds)}
                  className="px-3 mb-2 flex items-center justify-between cursor-pointer group/header hover:text-blue-600 transition-colors"
                  title="Click to toggle all"
                >
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-wider group-hover/header:text-blue-600">
                    {group.label}
                  </span>
                  <span className="text-[10px] text-gray-400 group-hover/header:text-blue-500">
                    {allGroupSelected ? 'Deselect' : 'Select'}
                  </span>
                </div>
              )}
              {isCollapsed && (
                <div 
                  className="w-full h-px bg-gray-200 my-3 mx-auto w-8 cursor-pointer hover:bg-gray-400" 
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
                        !isCollapsed && isSelected && "bg-blue-50 text-blue-700",
                        !isCollapsed && !isSelected && "hover:bg-gray-50 text-gray-600 hover:text-gray-900",
                        disabled && "opacity-50 cursor-not-allowed"
                      )}
                      title={displayName}
                    >
                      {/* Collapsed State: Avatar Circle */}
                      {isCollapsed ? (
                         <div className={clsx(
                           "w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold border transition-colors select-none",
                           isSelected 
                             ? "bg-blue-600 border-blue-500 text-white shadow-md shadow-blue-200" 
                             : "bg-gray-100 border-gray-200 text-gray-500 group-hover:border-gray-300 group-hover:text-gray-700"
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
                              : "border-gray-300 group-hover:border-gray-400 bg-white"
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
                              isSelected ? "text-gray-900" : "text-gray-600"
                            )}>
                              {displayName}
                            </span>
                            {expert.stats && (
                              <span className="text-[10px] text-gray-400">
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
                            className="ml-auto opacity-0 group-hover:opacity-100 text-gray-400 hover:text-blue-500 p-1"
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
      <div className="p-4 border-t border-gray-100 text-xs text-gray-400">
         {!isCollapsed ? (
           <div className="flex flex-col gap-1">
             <span>Gemini 2.5/3.0 Powered</span>
             <span>v2.1 Production</span>
           </div>
         ) : (
           <div className="text-center font-bold text-gray-300">AI</div>
         )}
      </div>
    </div>
  );
};