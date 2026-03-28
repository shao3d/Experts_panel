/**
 * MetaSynthesisSection - Cross-expert unified analysis
 *
 * Displays a synthesized summary that restructures information
 * from "per-expert" axis to "per-topic" axis.
 * Rendered ABOVE individual expert accordions.
 */

import React from 'react';
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
  // Dynamic title based on response language (detect from content)
  const isRussian = /[а-яА-ЯёЁ]/.test(metaSynthesis);
  const title = isRussian ? 'Сводный анализ' : 'Cross-Expert Analysis';
  const subtitle = isRussian
    ? `На основе ${expertCount} экспертов`
    : `Based on ${expertCount} experts`;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-blue-100 mb-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100">
        <span className="text-2xl" role="img" aria-label="brain">🧠</span>
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        <span className="ml-auto text-sm text-gray-500">{subtitle}</span>
      </div>

      {/* Content */}
      <div className="px-6 py-5">
        <div className="prose prose-base prose-blue max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {metaSynthesis}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};
