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
}

const PostCard: React.FC<PostCardProps> = ({ post, isExpanded, onToggleComments, isSelected = false }) => {
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
        style={{ color: '#0066cc', textDecoration: 'underline' }}
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
      <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '3px', fontSize: '0.9em' }}>{children}</code>
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
        backgroundColor: '#f8f9fa',
        borderLeft: '3px solid #6c757d',
        borderRadius: '4px',
      }}
    >
      {/* Comment Author & Date */}
      <div style={{
        fontSize: '13px',
        color: '#6c757d',
        marginBottom: '6px',
        fontWeight: '500'
      }}>
        <strong>{comment.author_name}</strong>
      </div>

      {/* Comment Text */}
      <div style={{ fontSize: '14px', color: '#495057' }}>
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

  return (
    <div
      id={`post-${post.telegram_message_id}`}
      style={{
        marginBottom: '16px',
        padding: '16px',
        backgroundColor: isSelected ? '#fff3cd' : 'white',
        borderRadius: '8px',
        border: isSelected ? '2px solid #ffc107' : '1px solid #dee2e6',
        transition: 'all 0.3s ease',
      }}
    >
      {/* Post Header */}
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div>
            <span style={{
              fontWeight: 'bold',
              fontSize: '14px',
              color: '#0066cc',
              marginRight: '8px'
            }}>
              [{post.telegram_message_id}]
            </span>
            <span style={{ fontSize: '14px', color: '#6c757d' }}>
              <strong>{post.author_name || 'Unknown'}</strong> • {formatDate(post.created_at)}
            </span>
          </div>
          {/* Telegram Link */}
          {post.channel_name && (
            <a
              href={`https://t.me/${post.channel_name}/${post.telegram_message_id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: '#0088cc',
                color: 'white',
                borderRadius: '4px',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: '500',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#006699';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#0088cc';
              }}
            >
              <span style={{ fontSize: '16px' }}>📱</span>
              Telegram
            </a>
          )}
        </div>
        {post.relevance_score && (
          <span style={{
            fontSize: '12px',
            padding: '4px 8px',
            backgroundColor: post.relevance_score === 'HIGH' ? '#d4edda' :
                           post.relevance_score === 'MEDIUM' ? '#fff3cd' : '#f8f9fa',
            color: post.relevance_score === 'HIGH' ? '#155724' :
                   post.relevance_score === 'MEDIUM' ? '#856404' : '#6c757d',
            borderRadius: '4px',
            fontWeight: 'bold',
          }}>
            {post.relevance_score}
          </span>
        )}
      </div>

      {/* Post Content */}
      <div style={{
        fontSize: '15px',
        lineHeight: '1.6',
        color: '#212529',
        marginBottom: hasComments ? '12px' : '0'
      }}>
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
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              padding: '6px 12px',
              fontSize: '14px',
              color: '#495057',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f8f9fa';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <span style={{ fontSize: '16px', lineHeight: '1' }}>
              {isExpanded ? '−' : '+'}
            </span>
            Комментарии
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