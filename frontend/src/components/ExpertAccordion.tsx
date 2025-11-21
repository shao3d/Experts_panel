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

  /**
   * Load posts when expanded and has sources
   */
  useEffect(() => {
    if (!isExpanded || expert.main_sources.length === 0) {
      setPosts([]);
      setTranslationProgress({ current: 0, total: 0 });
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
    <div style={styles.accordion}>
      {/* Header - always visible */}
      <div style={styles.header} onClick={onToggle}>
        <span style={styles.icon}>{isExpanded ? '▼' : '▶'}</span>
        <span style={styles.expertName}>{expert.expert_name}</span>
        <span style={styles.channelName}>@{expert.channel_username}</span>
        <span style={styles.stats}>
          {expert.posts_analyzed} posts • {(expert.processing_time_ms / 1000).toFixed(1)} seconds
        </span>
        <span style={{
          ...styles.confidence,
          backgroundColor: getConfidenceColor(expert.confidence)
        }}>
          {expert.confidence}
        </span>
      </div>

      {/* Body - only when expanded */}
      {isExpanded && (
        <div style={styles.body}>
          {/* Left Column - Expert Response */}
          <div style={styles.leftColumn}>
            <div style={styles.columnHeader}>
              <h2 style={styles.columnTitle}>Expert Response</h2>
            </div>

            <div style={styles.scrollableContent}>
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
                <div style={styles.placeholder}>
                  No response from expert
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Posts */}
          <div style={styles.rightColumn}>
            <div style={styles.columnHeader}>
              <h2 style={styles.columnTitle}>
                Source posts with comments
              </h2>
            </div>

            <div style={styles.scrollableContent}>
              {isTranslating ? (
                <div>
                  {/* Progress indicator */}
                  <div style={styles.translationLoading}>
                    <div style={styles.loadingIcon}>🔄</div>
                    <div style={styles.loadingText}>
                      Translating posts used for generating the expert response...
                    </div>
                    <div style={styles.progressIndicator}>
                      {translationProgress.current} / {translationProgress.total}
                    </div>
                  </div>

                  {/* Show posts as they become available */}
                  {posts.length > 0 && (
                    <div style={styles.progressivePostsContainer}>
                      <div style={styles.progressivePostsHeader}>
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
                <div style={styles.placeholder}>Loading posts...</div>
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
                    <div style={styles.placeholder}>
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

const styles = {
  accordion: {
    marginBottom: '20px',
    backgroundColor: 'white',
    borderRadius: '8px',
    border: '1px solid #dee2e6',
    overflow: 'hidden'
  },
  header: {
    padding: '15px 20px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px 8px 0 0',
    transition: 'background-color 0.2s',
    userSelect: 'none' as const
  },
  icon: {
    fontSize: '14px',
    color: '#6c757d',
    width: '14px'
  },
  expertName: {
    fontSize: '16px',
    fontWeight: '600' as const,
    color: '#212529'
  },
  channelName: {
    fontSize: '14px',
    color: '#6c757d'
  },
  stats: {
    fontSize: '13px',
    color: '#6c757d',
    marginLeft: 'auto'
  },
  confidence: {
    fontSize: '12px',
    fontWeight: '600' as const,
    color: 'white',
    padding: '3px 8px',
    borderRadius: '4px',
    textTransform: 'uppercase' as const
  },
  body: {
    display: 'flex',
    gap: '2px',
    height: '600px', // Fixed height for consistency
    borderTop: '1px solid #dee2e6'
  },
  leftColumn: {
    flex: "0 0 50%",  // Fixed width, prevents growing/shrinking
    minWidth: 0,      // Allow content overflow instead of container expansion
    display: 'flex',
    flexDirection: 'column' as const,
    backgroundColor: 'white',
    borderRight: '1px solid #dee2e6'
  },
  rightColumn: {
    flex: "0 0 50%",  // Fixed width, prevents growing/shrinking
    minWidth: 0,      // Allow content overflow instead of container expansion
    display: 'flex',
    flexDirection: 'column' as const,
    backgroundColor: '#f8f9fa'
  },
  columnHeader: {
    padding: '12px 20px',
    backgroundColor: '#f5f7fa',
    borderBottom: '1px solid #dee2e6',
    textAlign: 'center' as const
  },
  columnTitle: {
    fontSize: '16px',
    fontWeight: '600' as const,
    color: '#495057',
    margin: 0,
    textAlign: 'center' as const
  },
  scrollableContent: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '20px'
  },
  placeholder: {
    padding: '40px',
    textAlign: 'center' as const,
    color: '#6c757d',
    fontSize: '16px'
  },
  translationLoading: {
    padding: '40px',
    textAlign: 'center' as const,
    color: '#6c757d',
    fontSize: '16px',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: '12px'
  },
  loadingIcon: {
    fontSize: '24px',
    marginBottom: '8px',
    animation: 'spin 1s linear infinite'
  },
  loadingText: {
    fontSize: '14px',
    color: '#495057',
    fontWeight: '500' as const,
    textAlign: 'center' as const
  },
  progressIndicator: {
    fontSize: '12px',
    color: '#495057',
    fontWeight: '500' as const,
    textAlign: 'center' as const,
    marginTop: '8px'
  },
  progressivePostsContainer: {
    marginTop: '20px'
  },
  progressivePostsHeader: {
    fontSize: '14px',
    color: '#495057',
    fontWeight: '600' as const,
    marginBottom: '12px',
    textAlign: 'center' as const,
    padding: '8px',
    backgroundColor: '#e9ecef',
    borderRadius: '6px'
  }
};

export default ExpertAccordion;