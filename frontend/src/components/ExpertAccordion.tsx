/**
 * Accordion component for displaying single expert's results.
 * Contains two columns: answer on the left, posts on the right.
 */

import React, { useState, useEffect } from 'react';
import ExpertResponse from './ExpertResponse';
import PostsList from './PostsList';
import { CommentGroupsList } from './CommentGroupsList';
import CommentSynthesis from './CommentSynthesis';
import { apiClient, isEnglishQuery } from '../services/api';
import { ExpertResponse as ExpertResponseType, PostDetailResponse } from '../types/api';

interface PostWithRelevance extends PostDetailResponse {
  relevance_score?: 'HIGH' | 'MEDIUM' | 'LOW' | null;
}

interface ExpertAccordionProps {
  expert: ExpertResponseType;
  isExpanded: boolean;
  onToggle: () => void;
  query?: string;
}

const ExpertAccordion: React.FC<ExpertAccordionProps> = ({
  expert,
  isExpanded,
  onToggle,
  query
}) => {
  const [posts, setPosts] = useState<PostWithRelevance[]>([]);
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
  const [postsLoading, setPostsLoading] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationProgress, setTranslationProgress] = useState({
    current: 0,
    total: 0
  });
  // Mobile source toggle state
  const [showMobileSources, setShowMobileSources] = useState(false);

  /**
   * Load posts when expanded and has sources
   */
  useEffect(() => {
    if (!isExpanded || expert.main_sources.length === 0) {
      setPosts([]);
      setTranslationProgress({ current: 0, total: 0 });
      setShowMobileSources(false); // Reset mobile view
      return;
    }

    let cancelled = false;
    console.log(`[ExpertAccordion] Loading posts for ${expert.expert_id}:`, expert.main_sources);

    // Check if this is an English query and show translation indicator
    const needsTranslation = query && isEnglishQuery(query);
    const sourceCount = expert.main_sources.length;

    if (needsTranslation && sourceCount > 0) {
      setIsTranslating(true);
      setTranslationProgress({ current: 0, total: sourceCount });
      console.log(`[ExpertAccordion] Starting progressive translation for ${sourceCount} posts`);
    } else {
      setPostsLoading(true);
    }

    // Progressive post loading callbacks - optimized for performance!
    let updateTimeout: number | null = null;
    let pendingProgressUpdate: {current: number, total: number} | null = null;
    let pendingPostAdd: ((prev: PostWithRelevance[]) => PostWithRelevance[]) | null = null;

    const flushUpdates = () => {
      if (updateTimeout) {
        clearTimeout(updateTimeout);
        updateTimeout = null;
      }

      if (!cancelled) {
        // Apply all pending updates at once
        if (pendingProgressUpdate) {
          setTranslationProgress(pendingProgressUpdate);
          pendingProgressUpdate = null;
        }

        if (pendingPostAdd) {
          setPosts(pendingPostAdd);
          pendingPostAdd = null;
        }
      }
    };

    const scheduleUpdate = () => {
      // Debounce updates to batch them
      if (updateTimeout) {
        clearTimeout(updateTimeout);
      }

      updateTimeout = setTimeout(flushUpdates, 16); // ~60fps
    };

    const handlePostReady = (newPost: PostDetailResponse) => {
      if (!cancelled) {
        // Accumulate post addition
        if (!pendingPostAdd) {
          pendingPostAdd = (prev) => prev;
        }

        const previousPostAdd = pendingPostAdd;
        pendingPostAdd = (prev) => {
          const basePosts = previousPostAdd(prev);
          // Check if post already exists to prevent duplicates
          const exists = basePosts.some(p => p.telegram_message_id === newPost.telegram_message_id);
          if (exists) {
            return basePosts;
          }
          return [...basePosts, newPost];
        };

        scheduleUpdate();
      }
    };

    const handleProgress = (completed: number, total: number) => {
      if (!cancelled) {
        pendingProgressUpdate = { current: completed, total };
        scheduleUpdate();
      }
    };

    apiClient.getPostsByIdsProgressive(
      expert.main_sources,
      expert.expert_id,
      query,
      handlePostReady,
      handleProgress
    )
      .then(finalOrderedPosts => {
        if (!cancelled) {
          // IMPORTANT: Only update if we're still translating or have no posts yet
          setPosts(currentPosts => {
            if (currentPosts.length === finalOrderedPosts.length) {
              return currentPosts; // Keep progressive order
            }
            return finalOrderedPosts; // Use final correct order if missing posts
          });
        }
      })
      .catch(err => {
        if (!cancelled) {
          console.error(`[ExpertAccordion] Failed to load posts for ${expert.expert_id}:`, err);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPostsLoading(false);
          setIsTranslating(false);
        }
      });

    return () => {
      cancelled = true;
      if (updateTimeout) {
        clearTimeout(updateTimeout);
      }
      flushUpdates();
    };
  }, [isExpanded, expert.main_sources, expert.expert_id, query]);

  /**
   * Handle clicking on post reference in answer
   */
  const handlePostClick = (postId: number): void => {
    setSelectedPostId(postId);
    // On mobile, auto-expand sources when clicking a reference
    setShowMobileSources(true);
  };

  /**
   * Get confidence badge color
   */
  const getConfidenceColor = (confidence: string): string => {
    switch (confidence) {
      case 'HIGH': return '#28a745';
      case 'MEDIUM': return '#ffc107';
      case 'LOW': return '#dc3545';
      default: return '#6c757d';
    }
  };

  return (
    <div className="expert-accordion">
      {/* Header - always visible */}
      <div className="accordion-header" onClick={onToggle}>
        <span className="accordion-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="expert-name">{expert.expert_name}</span>
        <span className="channel-name">@{expert.channel_username}</span>
        <span className="header-stats">
          {expert.posts_analyzed} posts • {(expert.processing_time_ms / 1000).toFixed(1)}s
        </span>
        <span 
          className="confidence-badge"
          style={{ backgroundColor: getConfidenceColor(expert.confidence) }}
        >
          {expert.confidence}
        </span>
      </div>

      {/* Body - only when expanded */}
      {isExpanded && (
        <div className="accordion-body">
          {/* Left Column - Expert Response */}
          <div className="accordion-col-left">
            <div className="col-header">
              <h2 className="column-title" style={{fontSize: '16px', margin: 0}}>Expert Response</h2>
            </div>

            <div className="scrollable-content">
              {expert.answer ? (
                <>
                  <ExpertResponse
                    answer={expert.answer}
                    sources={expert.main_sources}
                    onPostClick={handlePostClick}
                  />
                  {expert.comment_groups_synthesis && (
                    <CommentSynthesis synthesis={expert.comment_groups_synthesis} />
                  )}
                </>
              ) : (
                <div className="empty-placeholder">
                  No response from expert
                </div>
              )}
            </div>
            
            {/* Mobile Only: Toggle Sources Button */}
            <div 
              className="mobile-sources-toggle mobile-only"
              onClick={() => setShowMobileSources(!showMobileSources)}
            >
              {showMobileSources ? 'Hide Sources ▲' : `Show Sources (${expert.main_sources.length}) ▼`}
            </div>
          </div>

          {/* Right Column - Posts */}
          {/* On mobile, this is hidden by default until toggled */}
          <div className={`accordion-col-right ${!showMobileSources ? 'mobile-hidden' : ''}`}>
            <div className="col-header">
              <h2 className="column-title" style={{fontSize: '16px', margin: 0}}>
                Source posts with comments
              </h2>
            </div>

            <div className="scrollable-content">
              {isTranslating ? (
                <div>
                  {/* Progress indicator */}
                  <div className="translation-loading">
                    <div className="loading-icon">🔄</div>
                    <div className="loading-text">
                      Translating posts used for generating the expert response...
                    </div>
                    <div className="progress-indicator">
                      {translationProgress.current} / {translationProgress.total}
                    </div>
                  </div>

                  {/* Show posts as they become available */}
                  {posts.length > 0 && (
                    <div className="progressive-posts-container">
                      <div className="progressive-posts-header">
                        {posts.length} post{posts.length === 1 ? '' : 's'} translated so far:
                      </div>
                      <PostsList
                        posts={posts}
                        selectedPostId={selectedPostId}
                        expertId={expert.expert_id}
                      />
                    </div>
                  )}
                </div>
              ) : postsLoading ? (
                <div className="empty-placeholder">Loading posts...</div>
              ) : (
                <>
                  {/* 1. Render Posts (if any) */}
                  {posts.length > 0 && (
                    <PostsList
                      posts={posts}
                      selectedPostId={selectedPostId}
                      expertId={expert.expert_id}
                    />
                  )}

                  {/* 2. Render Comment Groups (ALWAYS if they exist) */}
                  {expert.relevant_comment_groups && expert.relevant_comment_groups.length > 0 && (
                    <CommentGroupsList
                      commentGroups={expert.relevant_comment_groups}
                    />
                  )}

                  {/* 3. Placeholder only if NOTHING exists */}
                  {posts.length === 0 && (!expert.relevant_comment_groups || expert.relevant_comment_groups.length === 0) && (
                    <div className="empty-placeholder">
                       {expert.main_sources.length > 0 ? 'Loading posts...' : 'No source posts available'}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExpertAccordion;