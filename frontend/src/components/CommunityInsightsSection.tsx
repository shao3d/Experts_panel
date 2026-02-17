/**
 * CommunityInsightsSection - Displays Reddit community insights
 * 
 * Shows AI-synthesized analysis of Reddit discussions including:
 * - Reality Check: Bugs, edge cases, hardware issues
 * - Hacks & Workarounds: Community solutions
 * - Vibe Check: Sentiment and opinions
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RedditResponse } from '../types/api';

interface CommunityInsightsSectionProps {
  redditResponse: RedditResponse | null | undefined;
  isLoading?: boolean;
  isEnabled?: boolean;
}

/**
 * Format markdown-like content with proper styling using ReactMarkdown
 */
const FormattedContent: React.FC<{ content: string | null | undefined }> = ({ content }) => {
  if (!content || content.trim() === '') {
    return <div className="empty-synthesis">No analysis available.</div>;
  }
  
  return (
    <div className="formatted-content prose prose-base prose-blue max-w-none">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        components={{
          // Map markdown headers to our existing CSS classes
          h3: ({node, ...props}) => <h3 className="content-subheader" {...props} />,
          h4: ({node, ...props}) => <h4 className="content-header" {...props} />,
          h5: ({node, ...props}) => <h5 className="content-sub-subheader" {...props} />,
          // Map list items
          li: ({node, ...props}) => <li className="content-bullet" {...props} />,
          // Map paragraphs
          p: ({node, ...props}) => <p className="content-paragraph" {...props} />,
          // Map links
          a: ({node, ...props}) => <a className="content-link" target="_blank" rel="noopener noreferrer" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
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
  isLoading = false,
  isEnabled = true
}) => {
  // If explicitly disabled in UI, don't show anything at all
  if (!isEnabled) {
    return null;
  }

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
          <h3 className="header-title">Reddit Insights</h3>
          <span className="header-badge">
            {redditResponse.found_count} posts from Reddit
          </span>
        </div>
      </div>

      {/* AI Synthesis */}
      <div className="insights-synthesis">
        <FormattedContent content={redditResponse.synthesis} />
      </div>



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
