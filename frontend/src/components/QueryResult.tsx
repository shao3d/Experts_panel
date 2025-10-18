/**
 * Query result component for displaying answer and sources.
 * Shows the final response from backend.
 */

import React from 'react';
import { QueryResponse } from '../types/api';

interface QueryResultProps {
  /** Query response from backend */
  result: QueryResponse;
}

/**
 * Query result component showing answer and statistics
 */
export const QueryResult: React.FC<QueryResultProps> = ({ result }) => {
  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Результат</h2>

      {/* Main Answer */}
      <div style={styles.answer}>
        <h3 style={styles.sectionTitle}>Ответ:</h3>
        <div style={styles.answerText}>
          {result.answer}
        </div>
      </div>

      {/* Main Sources */}
      <div style={styles.sources}>
        <h3 style={styles.sectionTitle}>
          Источники ({result.main_sources.length}):
        </h3>
        <div style={styles.sourceList}>
          {result.main_sources.map((sourceId) => (
            <div key={sourceId} style={styles.sourceItem}>
              <span style={styles.sourceIcon}>📄</span>
              <span>Пост #{sourceId}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Statistics */}
      <div style={styles.stats}>
        <h3 style={styles.sectionTitle}>Статистика:</h3>
        <div style={styles.statsGrid}>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Проанализировано постов:</span>
            <span style={styles.statValue}>{result.posts_analyzed}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Уверенность:</span>
            <span style={styles.statValue}>{result.confidence}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Время обработки:</span>
            <span style={styles.statValue}>
              {(result.processing_time_ms / 1000).toFixed(2)} сек
            </span>
          </div>
          {result.has_expert_comments && (
            <div style={styles.statItem}>
              <span style={styles.statLabel}>Комментарии экспертов:</span>
              <span style={styles.statValue}>
                {result.expert_comments_included}
              </span>
            </div>
          )}
          {result.token_usage && (
            <div style={styles.statItem}>
              <span style={styles.statLabel}>Токены:</span>
              <span style={styles.statValue}>
                {result.token_usage.total_tokens}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Relevance Distribution */}
      {Object.keys(result.relevance_distribution).length > 0 && (
        <div style={styles.distribution}>
          <h3 style={styles.sectionTitle}>Распределение по релевантности:</h3>
          <div style={styles.distributionList}>
            {Object.entries(result.relevance_distribution).map(([level, count]) => (
              <div key={level} style={styles.distributionItem}>
                <span>{level}:</span>
                <span style={styles.distributionCount}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Simple inline styles for MVP
const styles = {
  container: {
    marginBottom: '24px'
  },
  title: {
    fontSize: '24px',
    fontWeight: '600' as const,
    marginBottom: '20px',
    color: '#333'
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: '600' as const,
    marginBottom: '12px',
    color: '#667eea'
  },
  answer: {
    marginBottom: '24px',
    padding: '20px',
    backgroundColor: 'white',
    borderRadius: '8px',
    border: '2px solid #667eea'
  },
  answerText: {
    fontSize: '16px',
    lineHeight: '1.6',
    color: '#333',
    whiteSpace: 'pre-wrap' as const
  },
  sources: {
    marginBottom: '24px',
    padding: '16px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px'
  },
  sourceList: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '8px'
  },
  sourceItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    backgroundColor: 'white',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    fontSize: '14px'
  },
  sourceIcon: {
    fontSize: '16px'
  },
  stats: {
    marginBottom: '24px',
    padding: '16px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px'
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px'
  },
  statLabel: {
    fontSize: '13px',
    color: '#666'
  },
  statValue: {
    fontSize: '18px',
    fontWeight: '600' as const,
    color: '#333'
  },
  distribution: {
    padding: '16px',
    backgroundColor: '#f8f9fa',
    borderRadius: '8px'
  },
  distributionList: {
    display: 'flex',
    gap: '16px',
    flexWrap: 'wrap' as const
  },
  distributionItem: {
    display: 'flex',
    gap: '8px',
    fontSize: '14px'
  },
  distributionCount: {
    fontWeight: '600' as const,
    color: '#667eea'
  }
};

export default QueryResult;
