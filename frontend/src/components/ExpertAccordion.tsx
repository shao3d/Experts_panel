/**
 * Accordion component for displaying single expert's results.
 * Contains two columns: answer on the left, posts on the right.
 */

import React, { useState, useEffect } from 'react';
import ExpertResponse from './ExpertResponse';
import PostsList from './PostsList';
import { CommentGroupsList } from './CommentGroupsList';
import CommentSynthesis from './CommentSynthesis';
import { apiClient } from '../services/api';
import { ExpertResponse as ExpertResponseType, PostDetailResponse } from '../types/api';

interface PostWithRelevance extends PostDetailResponse {
  relevance_score?: 'HIGH' | 'MEDIUM' | 'LOW' | null;
}

interface ExpertAccordionProps {
  expert: ExpertResponseType;
  isExpanded: boolean;
  onToggle: () => void;
}

const ExpertAccordion: React.FC<ExpertAccordionProps> = ({
  expert,
  isExpanded,
  onToggle
}) => {
  const [posts, setPosts] = useState<PostWithRelevance[]>([]);
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);
  const [postsLoading, setPostsLoading] = useState(false);

  /**
   * Load posts when expanded and has sources
   */
  useEffect(() => {
    if (!isExpanded || expert.main_sources.length === 0) {
      setPosts([]);
      return;
    }

    let cancelled = false;
    console.log(`[ExpertAccordion] Loading posts for ${expert.expert_id}:`, expert.main_sources);
    setPostsLoading(true);

    apiClient.getPostsByIds(expert.main_sources, expert.expert_id)
      .then(fetchedPosts => {
        if (!cancelled) {
          console.log(`[ExpertAccordion] Posts loaded for ${expert.expert_id}:`, fetchedPosts.length);
          setPosts(fetchedPosts);
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
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isExpanded, expert.main_sources, expert.expert_id]);

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
                Source posts with comments ({posts.length})
              </h2>
            </div>

            <div style={styles.scrollableContent}>
              {postsLoading ? (
                <div style={styles.placeholder}>Loading posts...</div>
              ) : posts.length > 0 ? (
                <>
                  <PostsList
                    posts={posts}
                    selectedPostId={selectedPostId}
                  />
                  {expert.relevant_comment_groups && expert.relevant_comment_groups.length > 0 && (
                    <CommentGroupsList
                      commentGroups={expert.relevant_comment_groups}
                      channelUsername={expert.channel_username}
                    />
                  )}
                </>
              ) : (
                <div style={styles.placeholder}>
                  {expert.main_sources.length > 0 ? 'Loading posts...' : 'No source posts available'}
                </div>
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
  }
};

export default ExpertAccordion;