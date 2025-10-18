import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { CommentGroupResponse } from '../types/api';

interface CommentGroupsListProps {
  commentGroups: CommentGroupResponse[];
  channelUsername?: string;
}

export const CommentGroupsList: React.FC<CommentGroupsListProps> = ({
  commentGroups,
  channelUsername = 'nobilix'
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

  const getRelevanceBadge = (relevance: string): { color: string; text: string } => {
    switch (relevance) {
      case 'HIGH':
        return { color: '#22c55e', text: 'Высокая' };
      case 'MEDIUM':
        return { color: '#f59e0b', text: 'Средняя' };
      default:
        return { color: '#94a3b8', text: 'Низкая' };
    }
  };

  const styles = {
    container: {
      marginTop: '24px',
      padding: '20px',
      backgroundColor: '#f8fafc',
      borderRadius: '8px',
      border: '1px solid #e2e8f0'
    },
    header: {
      fontSize: '16px',
      fontWeight: '600' as const,
      marginBottom: '16px',
      color: '#495057',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px'
    },
    groupCard: {
      backgroundColor: '#ffffff',
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      padding: '16px',
      marginBottom: '12px',
      transition: 'border-color 0.2s'
    },
    postHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: '12px',
      paddingBottom: '12px',
      borderBottom: '1px solid #f1f5f9'
    },
    postHeaderLeft: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    postId: {
      fontSize: '14px',
      fontWeight: '600' as const,
      color: '#64748b'
    },
    toggleButton: {
      backgroundColor: 'transparent',
      border: 'none',
      color: '#3b82f6',
      fontSize: '14px',
      fontWeight: '500' as const,
      cursor: 'pointer',
      padding: '4px 8px',
      borderRadius: '4px',
      transition: 'background-color 0.2s',
      display: 'flex',
      alignItems: 'center',
      gap: '4px'
    },
    relevanceBadge: (color: string) => ({
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: '500' as const,
      backgroundColor: `${color}20`,
      color: color
    }),
    expandedPost: {
      marginBottom: '12px',
      padding: '12px',
      backgroundColor: '#f8fafc',
      borderRadius: '6px',
      border: '1px solid #e2e8f0'
    },
    postText: {
      fontSize: '14px',
      color: '#334155',
      lineHeight: '1.6',
      marginBottom: '8px',
      whiteSpace: 'pre-wrap' as const
    },
    postMeta: {
      fontSize: '12px',
      color: '#94a3b8',
      display: 'flex',
      gap: '12px'
    },
    commentsSection: {
      marginTop: '12px'
    },
    commentsCount: {
      fontSize: '13px',
      fontWeight: '600' as const,
      color: '#64748b',
      marginBottom: '8px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    },
    commentsToggle: {
      fontSize: '12px',
      color: '#3b82f6'
    },
    comment: {
      marginBottom: '8px',
      padding: '8px',
      backgroundColor: '#f8fafc',
      borderRadius: '4px',
      borderLeft: '3px solid #3b82f6'
    },
    commentAuthor: {
      fontSize: '13px',
      fontWeight: '600' as const,
      color: '#1e293b',
      marginBottom: '4px'
    },
    commentText: {
      fontSize: '13px',
      color: '#475569',
      lineHeight: '1.5'
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span>💬</span>
        <span>Релевантные группы комментариев ({commentGroups.length})</span>
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
                    e.currentTarget.style.backgroundColor = '#eff6ff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <span>{isExpanded ? '▼' : '▶'}</span>
                  <span>{isExpanded ? 'Скрыть пост' : 'Показать пост'}</span>
                </button>
                <span>•</span>
                <span style={{ fontSize: '13px', color: '#64748b' }}>{group.anchor_post.author_name}</span>
                <span>•</span>
                <span style={{ fontSize: '13px', color: '#64748b' }}>
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
                    backgroundColor: '#0088cc',
                    color: 'white',
                    textDecoration: 'none',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: '500'
                  }}
                >
                  📱 Telegram
                </a>
              </div>
              <span style={styles.relevanceBadge(badge.color)}>{badge.text}</span>
            </div>

            {/* Expanded Post Content */}
            {isExpanded && (
              <div style={styles.expandedPost}>
                <div style={styles.postText}>
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
                  <div style={styles.commentText}>
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
