import React from 'react';
import ReactMarkdown from 'react-markdown';

interface ExpertResponseProps {
  answer: string;
  sources: number[];
  onPostClick: (postId: number) => void;
}

const ExpertResponse: React.FC<ExpertResponseProps> = ({ answer, sources, onPostClick }) => {
  // Process text nodes to handle [post:ID] and [ID] references
  const processTextNode = (text: string): React.ReactNode[] => {
    // Match both [post:ID] and [ID] formats
    const postRefPattern = /\[(?:post:)?(\d+)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = postRefPattern.exec(text)) !== null) {
      const postId = parseInt(match[1], 10);
      const wasPostFormat = match[0].startsWith('[post:');

      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      // Add clickable reference if it's in sources
      if (sources.includes(postId)) {
        parts.push(
          <button
            key={`ref-${match.index}`}
            onClick={() => onPostClick(postId)}
            style={{
              backgroundColor: '#e6f2ff',
              border: '1px solid #0066cc',
              color: '#0066cc',
              padding: '2px 6px',
              borderRadius: '3px',
              fontSize: 'inherit',
              fontFamily: 'inherit',
              margin: '0 2px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'inline-block',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#0066cc';
              e.currentTarget.style.color = 'white';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#e6f2ff';
              e.currentTarget.style.color = '#0066cc';
            }}
            title={`Перейти к посту #${postId}`}
          >
            [{postId}]
          </button>
        );
      } else {
        // Keep original format if not in sources
        parts.push(match[0]);
      }

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text after the last match
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : [text];
  };

  // Custom components for ReactMarkdown
  const markdownComponents = {
    // Handle paragraph nodes
    p: ({ children }: any) => {
      return (
        <p style={{ margin: '0 0 1em 0' }}>
          {React.Children.map(children, (child) => {
            if (typeof child === 'string') {
              return processTextNode(child);
            }
            return child;
          })}
        </p>
      );
    },
    // Handle text nodes in other elements
    text: ({ children }: any) => {
      if (typeof children === 'string') {
        return <>{processTextNode(children)}</>;
      }
      return children;
    },
    // Style for links
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
    // Style for strong/bold text
    strong: ({ children }: any) => (
      <strong style={{ fontWeight: 600 }}>{children}</strong>
    ),
    // Style for emphasis/italic text
    em: ({ children }: any) => (
      <em style={{ fontStyle: 'italic' }}>{children}</em>
    ),
    // Style for lists
    ul: ({ children }: any) => (
      <ul style={{ margin: '0.5em 0', paddingLeft: '1.5em' }}>{children}</ul>
    ),
    ol: ({ children }: any) => (
      <ol style={{ margin: '0.5em 0', paddingLeft: '1.5em' }}>{children}</ol>
    ),
    // Style for list items
    li: ({ children }: any) => {
      return (
        <li style={{ margin: '0.25em 0' }}>
          {React.Children.map(children, (child) => {
            if (typeof child === 'string') {
              return processTextNode(child);
            }
            return child;
          })}
        </li>
      );
    },
    // Style for headings
    h1: ({ children }: any) => (
      <h1 style={{ fontSize: '1.5em', fontWeight: 600, margin: '0.5em 0' }}>{children}</h1>
    ),
    h2: ({ children }: any) => (
      <h2 style={{ fontSize: '1.3em', fontWeight: 600, margin: '0.5em 0' }}>{children}</h2>
    ),
    h3: ({ children }: any) => (
      <h3 style={{ fontSize: '1.1em', fontWeight: 600, margin: '0.5em 0' }}>{children}</h3>
    ),
  };

  return (
    <div
      style={{
        padding: '20px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px',
        border: '1px solid #dee2e6',
        height: '100%',
        overflowY: 'auto',
      }}
    >
      <div
        style={{
          fontSize: '16px',
          lineHeight: '1.6',
          color: '#212529',
        }}
      >
        <ReactMarkdown
          components={markdownComponents}
          urlTransform={(url) => url}
        >
          {answer}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default ExpertResponse;