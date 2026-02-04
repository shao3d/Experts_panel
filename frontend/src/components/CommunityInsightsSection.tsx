/**
 * CommunityInsightsSection - Displays Reddit community insights
 * 
 * Shows AI-synthesized analysis of Reddit discussions including:
 * - Reality Check: Bugs, edge cases, hardware issues
 * - Hacks & Workarounds: Community solutions
 * - Vibe Check: Sentiment and opinions
 */

import React, { useState } from 'react';
import { RedditResponse, RedditSource } from '../types/api';

interface CommunityInsightsSectionProps {
  redditResponse: RedditResponse | null | undefined;
  isLoading?: boolean;
}

/**
 * Format markdown-like content with basic styling
 */
const FormattedContent: React.FC<{ content: string | null | undefined }> = ({ content }) => {
  // FIX: Handle null/undefined/empty content gracefully
  if (!content || content.trim() === '') {
    return <div className="empty-synthesis">No analysis available.</div>;
  }
  
  const lines = content.split('\n');
  
  return (
    <div className="formatted-content">
      {lines.map((line, index) => {
        // Headers (### Header)
        if (line.startsWith('### ')) {
          return (
            <h4 key={index} className="content-header">
              {line.replace('### ', '')}
            </h4>
          );
        }
        
        // Subheaders (## Header)
        if (line.startsWith('## ')) {
          return (
            <h3 key={index} className="content-subheader">
              {line.replace('## ', '')}
            </h3>
          );
        }
        
        // Bullet points (- item or * item)
        if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
          return (
            <li key={index} className="content-bullet">
              {formatInlineMarkdown(line.replace(/^[*-]\s*/, ''))}
            </li>
          );
        }
        
        // Empty lines
        if (line.trim() === '') {
          return <div key={index} className="content-spacer" />;
        }
        
        // Regular paragraph
        return (
          <p key={index} className="content-paragraph">
            {formatInlineMarkdown(line)}
          </p>
        );
      })}
    </div>
  );
};

/**
 * Format inline markdown (bold, italic, links)
 * FIX: Uses safer iterative parsing instead of regex to avoid ReDoS
 */
const formatInlineMarkdown = (text: string): React.ReactNode => {
  if (!text) return text;
  
  const elements: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;
  
  while (remaining.length > 0) {
    // Find earliest special marker
    const boldIndex = remaining.indexOf('**');
    const italicIndex = remaining.indexOf('*');
    const linkStartIndex = remaining.indexOf('[');
    
    // Find which comes first
    let earliestIndex = Infinity;
    let markerType: 'bold' | 'italic' | 'link' | null = null;
    
    if (boldIndex !== -1 && boldIndex < earliestIndex) {
      earliestIndex = boldIndex;
      markerType = 'bold';
    }
    if (italicIndex !== -1 && italicIndex < earliestIndex && italicIndex !== boldIndex) {
      earliestIndex = italicIndex;
      markerType = 'italic';
    }
    if (linkStartIndex !== -1 && linkStartIndex < earliestIndex) {
      earliestIndex = linkStartIndex;
      markerType = 'link';
    }
    
    // If no markers found, add rest as text
    if (markerType === null) {
      elements.push(<span key={key++}>{remaining}</span>);
      break;
    }
    
    // Add text before marker
    if (earliestIndex > 0) {
      elements.push(<span key={key++}>{remaining.slice(0, earliestIndex)}</span>);
    }
    
    // Process marker
    const afterMarker = remaining.slice(earliestIndex + (markerType === 'bold' ? 2 : 1));
    
    if (markerType === 'bold') {
      const endIndex = afterMarker.indexOf('**');
      if (endIndex !== -1) {
        elements.push(<strong key={key++}>{afterMarker.slice(0, endIndex)}</strong>);
        remaining = afterMarker.slice(endIndex + 2);
      } else {
        // No closing marker, treat as text
        elements.push(<span key={key++}>{remaining.slice(earliestIndex)}</span>);
        break;
      }
    } else if (markerType === 'italic') {
      const endIndex = afterMarker.indexOf('*');
      if (endIndex !== -1) {
        elements.push(<em key={key++}>{afterMarker.slice(0, endIndex)}</em>);
        remaining = afterMarker.slice(endIndex + 1);
      } else {
        elements.push(<span key={key++}>{remaining.slice(earliestIndex)}</span>);
        break;
      }
    } else if (markerType === 'link') {
      // Look for ](url) pattern
      const textEndIndex = remaining.indexOf(']', earliestIndex);
      const urlStartIndex = textEndIndex !== -1 ? remaining.indexOf('(', textEndIndex) : -1;
      const urlEndIndex = urlStartIndex !== -1 ? remaining.indexOf(')', urlStartIndex) : -1;
      
      if (textEndIndex !== -1 && urlStartIndex === textEndIndex + 1 && urlEndIndex !== -1) {
        const linkText = remaining.slice(earliestIndex + 1, textEndIndex);
        const url = remaining.slice(urlStartIndex + 1, urlEndIndex);
        elements.push(
          <a key={key++} href={url} target="_blank" rel="noopener noreferrer" className="content-link">
            {linkText}
          </a>
        );
        remaining = remaining.slice(urlEndIndex + 1);
      } else {
        elements.push(<span key={key++}>{remaining[earliestIndex]}</span>);
        remaining = remaining.slice(earliestIndex + 1);
      }
    }
  }
  
  return <>{elements}</>;
};

/**
 * Source card for a Reddit post
 */
const SourceCard: React.FC<{ source: RedditSource }> = ({ source }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div className="source-card">
      <div 
        className="source-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="source-toggle">{isExpanded ? '▼' : '▶'}</span>
        <span className="source-title" title={source.title || 'Untitled'}>
          {/* FIX: Add null check for title */}
          {(source.title?.length || 0) > 60 
            ? (source.title || 'Untitled').slice(0, 60) + '...' 
            : (source.title || 'Untitled')}
        </span>
        <span className="source-subreddit">r/{source.subreddit}</span>
      </div>
      
      {isExpanded && (
        <div className="source-details">
          <div className="source-stats">
            <span className="stat">⬆️ {source.score}</span>
            <span className="stat">💬 {source.comments_count} comments</span>
          </div>
          <a 
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="source-link"
          >
            View on Reddit →
          </a>
        </div>
      )}
    </div>
  );
};

/**
 * Loading skeleton for community insights
 */
const LoadingSkeleton: React.FC = () => (
  <div className="community-insights loading">
    <div className="skeleton-header" />
    <div className="skeleton-content">
      <div className="skeleton-line" />
      <div className="skeleton-line" />
      <div className="skeleton-line short" />
    </div>
    <div className="skeleton-sources">
      <div className="skeleton-source" />
      <div className="skeleton-source" />
    </div>
  </div>
);

/**
 * Empty state when no Reddit data
 */
const EmptyState: React.FC = () => (
  <div className="community-insights empty">
    <div className="empty-icon">🤷</div>
    <div className="empty-title">No community discussions found</div>
    <div className="empty-message">
      Try rephrasing your query or check back later for new discussions.
    </div>
  </div>
);

/**
 * Error state when Reddit fetch failed
 */
const ErrorState: React.FC<{ onRetry?: () => void }> = ({ onRetry }) => (
  <div className="community-insights error">
    <div className="error-icon">⚠️</div>
    <div className="error-title">Community insights temporarily unavailable</div>
    <div className="error-message">
      We couldn't fetch Reddit discussions at this time. Expert responses are still available.
    </div>
    {onRetry && (
      <button className="retry-button" onClick={onRetry}>
        Retry
      </button>
    )}
  </div>
);

/**
 * Main Community Insights Section component
 */
export const CommunityInsightsSection: React.FC<CommunityInsightsSectionProps> = ({
  redditResponse,
  isLoading = false
}) => {
  const [showRaw, setShowRaw] = useState(false);
  const [showSources, setShowSources] = useState(true);

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // No Reddit response at all (null/undefined)
  if (!redditResponse) {
    return <ErrorState />;
  }

  // Empty response (0 posts found)
  if (redditResponse.found_count === 0) {
    return <EmptyState />;
  }

  return (
    <div className="community-insights">
      {/* Header */}
      <div className="insights-header">
        <div className="header-left">
          <span className="header-icon">👥</span>
          <h3 className="header-title">Community Insights</h3>
          <span className="header-badge">
            {redditResponse.found_count} posts from Reddit
          </span>
        </div>
        <div className="header-actions">
          <button 
            className={`action-button ${showSources ? 'active' : ''}`}
            onClick={() => setShowSources(!showSources)}
            title="Toggle sources"
          >
            📋
          </button>
          <button 
            className={`action-button ${showRaw ? 'active' : ''}`}
            onClick={() => setShowRaw(!showRaw)}
            title="Show raw markdown"
          >
            📝
          </button>
        </div>
      </div>

      {/* AI Synthesis */}
      <div className="insights-synthesis">
        <FormattedContent content={redditResponse.synthesis} />
      </div>

      {/* Raw Markdown (toggleable) */}
      {showRaw && (
        <div className="insights-raw">
          <h4 className="raw-title">Raw Reddit Results</h4>
          <pre className="raw-content">{redditResponse.markdown}</pre>
        </div>
      )}

      {/* Sources */}
      {showSources && redditResponse.sources.length > 0 && (
        <div className="insights-sources">
          <h4 className="sources-title">
            📚 Sources ({redditResponse.sources.length})
          </h4>
          <div className="sources-list">
            {redditResponse.sources.map((source, index) => (
              <SourceCard key={index} source={source} />
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="insights-footer">
        <span className="footer-meta">
          Analyzed in {(redditResponse.processing_time_ms / 1000).toFixed(1)}s
        </span>
        <a 
          href={`https://reddit.com/search/?q=${encodeURIComponent(redditResponse.query)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="footer-link"
        >
          Search on Reddit →
        </a>
      </div>
    </div>
  );
};

export default CommunityInsightsSection;
