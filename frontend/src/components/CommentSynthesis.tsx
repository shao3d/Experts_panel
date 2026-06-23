import React from 'react';
import ReactMarkdown from 'react-markdown';

interface CommentSynthesisProps {
  synthesis: string;
}

const CommentSynthesis: React.FC<CommentSynthesisProps> = ({ synthesis }) => {
  return (
    <div
      style={{
        marginTop: '20px',
        padding: '16px',
        backgroundColor: 'var(--ep-paper-muted)',
        borderRadius: 'var(--ep-radius-card)',
        border: '1px solid rgba(26, 51, 0, 0.14)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '12px',
        }}
      >
        <span style={{ fontSize: '20px', marginRight: '8px' }}>💬</span>
        <h3
          style={{
            fontSize: '16px',
            fontWeight: '600',
            color: 'var(--ep-forest)',
            margin: 0,
          }}
        >
          Additional insights from relevant comments
        </h3>
      </div>
      <div
        style={{
          fontSize: '14px',
          lineHeight: '1.8',
          color: 'var(--ep-forest)',
        }}
      >
        <style>{`
          .comment-synthesis ul {
            margin: 8px 0;
            padding-left: 20px;
          }
          .comment-synthesis li {
            margin: 6px 0;
            list-style-type: disc;
          }
          .comment-synthesis p {
            margin: 8px 0;
          }
        `}</style>
        <div className="comment-synthesis">
          <ReactMarkdown>{synthesis}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default CommentSynthesis;
