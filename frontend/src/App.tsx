/**
 * Main application component.
 * Connects all components and manages query state.
 */

import React, { useState, useEffect } from 'react';
import { QueryForm } from './components/QueryForm';
import ExpertAccordion from './components/ExpertAccordion';
import ProgressSection from './components/ProgressSection';
import ExpertSelectionBar from './components/ExpertSelectionBar'; // Kept for Mobile
import { Sidebar } from './components/Sidebar'; // New Desktop Sidebar
import CommunityInsightsSection from './components/CommunityInsightsSection';
import { apiClient } from './services/api';
import { ExpertResponse as ExpertResponseType, ProgressEvent, ExpertInfo, RedditResponse } from './types/api';
import { transformExpertsForUI, EXPERT_UI_CONFIG } from './config/expertConfig';
import './App.css';
import './components/CommunityInsightsSection.css';

export const App: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [expertResponses, setExpertResponses] = useState<ExpertResponseType[]>([]);
  const [redditResponse, setRedditResponse] = useState<RedditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [availableExperts, setAvailableExperts] = useState<ExpertInfo[]>([]);
  const [expandedExperts, setExpandedExperts] = useState<Set<string>>(new Set());
  const [currentQuery, setCurrentQuery] = useState<string>('');
  const [selectedExperts, setSelectedExperts] = useState<Set<string>>(new Set());
  
  // Mobile Expert Selector Drawer State
  const [isExpertSelectorOpen, setIsExpertSelectorOpen] = useState(false);

  // Timer state for processing time
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Timer management
  useEffect(() => {
    if (isProcessing && !startTime) {
      setStartTime(Date.now());
    }
    if (!isProcessing) {
      setStartTime(null);
      setElapsedSeconds(0);
    }
  }, [isProcessing]);

  useEffect(() => {
    if (!isProcessing || !startTime) return;

    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [isProcessing, startTime]);

  // Load experts from API on mount
  useEffect(() => {
    const loadExperts = async () => {
      try {
        console.log('[App] Loading experts from API...');
        const experts = await apiClient.getExperts();
        console.log('[App] Loaded experts:', experts);

        // Transform experts for UI display
        const transformedExperts = transformExpertsForUI(experts);
        console.log('[App] Transformed experts for UI:', transformedExperts);

        setAvailableExperts(transformedExperts);

        // Initialize selection with all experts
        const allExpertIds = new Set(transformedExperts.map(e => e.expert_id));
        setSelectedExperts(allExpertIds);
        setExpandedExperts(allExpertIds);
      } catch (err) {
        console.error('[App] Failed to load experts:', err);
        setError('Failed to load experts list. Please refresh the page.');
      }
    };

    loadExperts();
  }, []);

  /**
   * Handle query submission
   */
  const handleQuerySubmit = async (query: string, options?: { use_recent_only?: boolean; include_reddit?: boolean }): Promise<void> => {
    // Reset state
    setIsProcessing(true);
    setProgressEvents([]);
    setExpertResponses([]);
    setRedditResponse(null);
    setError(null);
    setCurrentQuery(query);
    setIsExpertSelectorOpen(false); // Close selector on submit

    try {
      const experts = Array.from(selectedExperts);
      // Submit query with progress callback
      const response = await apiClient.submitQuery(
        { query, expert_filter: experts, stream_progress: true, include_comments: true, include_comment_groups: true, use_recent_only: options?.use_recent_only, include_reddit: options?.include_reddit },
        (event: ProgressEvent) => {
          // Add progress event to log
          setProgressEvents(prev => [...prev, event]);
        }
      );

      // Set Reddit response if available
      if (response.reddit_response) {
        setRedditResponse(response.reddit_response);
      }

      // Check if response has expert_responses (multi-expert)
      if (response.expert_responses !== undefined) {
        console.log('[DEBUG] Multi-expert response with', response.expert_responses.length, 'experts');
        setExpertResponses(response.expert_responses);
        
        // If no experts and no reddit, show error from answer if present
        if (response.expert_responses.length === 0 && !response.reddit_response && response.answer) {
             setError(response.answer);
        }
      } else if (response.answer) {
        // Fallback: convert legacy response to expert response format
        console.log('[DEBUG] Legacy single response, converting to expert format');
        const legacyExpert: ExpertResponseType = {
          expert_id: 'refat',
          expert_name: 'Tech_Refat',
          channel_username: 'nobilix',
          answer: response.answer,
          main_sources: response.main_sources || [],
          confidence: response.confidence || 'LOW',
          posts_analyzed: response.posts_analyzed || 0,
          processing_time_ms: response.processing_time_ms || 0,
          relevant_comment_groups: response.relevant_comment_groups || [],
          comment_groups_synthesis: response.comment_groups_synthesis
        };
        setExpertResponses([legacyExpert]);
      } else {
        console.log('[DEBUG] No valid response:', response);
        setError('Failed to get experts response');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);
      console.error('Query failed:', err);
    } finally {
      setIsProcessing(false);
    }
  };

  /**
   * Toggle expert accordion
   */
  const handleToggleExpert = (expertId: string): void => {
    setExpandedExperts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(expertId)) {
        newSet.delete(expertId);
      } else {
        newSet.add(expertId);
      }
      return newSet;
    });
  };

  /**
   * Calculate total statistics across all experts
   */
  const getTotalStats = () => {
    const totalPosts = expertResponses.reduce((sum, expert) => sum + expert.posts_analyzed, 0);
    const processingTime = Math.max(...expertResponses.map(e => e.processing_time_ms || 0)) / 1000;
    const expertCount = expertResponses.length;
    return { totalPosts, processingTime, expertCount };
  };

  return (
    // Main Container with Sidebar Layout
    <div className="flex h-screen overflow-hidden bg-gray-50">
      
      {/* 1. Desktop Sidebar (Hidden on Mobile) */}
      <div className="hidden md:flex shrink-0 z-20 h-full">
        <Sidebar 
          availableExperts={availableExperts}
          selectedExperts={selectedExperts}
          onExpertsChange={setSelectedExperts}
          disabled={isProcessing}
        />
      </div>

      {/* 2. Main Content Area (Flex Column) */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative w-full">
        
        {/* Mobile Header (Original) */}
        <div className="mobile-header mobile-only md:hidden">
          <ProgressSection
            isProcessing={isProcessing}
            progressEvents={progressEvents}
            stats={expertResponses.length > 0 ? getTotalStats() : undefined}
          />
        </div>

        {/* Desktop Top Section (Query + Progress) */}
        <div className="hidden md:flex flex-shrink-0 bg-white border-b border-gray-200 p-5 gap-5 min-h-[160px] h-auto">
           <div className="flex-1 flex flex-col gap-2 overflow-visible">
              <QueryForm
                onSubmit={handleQuerySubmit}
                disabled={isProcessing}
                elapsedSeconds={elapsedSeconds}
                selectedExperts={selectedExperts}
              />
           </div>
           <div className="flex-1 flex flex-col gap-2 overflow-hidden">
              <ProgressSection
                isProcessing={isProcessing}
                progressEvents={progressEvents}
                stats={expertResponses.length > 0 ? getTotalStats() : undefined}
              />
           </div>
        </div>

        {/* Scrollable Results Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6" id="main-scroll-container">
           <div className="max-w-[1600px] mx-auto w-full pb-24 md:pb-10">
              {error ? (
                <div className="p-5 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  <h3 className="font-bold mb-2">⚠️ Error</h3>
                  <p>{error}</p>
                </div>
              ) : expertResponses.length > 0 || redditResponse ? (
                <>
                  {/* Expert Responses */}
                  {[...expertResponses]
                    .sort((a, b) => {
                      const uiOrder = EXPERT_UI_CONFIG.order;
                      const aIndex = uiOrder.indexOf(a.expert_id);
                      const bIndex = uiOrder.indexOf(b.expert_id);
                      if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
                      if (aIndex !== -1) return -1;
                      if (bIndex !== -1) return 1;
                      return a.expert_id.localeCompare(b.expert_id);
                    })
                    .map((expert) => (
                      <ExpertAccordion
                        key={expert.expert_id}
                        expert={expert}
                        isExpanded={expandedExperts.has(expert.expert_id)}
                        onToggle={() => handleToggleExpert(expert.expert_id)}
                        query={currentQuery}
                      />
                    ))}
                  
                  {/* Reddit Insights */}
                  <CommunityInsightsSection
                    redditResponse={redditResponse}
                    isLoading={isProcessing}
                  />
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                  <p className="text-lg">{isProcessing ? 'Processing query...' : 'Expert answers and community insights will appear here'}</p>
                </div>
              )}
           </div>
        </main>

        {/* Mobile Footer (Original) */}
        <div className="mobile-footer mobile-only md:hidden">
          <div 
            className="expert-toggle-bar"
            onClick={() => setIsExpertSelectorOpen(!isExpertSelectorOpen)}
          >
            <span>
              Select Experts ({selectedExperts.size}/{availableExperts.length})
            </span>
            <span className="toggle-icon">
              {isExpertSelectorOpen ? '▼' : '▲'}
            </span>
          </div>

          <div className={`mobile-expert-selector ${isExpertSelectorOpen ? 'open' : ''}`}>
            <ExpertSelectionBar
              availableExperts={availableExperts}
              selectedExperts={selectedExperts}
              onExpertsChange={setSelectedExperts}
              disabled={isProcessing}
            />
          </div>
          
          <div className="mobile-query-form-container">
            <QueryForm
              onSubmit={handleQuerySubmit}
              disabled={isProcessing}
              elapsedSeconds={elapsedSeconds}
              selectedExperts={selectedExperts}
            />
          </div>
        </div>

      </div>
    </div>
  );
};

export default App;
