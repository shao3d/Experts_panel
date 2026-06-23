import React from 'react';
import ReactMarkdown from 'react-markdown';

interface ExpertResponseProps {
  answer: string;
  sources: number[];
  onPostClick: (postId: number) => void;
}

const ExpertResponse: React.FC<ExpertResponseProps> = ({ answer, sources, onPostClick }) => {
  // Process text nodes to handle [post:ID], [ID] and multiple [post:ID, post:ID2] references
  const processTextNode = (text: string): React.ReactNode[] => {
    // Match both single [post:ID] and multiple [post:ID, post:ID2, ID3] formats
    const postRefPattern = /\[(post:\s*\d+(?:\s*,\s*post:\s*\d+|\s*,\s*\d+)*|(?:post:\s*)?\d+)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = postRefPattern.exec(text)) !== null) {
      const matchIndex = match.index;
      const fullMatch = match[0];

      // Add text before the match
      if (matchIndex > lastIndex) {
        parts.push(text.substring(lastIndex, matchIndex));
      }

      // Parse the content inside brackets
      const bracketContent = match[1];
      const postIds: number[] = [];

      // Extract all post IDs from the bracket content
      // Handle formats: "post:50, post:73", "50, 73", "post:50, 73"
      const idMatches = bracketContent.match(/(?:post:\s*)?(\d+)/g);

      if (idMatches) {
        idMatches.forEach(idStr => {
          const postId = parseInt(idStr.replace(/(?:post:\s*)/, ''), 10);
          if (!isNaN(postId)) {
            postIds.push(postId);
          }
        });
      }

      if (postIds.length === 0) {
        // No valid IDs found, keep original text
        parts.push(fullMatch);
      } else if (postIds.length === 1) {
        // Single post ID
        const postId = postIds[0];
        if (sources.includes(postId)) {
          parts.push(
            <button
              key={`ref-${matchIndex}`}
              onClick={() => onPostClick(postId)}
              className="source-ref-button"
              title={`View post #${postId}`}
            >
              [{postId}]
            </button>
          );
        } else {
          // Keep original format if not in sources
          parts.push(`[${postId}]`);
        }
      } else {
        // Multiple post IDs - create separate buttons for each valid one
        const validPostIds = postIds.filter(id => sources.includes(id));
        const invalidPostIds = postIds.filter(id => !sources.includes(id));

        if (validPostIds.length > 0) {
          // Add buttons for valid posts
          validPostIds.forEach((postId, index) => {
            parts.push(
              <button
                key={`ref-${matchIndex}-${index}`}
                onClick={() => onPostClick(postId)}
                className="source-ref-button"
                title={`View post #${postId}`}
              >
                [{postId}]
              </button>
            );
          });
        }

        // Add text for invalid posts
        if (invalidPostIds.length > 0) {
          parts.push(
            <span key={`invalid-${matchIndex}`} style={{ margin: '0 2px' }}>
              [{invalidPostIds.join(', ')}]
            </span>
          );
        }
      }

      lastIndex = matchIndex + fullMatch.length;
    }

    // Add remaining text after the last match
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : [text];
  };

  // Custom components for ReactMarkdown
  const markdownComponents = {
    // Handle paragraph nodes - REMOVED Inline Styles
    p: ({ children }: any) => {
      return (
        <p>
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
    // Style for links - REMOVED Inline Styles (handled by prose)
    a: ({ href, children }: any) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    ),
    // Style for list items - REMOVED Inline Styles
    li: ({ children }: any) => {
      return (
        <li>
          {React.Children.map(children, (child) => {
            if (typeof child === 'string') {
              return processTextNode(child);
            }
            return child;
          })}
        </li>
      );
    },
  };

  return (
    <div className="expert-response-card">
      <div
        className="expert-response-markdown prose prose-base max-w-none breakable-markdown"
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
