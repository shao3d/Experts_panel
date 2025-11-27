/**
 * Main application component.
 * Connects all components and manages query state.
 */

import React, { useState, useEffect } from 'react';
import { QueryForm } from './components/QueryForm';
import ExpertAccordion from './components/ExpertAccordion';
import ProgressSection from './components/ProgressSection';
import ExpertSelectionBar from './components/ExpertSelectionBar';
import { apiClient } from './services/api';
import { ExpertResponse as ExpertResponseType, ProgressEvent } from './types/api';
import './App.css';

interface ExpertInfo {
  expert_id: string;
  display_name: string;
  channel_username: string;
}

export const App: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [expertResponses, setExpertResponses] = useState<ExpertResponseType[]>([]);
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
    const loadAndOrderExperts = () => {
      // Define the final, ordered list of experts with their UI-facing names and data
      const orderedExperts: ExpertInfo[] = [
        { expert_id: 'refat', display_name: 'Tech_Refat', channel_username: 'nobilix' },
        { expert_id: 'ai_architect', display_name: 'Tech_aiArchitect', channel_username: 'the_ai_architect' },
        { expert_id: 'neuraldeep', display_name: 'Tech_Kovalskii', channel_username: 'neuraldeep' },
        { expert_id: 'akimov', display_name: 'Biz_Akimov', channel_username: 'ai_product' }
      ];

      setAvailableExperts(orderedExperts);
      
      // Initialize selection with all experts
      const allExpertIds = new Set(orderedExperts.map(e => e.expert_id));
      setSelectedExperts(allExpertIds);
      setExpandedExperts(allExpertIds);
    };

    loadAndOrderExperts();
  }, []);

  /**
   * Handle query submission
   */
  const handleQuerySubmit = async (query: string): Promise<void> => {
    // Reset state
    setIsProcessing(true);
    setProgressEvents([]);
    setExpertResponses([]);
    setError(null);
    setCurrentQuery(query);
    setIsExpertSelectorOpen(false); // Close selector on submit

    try {
      const experts = Array.from(selectedExperts);
      // Submit query with progress callback
      const response = await apiClient.submitQuery(
        { query, expert_filter: experts, stream_progress: true, include_comments: true, include_comment_groups: true },
        (event: ProgressEvent) => {
          // Add progress event to log
          setProgressEvents(prev => [...prev, event]);
        }
      );

      // Check if response has expert_responses (multi-expert) or is a legacy single response
      if (response.expert_responses && response.expert_responses.length > 0) {
        console.log('[DEBUG] Multi-expert response with', response.expert_responses.length, 'experts');
        setExpertResponses(response.expert_responses);
      } else if (response.answer) {
        // Fallback: convert legacy response to expert response format
        console.log('[DEBUG] Legacy single response, converting to expert format');
        const legacyExpert: ExpertResponseType = {
          expert_id: 'refat',
          expert_name: 'Refat (Tech & AI)',
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
    <div className="app-container">
      {/* Mobile: Sticky Header for Progress */}
      <div className="mobile-header mobile-only">
        <ProgressSection
          isProcessing={isProcessing}
          progressEvents={progressEvents}
          stats={expertResponses.length > 0 ? getTotalStats() : undefined}
        />
      </div>

      {/* Desktop: Top Section */}
      <div className="top-section desktop-only">
        <div className="query-container">
          <QueryForm
            onSubmit={handleQuerySubmit}
            disabled={isProcessing}
            elapsedSeconds={elapsedSeconds}
            selectedExperts={selectedExperts}
          />
        </div>

        <div className="progress-container">
          <ProgressSection
            isProcessing={isProcessing}
            progressEvents={progressEvents}
            stats={expertResponses.length > 0 ? getTotalStats() : undefined}
          />
        </div>
      </div>

      {/* Desktop: Expert Selection Bar */}
      <div className="expert-bar-container desktop-only">
        <ExpertSelectionBar
          availableExperts={availableExperts}
          selectedExperts={selectedExperts}
          onExpertsChange={setSelectedExperts}
          disabled={isProcessing}
        />
      </div>

      {/* Main Content Area - Expert Accordions */}
      <div className="main-content">
        <div className="accordion-container">
          {error ? (
            <div className="error-message">
              <h3>⚠️ Error</h3>
              <p>{error}</p>
            </div>
          ) : expertResponses.length > 0 ? (
            [...expertResponses]
              .sort((a, b) => {
                // Refat always first
                if (a.expert_id === 'refat') return -1;
                if (b.expert_id === 'refat') return 1;
                // Others alphabetically
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
              ))
          ) : (
            <div className="empty-placeholder">
              {isProcessing ? 'Stages query...' : 'Experts answers will appear here'}
            </div>
          )}
        </div>
      </div>

      {/* Mobile: Sticky Footer */}
      <div className="mobile-footer mobile-only">
        {/* Expert Selector Toggle Strip */}
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

        {/* Collapsible Expert List */}
        <div className={`mobile-expert-selector ${isExpertSelectorOpen ? 'open' : ''}`}>
          <ExpertSelectionBar
            availableExperts={availableExperts}
            selectedExperts={selectedExperts}
            onExpertsChange={setSelectedExperts}
            disabled={isProcessing}
          />
        </div>
        
        {/* Always Visible Query Form */}
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
  );
};

export default App;
