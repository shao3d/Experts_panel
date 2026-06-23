/**
 * Main application component.
 * Connects all components and manages query state.
 */

import React, { useState, useEffect, Suspense, useRef } from 'react';
import { QueryForm } from './components/QueryForm';
import ExpertAccordion from './components/ExpertAccordion';
import ProgressSection from './components/ProgressSection';
import QueryDeck from './components/QueryDeck';
// PixelMascot removed — no pixel office on mobile
import { useMediaQuery } from './utils/useMediaQuery';
import ExpertSelectionBar from './components/ExpertSelectionBar'; // Kept for Mobile
import { Sidebar } from './components/Sidebar'; // New Desktop Sidebar
import CommunityInsightsSection from './components/CommunityInsightsSection';
import { apiClient } from './services/api';
import { ExpertResponse as ExpertResponseType, ProgressEvent, ExpertInfo, RedditResponse } from './types/api';
import { MetaSynthesisSection } from './components/MetaSynthesisSection';
import { transformExpertsForUI, EXPERT_UI_CONFIG } from './config/expertConfig';
import './components/CommunityInsightsSection.css';
import './App.css';

const PixelOffice = React.lazy(() => import('./components/PixelOffice'));

class PixelOfficeErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

export const App: React.FC = () => {
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [expertResponses, setExpertResponses] = useState<ExpertResponseType[]>([]);
  const [redditResponse, setRedditResponse] = useState<RedditResponse | null>(null);
  const [metaSynthesis, setMetaSynthesis] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [availableExperts, setAvailableExperts] = useState<ExpertInfo[]>([]);
  const [expandedExperts, setExpandedExperts] = useState<Set<string>>(new Set());
  const [currentQuery, setCurrentQuery] = useState<string>('');
  const [selectedExperts, setSelectedExperts] = useState<Set<string>>(new Set());
  const [queryResetToken, setQueryResetToken] = useState(0);
  const queryAbortControllerRef = useRef<AbortController | null>(null);
  const activeQueryRunRef = useRef(0);
  
  // Search Options State (Lifted from QueryForm)
  const [useRecentOnly, setUseRecentOnly] = useState(false);
  const [includeReddit, setIncludeReddit] = useState(true);
  const [useSuperPassport, setUseSuperPassport] = useState(true);
  
  // Mobile Expert Selector Drawer State
  const [isExpertSelectorOpen, setIsExpertSelectorOpen] = useState(false);

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
  const handleQuerySubmit = async (query: string): Promise<void> => {
    queryAbortControllerRef.current?.abort();
    const queryRunId = activeQueryRunRef.current + 1;
    activeQueryRunRef.current = queryRunId;
    const abortController = new AbortController();
    queryAbortControllerRef.current = abortController;

    // Reset state
    setIsProcessing(true);
    setProgressEvents([]);
    setExpertResponses([]);
    setRedditResponse(null);
    setMetaSynthesis(null);
    setError(null);
    setCurrentQuery(query);
    setIsExpertSelectorOpen(false); // Close selector on submit

    try {
      const experts = Array.from(selectedExperts);
      // Submit query with progress callback
      const response = await apiClient.submitQuery(
        { query, expert_filter: experts, stream_progress: true, include_comments: true, include_comment_groups: true, use_recent_only: useRecentOnly, include_reddit: includeReddit, use_super_passport: useSuperPassport },
        (event: ProgressEvent) => {
          if (abortController.signal.aborted || activeQueryRunRef.current !== queryRunId) {
            return;
          }
          // Add progress event to log
          setProgressEvents(prev => [...prev, event]);
        },
        abortController.signal
      );

      if (abortController.signal.aborted || activeQueryRunRef.current !== queryRunId) {
        return;
      }

      // Set Reddit response if available
      if (response.reddit_response) {
        setRedditResponse(response.reddit_response);
      }

      // Set Meta-Synthesis if available
      if (response.meta_synthesis) {
        setMetaSynthesis(response.meta_synthesis);
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
      if (
        abortController.signal.aborted ||
        activeQueryRunRef.current !== queryRunId ||
        (err instanceof Error && err.name === 'AbortError')
      ) {
        return;
      }

      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);
      console.error('Query failed:', err);
    } finally {
      if (activeQueryRunRef.current === queryRunId) {
        setIsProcessing(false);
        queryAbortControllerRef.current = null;
      }
    }
  };

  /**
   * Stop active query and reset the query surface for a fresh question.
   */
  const handleStopQuery = (): void => {
    activeQueryRunRef.current += 1;
    queryAbortControllerRef.current?.abort();
    queryAbortControllerRef.current = null;

    setIsProcessing(false);
    setProgressEvents([]);
    setExpertResponses([]);
    setRedditResponse(null);
    setMetaSynthesis(null);
    setError(null);
    setCurrentQuery('');
    setIsExpertSelectorOpen(false);
    setQueryResetToken(token => token + 1);
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
    <div className="experts-app-shell flex h-screen overflow-hidden">
      
      {/* 1. Desktop Sidebar (Hidden on Mobile) */}
      <div className="hidden md:flex shrink-0 z-20 h-full">
        <Sidebar
          availableExperts={availableExperts}
          selectedExperts={selectedExperts}
          onExpertsChange={setSelectedExperts}
          useRecentOnly={useRecentOnly}
          onUseRecentOnlyChange={setUseRecentOnly}
          includeReddit={includeReddit}
          onIncludeRedditChange={setIncludeReddit}
          useSuperPassport={useSuperPassport}
          onUseSuperPassportChange={setUseSuperPassport}
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
        <div className="hidden md:block flex-shrink-0">
          <QueryDeck
            onSubmit={handleQuerySubmit}
            disabled={isProcessing}
            selectedExperts={selectedExperts}
            hasRedditEnabled={includeReddit}
            progressEvents={progressEvents}
            stats={expertResponses.length > 0 ? getTotalStats() : undefined}
            currentQuery={currentQuery}
            error={error}
            onStop={handleStopQuery}
          />
        </div>

        {/* Scrollable Results Area */}
        <main className="experts-main-scroll flex-1 overflow-y-auto p-4 md:p-6" id="main-scroll-container">
           <div className="experts-content-frame max-w-[1600px] mx-auto w-full pb-24 md:pb-10">

              {/* Pixel Office — desktop only, hidden on mobile */}
              {isDesktop && (
                <PixelOfficeErrorBoundary>
                <Suspense fallback={<div className="rounded-lg mb-4 animate-pulse" style={{ height: 360 }} />}>
                  <PixelOffice
                    selectedExperts={selectedExperts}
                    progressEvents={progressEvents}
                    isProcessing={isProcessing}
                  />
                </Suspense>
                </PixelOfficeErrorBoundary>
              )}

              {error ? (
                <div className="app-error-panel p-5">
                  <h3 className="font-bold mb-2">⚠️ Error</h3>
                  <p>{error}</p>
                </div>
              ) : expertResponses.length > 0 || redditResponse ? (
                <>
                  {/* Meta-Synthesis: Cross-expert unified analysis */}
                  {metaSynthesis && (
                    <MetaSynthesisSection
                      metaSynthesis={metaSynthesis}
                      expertCount={expertResponses.length}
                    />
                  )}

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
                    isEnabled={includeReddit}
                  />
                </>
              ) : null}
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
             {/* Simple filter toggles for mobile inside the drawer */}
             <div className="p-4 border-t border-gray-100 flex flex-col gap-3">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={useSuperPassport} onChange={e => setUseSuperPassport(e.target.checked)} disabled={isProcessing} className="w-4 h-4 accent-yellow-500"/>
                  <span className="text-sm font-medium text-gray-700">Embs&amp;Keys Search</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={useRecentOnly} onChange={e => setUseRecentOnly(e.target.checked)} disabled={isProcessing} className="w-4 h-4 accent-blue-600"/>
                  <span className="text-sm font-medium text-gray-700">Recent Only (3m)</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={includeReddit} onChange={e => setIncludeReddit(e.target.checked)} disabled={isProcessing} className="w-4 h-4 accent-orange-600"/>
                  <span className="text-sm font-medium text-gray-700">Search Reddit</span>
                </label>
             </div>
          </div>
          
          <div className="mobile-query-form-container">
            <QueryForm
              onSubmit={handleQuerySubmit}
              disabled={isProcessing}
              selectedExperts={selectedExperts}
              hasRedditEnabled={includeReddit}
              onStop={handleStopQuery}
              resetToken={queryResetToken}
            />
          </div>
        </div>

      </div>
    </div>
  );
};

export default App;
