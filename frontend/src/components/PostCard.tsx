import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CommentResponse, PostDetailResponse } from '../types/api';

// Extend PostDetailResponse to include relevance_score from Map phase
interface PostWithRelevance extends PostDetailResponse {
  relevance_score?: 'HIGH' | 'MEDIUM' | 'LOW' | null;
}

interface PostCardProps {
  post: PostWithRelevance;
  isExpanded: boolean;
  onToggleComments: () => void;
  isSelected?: boolean;
  expertId?: string;
}

const PostCard: React.FC<PostCardProps> = ({ post, isExpanded, onToggleComments, isSelected = false, expertId }) => {
  const hasComments = post.comments && post.comments.length > 0;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Markdown components for rendering (same as ExpertResponse)
  const markdownComponents = {
    a: ({ href, children }: any) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          color: 'var(--ep-forest)',
          textDecoration: 'underline',
          textDecorationColor: 'var(--ep-yellow)',
          textDecorationThickness: '0.16em',
          textUnderlineOffset: '0.12em',
          overflowWrap: 'anywhere',
          wordBreak: 'break-word',
        }}
      >
        {children}
      </a>
    ),
    strong: ({ children }: any) => (
      <strong style={{ fontWeight: 600 }}>{children}</strong>
    ),
    em: ({ children }: any) => (
      <em style={{ fontStyle: 'italic' }}>{children}</em>
    ),
    code: ({ children }: any) => (
      <code style={{
        backgroundColor: 'var(--ep-paper-muted)',
        padding: '2px 4px',
        borderRadius: 'var(--ep-radius-button)',
        fontSize: '0.9em',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
      }}>{children}</code>
    ),
    p: ({ children }: any) => (
      <p style={{ margin: '0 0 0.5em 0' }}>{children}</p>
    ),
    ul: ({ children }: any) => (
      <ul style={{ paddingLeft: '20px', marginBottom: '0.5em' }}>{children}</ul>
    ),
    ol: ({ children }: any) => (
      <ol style={{ paddingLeft: '20px', marginBottom: '0.5em' }}>{children}</ol>
    ),
    li: ({ children }: any) => (
      <li style={{ marginBottom: '0.25em' }}>{children}</li>
    ),
  };

  const renderComment = (comment: CommentResponse) => (
    <div
      key={comment.comment_id}
      style={{
        padding: '12px',
        marginLeft: '20px',
        marginTop: '8px',
        backgroundColor: 'var(--ep-paper-muted)',
        borderLeft: '3px solid var(--ep-forest)',
        borderRadius: 'var(--ep-radius-button)',
        minWidth: 0,
        maxWidth: '100%',
      }}
    >
      {/* Comment Author & Date */}
      <div style={{
        fontSize: '13px',
        color: 'rgba(26, 51, 0, 0.62)',
        marginBottom: '6px',
        fontWeight: '500'
      }}>
        <strong>{comment.author_name}</strong>
      </div>

      {/* Comment Text */}
      <div
        className="breakable-markdown"
        style={{
          fontSize: '14px',
          color: 'var(--ep-forest)',
          minWidth: 0,
          maxWidth: '100%',
        }}
      >
        <ReactMarkdown
          components={markdownComponents}
          remarkPlugins={[remarkGfm]}
          urlTransform={(url) => url}
        >
          {comment.comment_text}
        </ReactMarkdown>
      </div>
    </div>
  );

  const isVideoSegment = post.media_metadata?.type === 'video_segment';
  const videoUrl = post.media_metadata?.video_url;
  const timestampSeconds = post.media_metadata?.timestamp_seconds;
  const originalAuthor = post.media_metadata?.original_author;

  return (
    <div
      id={`post-${expertId || 'unknown'}-${post.telegram_message_id}`}
      style={{
        marginBottom: '16px',
        padding: '16px',
        backgroundColor: isSelected ? 'var(--ep-warning-bg)' : 'var(--ep-paper-raised)',
        borderRadius: 'var(--ep-radius-card)',
        border: isSelected ? '2px solid var(--ep-yellow)' : '1px solid rgba(26, 51, 0, 0.14)',
        transition: 'all 0.3s ease',
        minWidth: 0,
        maxWidth: '100%',
      }}
    >
      {/* Post Header */}
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 0 }}>
            <span style={{
              fontWeight: 'bold',
              fontSize: '14px',
              color: 'var(--ep-terracotta)',
              marginRight: '8px'
            }}>
              [{post.telegram_message_id}]
            </span>
            <span style={{ fontSize: '14px', color: 'rgba(26, 51, 0, 0.62)' }}>
              <strong>{originalAuthor || post.author_name || 'Unknown'}</strong> • {formatDate(post.created_at)}
            </span>
          </div>
          {/* Telegram Link */}
          {post.channel_name && !isVideoSegment && (
            <a
              href={`https://t.me/${post.channel_name}/${post.telegram_message_id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: 'var(--ep-forest)',
                color: 'var(--ep-cream)',
                borderRadius: 'var(--ep-radius-button)',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: '500',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--ep-yellow)';
                e.currentTarget.style.color = 'var(--ep-forest)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--ep-forest)';
                e.currentTarget.style.color = 'var(--ep-cream)';
              }}
            >
              <span style={{ fontSize: '16px' }}>📱</span>
              Telegram
            </a>
          )}
          {/* YouTube Link */}
          {isVideoSegment && videoUrl && (
            <a
              href={timestampSeconds !== undefined ? `${videoUrl}&t=${timestampSeconds}s` : videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: 'var(--ep-terracotta)',
                color: 'var(--ep-cream)',
                borderRadius: 'var(--ep-radius-button)',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: '500',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--ep-yellow)';
                e.currentTarget.style.color = 'var(--ep-forest)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--ep-terracotta)';
                e.currentTarget.style.color = 'var(--ep-cream)';
              }}
            >
              <span style={{ fontSize: '16px' }}>🎥</span>
              Watch Video {timestampSeconds !== undefined && `(${Math.floor(timestampSeconds / 60)}:${(timestampSeconds % 60).toString().padStart(2, '0')})`}
            </a>
          )}
        </div>
        {post.relevance_score && (
          <span style={{
            fontSize: '12px',
            padding: '4px 8px',
            backgroundColor: post.relevance_score === 'HIGH' ? 'var(--ep-success-bg)' :
                           post.relevance_score === 'MEDIUM' ? 'var(--ep-warning-bg)' : 'var(--ep-paper-muted)',
            color: post.relevance_score === 'HIGH' ? 'var(--ep-success)' :
                   post.relevance_score === 'MEDIUM' ? 'var(--ep-warning)' : 'rgba(26, 51, 0, 0.62)',
            borderRadius: 'var(--ep-radius-button)',
            fontWeight: 'bold',
          }}>
            {post.relevance_score}
          </span>
        )}
      </div>

      {/* Post Content */}
      <div
        className="breakable-markdown"
        style={{
          fontSize: '15px',
          lineHeight: '1.6',
          color: 'var(--ep-forest)',
          marginBottom: hasComments ? '12px' : '0',
          minWidth: 0,
          maxWidth: '100%',
        }}
      >
        <ReactMarkdown
          components={markdownComponents}
          remarkPlugins={[remarkGfm]}
          urlTransform={(url) => url}
        >
          {post.message_text || ''}
        </ReactMarkdown>
      </div>

      {/* Comments Toggle */}
      {hasComments && (
        <>
          <button
            onClick={onToggleComments}
            style={{
              background: 'none',
              border: '1px solid rgba(26, 51, 0, 0.18)',
              borderRadius: 'var(--ep-radius-button)',
              padding: '6px 12px',
              fontSize: '14px',
              color: 'var(--ep-forest)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--ep-yellow)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <span style={{ fontSize: '16px', lineHeight: '1' }}>
              {isExpanded ? '−' : '+'}
            </span>
            Comments
          </button>

          {/* Comments List */}
          {isExpanded && (
            <div style={{ marginTop: '12px' }}>
              {post.comments.map(renderComment)}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default PostCard;
