import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { CommentGroupResponse } from '../types/api';

interface CommentGroupsListProps {
  commentGroups: CommentGroupResponse[];
}

export const CommentGroupsList: React.FC<CommentGroupsListProps> = ({
  commentGroups
}) => {
  const [expandedPosts, setExpandedPosts] = useState<Set<number>>(new Set());
  const [expandedComments, setExpandedComments] = useState<Set<number>>(
    new Set(commentGroups.map(g => g.parent_telegram_message_id))
  );

  if (!commentGroups || commentGroups.length === 0) {
    return null;
  }

  const togglePost = (postId: number) => {
    setExpandedPosts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(postId)) {
        newSet.delete(postId);
      } else {
        newSet.add(postId);
      }
      return newSet;
    });
  };

  const toggleComments = (postId: number) => {
    setExpandedComments(prev => {
      const newSet = new Set(prev);
      if (newSet.has(postId)) {
        newSet.delete(postId);
      } else {
        newSet.add(postId);
      }
      return newSet;
    });
  };

  const getRelevanceBadge = (relevance: string): { color: string; backgroundColor: string; text: string } => {
    switch (relevance) {
      case 'HIGH':
        return { color: 'var(--ep-success)', backgroundColor: 'var(--ep-success-bg)', text: 'High' };
      case 'MEDIUM':
        return { color: 'var(--ep-warning)', backgroundColor: 'var(--ep-warning-bg)', text: 'Medium' };
      default:
        return { color: 'rgba(26, 51, 0, 0.62)', backgroundColor: 'var(--ep-paper-muted)', text: 'Low' };
    }
  };

  const styles = {
    container: {
      marginTop: '24px',
      padding: '20px',
      backgroundColor: 'var(--ep-paper-muted)',
      borderRadius: 'var(--ep-radius-card)',
      border: '1px solid rgba(26, 51, 0, 0.14)',
      minWidth: 0,
      maxWidth: '100%'
    },
    header: {
      fontSize: '16px',
      fontWeight: '600' as const,
      marginBottom: '16px',
      color: 'var(--ep-forest)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px'
    },
    groupCard: {
      backgroundColor: 'var(--ep-paper-raised)',
      border: '1px solid rgba(26, 51, 0, 0.14)',
      borderRadius: 'var(--ep-radius-card)',
      padding: '16px',
      marginBottom: '12px',
      transition: 'border-color 0.2s',
      minWidth: 0,
      maxWidth: '100%'
    },
    postHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: '12px',
      paddingBottom: '12px',
      borderBottom: '1px solid rgba(26, 51, 0, 0.12)',
      gap: '8px',
      flexWrap: 'wrap' as const
    },
    postHeaderLeft: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      flexWrap: 'wrap' as const,
      minWidth: 0
    },
    postId: {
      fontSize: '14px',
      fontWeight: '600' as const,
      color: 'var(--ep-terracotta)'
    },
    toggleButton: {
      backgroundColor: 'transparent',
      border: '1px solid transparent',
      color: 'var(--ep-forest)',
      fontSize: '14px',
      fontWeight: '600' as const,
      cursor: 'pointer',
      padding: '4px 8px',
      borderRadius: 'var(--ep-radius-button)',
      transition: 'background-color 0.2s',
      display: 'flex',
      alignItems: 'center',
      gap: '4px'
    },
    relevanceBadge: (color: string, backgroundColor: string) => ({
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 'var(--ep-radius-button)',
      fontSize: '12px',
      fontWeight: '600' as const,
      backgroundColor,
      color: color
    }),
    expandedPost: {
      marginBottom: '12px',
      padding: '12px',
      backgroundColor: 'var(--ep-paper-muted)',
      borderRadius: 'var(--ep-radius-button)',
      border: '1px solid rgba(26, 51, 0, 0.14)',
      minWidth: 0,
      maxWidth: '100%'
    },
    postText: {
      fontSize: '14px',
      color: 'var(--ep-forest)',
      lineHeight: '1.6',
      marginBottom: '8px',
      whiteSpace: 'pre-wrap' as const,
      overflowWrap: 'anywhere' as const,
      wordBreak: 'break-word' as const,
      minWidth: 0,
      maxWidth: '100%'
    },
    postMeta: {
      fontSize: '12px',
      color: 'rgba(26, 51, 0, 0.48)',
      display: 'flex',
      gap: '12px'
    },
    commentsSection: {
      marginTop: '12px'
    },
    commentsCount: {
      fontSize: '13px',
      fontWeight: '600' as const,
      color: 'var(--ep-forest)',
      marginBottom: '8px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    },
    commentsToggle: {
      fontSize: '12px',
      color: 'var(--ep-terracotta)'
    },
    comment: {
      marginBottom: '8px',
      padding: '8px',
      backgroundColor: 'var(--ep-paper-muted)',
      borderRadius: 'var(--ep-radius-button)',
      borderLeft: '3px solid var(--ep-forest)',
      minWidth: 0,
      maxWidth: '100%'
    },
    commentAuthor: {
      fontSize: '13px',
      fontWeight: '600' as const,
      color: 'var(--ep-forest)',
      marginBottom: '4px'
    },
    commentText: {
      fontSize: '13px',
      color: 'var(--ep-forest)',
      lineHeight: '1.5',
      overflowWrap: 'anywhere' as const,
      wordBreak: 'break-word' as const,
      minWidth: 0,
      maxWidth: '100%'
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span>💬</span>
        <span>Relevant groups of comments ({commentGroups.length})</span>
      </div>

      {commentGroups.map((group) => {
        const badge = getRelevanceBadge(group.relevance);
        const isExpanded = expandedPosts.has(group.parent_telegram_message_id);
        const commentsExpanded = expandedComments.has(group.parent_telegram_message_id);
        const telegramLink = `https://t.me/${group.anchor_post.channel_username}/${group.parent_telegram_message_id}`;

        return (
          <div key={group.parent_telegram_message_id} style={styles.groupCard}>
            {/* Post Header */}
            <div style={styles.postHeader}>
              <div style={styles.postHeaderLeft}>
                <button
                  style={styles.toggleButton}
                  onClick={() => togglePost(group.parent_telegram_message_id)}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--ep-yellow)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <span>{isExpanded ? '▼' : '▶'}</span>
                  <span>{isExpanded ? 'Hide post' : 'Show post'}</span>
                </button>
                <span>•</span>
                <span style={{ fontSize: '13px', color: 'rgba(26, 51, 0, 0.62)' }}>{group.anchor_post.author_name}</span>
                <span>•</span>
                <span style={{ fontSize: '13px', color: 'rgba(26, 51, 0, 0.62)' }}>
                  {new Date(group.anchor_post.created_at).toLocaleDateString('ru-RU')}
                </span>
                <span>•</span>
                <a
                  href={telegramLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    backgroundColor: 'var(--ep-forest)',
                    color: 'var(--ep-cream)',
                    textDecoration: 'none',
                    borderRadius: 'var(--ep-radius-button)',
                    fontSize: '12px',
                    fontWeight: '500'
                  }}
                >
                  📱 Telegram
                </a>
              </div>
              <span style={styles.relevanceBadge(badge.color, badge.backgroundColor)}>{badge.text}</span>
            </div>

            {/* Expanded Post Content */}
            {isExpanded && (
              <div style={styles.expandedPost}>
                <div className="breakable-markdown" style={styles.postText}>
                  <ReactMarkdown>{group.anchor_post.message_text}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* Comments Section */}
            <div style={styles.commentsSection}>
              <div
                style={styles.commentsCount}
                onClick={() => toggleComments(group.parent_telegram_message_id)}
              >
                <span style={styles.commentsToggle}>{commentsExpanded ? '−' : '+'}</span>
                <span>{group.comments_count} {group.comments_count === 1 ? 'комментарий' : 'комментариев'}</span>
              </div>

              {commentsExpanded && group.comments.map((comment) => (
                <div key={comment.comment_id} style={styles.comment}>
                  <div style={styles.commentAuthor}>💬 {comment.author_name}:</div>
                  <div className="breakable-markdown" style={styles.commentText}>
                    <ReactMarkdown>{comment.comment_text}</ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
