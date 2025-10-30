/**
 * Main application component.
 * Connects all components and manages query state.
 */

import React, { useState, useEffect } from 'react';
import { QueryForm } from './components/QueryForm';
import ExpertAccordion from './components/ExpertAccordion';
import ProgressSection from './components/ProgressSection';
import { apiClient } from './services/api';
import { ExpertResponse as ExpertResponseType, ProgressEvent } from './types/api';
import { experts } from './components/ExpertSelector';

export const App: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [expertResponses, setExpertResponses] = useState<ExpertResponseType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedExperts, setExpandedExperts] = useState<Set<string>>(new Set(['refat', 'ai_architect', 'neuraldeep']));
  const [currentQuery, setCurrentQuery] = useState<string>('');
  const [selectedExperts, setSelectedExperts] = useState<string[]>(
    experts.map(e => e.id)
  );

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

    try {
      // Submit query with progress callback
      const response = await apiClient.submitQuery(
        {
          query,
          stream_progress: true,
          include_comments: true,
          include_comment_groups: true,
          expert_filter: selectedExperts
        },
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
    <div style={styles.container}>
      {/* Top Section - Query & Progress */}
      <div style={styles.topSection}>
        <div style={styles.queryContainer}>
          <QueryForm
            onSubmit={handleQuerySubmit}
            disabled={isProcessing}
            elapsedSeconds={elapsedSeconds}
            selectedExperts={selectedExperts}
            onExpertsChange={setSelectedExperts}
          />
        </div>

        <div style={styles.progressContainer}>
          <ProgressSection
            isProcessing={isProcessing}
            progressEvents={progressEvents}
            stats={expertResponses.length > 0 ? getTotalStats() : undefined}
          />
        </div>
      </div>

      {/* Main Content Area - Expert Accordions */}
      <div style={styles.mainContent}>
        <div style={styles.accordionContainer}>
          {error ? (
            <div style={styles.error}>
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
            <div style={styles.placeholder}>
              {isProcessing ? 'Stages query...' : 'Experts answers will appear here'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Two-column layout styles
const styles = {
  container: {
    height: '100vh',
    display: 'flex',
    flexDirection: 'column' as const,
    backgroundColor: '#f5f5f5',
    overflow: 'hidden'
  },
  topSection: {
    height: '180px',
    display: 'flex',
    gap: '20px',
    padding: '20px',
    backgroundColor: 'white',
    borderBottom: '1px solid #dee2e6'
  },
  queryContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '10px',
    overflow: 'visible'
  },
  progressContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '10px',
    overflow: 'hidden'
  },
  mainContent: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '20px',
    backgroundColor: '#f5f5f5'
  },
  accordionContainer: {
    maxWidth: '1400px',
    margin: '0 auto',
    width: '100%'
  },
  error: {
    padding: '20px',
    backgroundColor: '#ffe0e0',
    border: '2px solid #ff6b6b',
    borderRadius: '8px'
  },
  placeholder: {
    padding: '40px',
    textAlign: 'center' as const,
    color: '#6c757d',
    fontSize: '16px'
  }
};

export default App;
