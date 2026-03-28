/**
 * MetaSynthesisSection - Cross-expert unified analysis (accordion)
 *
 * Displays a synthesized summary that restructures information
 * from "per-expert" axis to "per-topic" axis.
 * Rendered ABOVE individual expert accordions, expanded by default.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MetaSynthesisSectionProps {
  metaSynthesis: string;
  expertCount: number;
}

export const MetaSynthesisSection: React.FC<MetaSynthesisSectionProps> = ({
  metaSynthesis,
  expertCount,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  // Dynamic title based on response language (detect from content)
  const isRussian = /[а-яА-ЯёЁ]/.test(metaSynthesis);
  const title = isRussian ? 'Сводный анализ' : 'Cross-Expert Analysis';
  const subtitle = isRussian
    ? `${expertCount} экспертов`
    : `${expertCount} experts`;

  return (
    <div className="expert-accordion">
      {/* Header - always visible, clickable */}
      <div className="accordion-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="accordion-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="expert-name">{title}</span>
        <span className="channel-name">{subtitle}</span>
      </div>

      {/* Body - only when expanded */}
      {isExpanded && (
        <div className="px-6 py-5 bg-white">
          <div className="prose prose-base prose-blue max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {metaSynthesis}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};
