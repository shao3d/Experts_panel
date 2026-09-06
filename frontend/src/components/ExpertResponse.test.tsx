import { describe, expect, it, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import ExpertResponse from './ExpertResponse';
import { CitationVerificationReport } from '../types/api';

// vitest runs without globals: true, so testing-library auto-cleanup does
// not register itself; clean up between tests explicitly.
afterEach(cleanup);

const report: CitationVerificationReport = {
  total_count: 3,
  verified_count: 2,
  partial_count: 1,
  unsupported_count: 0,
  verdicts: { '100': 'supported', '200': 'supported', '300': 'partial' },
  method: 'lexical+llm',
};

const baseProps = {
  answer: 'Эксперт советует RAG пайплайн [post:100].',
  sources: [100],
  onPostClick: () => {},
};

describe('ExpertResponse citation verification badge', () => {
  it('renders badge counts in Russian for Russian answers', () => {
    render(<ExpertResponse {...baseProps} verification={report} language="Russian" />);

    expect(screen.getByText(/2\/3 цитат подтверждено источниками/)).toBeTruthy();
    expect(screen.getByText(/1 частично/)).toBeTruthy();
  });

  it('renders badge counts in English for English answers', () => {
    render(<ExpertResponse {...baseProps} verification={report} language="English" />);

    expect(screen.getByText(/2\/3 citations verified against sources/)).toBeTruthy();
  });

  it('renders no badge when the report is absent', () => {
    const { container } = render(<ExpertResponse {...baseProps} />);

    expect(container.querySelector('.citation-verification-badge')).toBeNull();
  });

  it('renders no badge for an empty report', () => {
    const { container } = render(
      <ExpertResponse
        {...baseProps}
        verification={{ ...report, total_count: 0, verified_count: 0, verdicts: {} }}
      />,
    );

    expect(container.querySelector('.citation-verification-badge')).toBeNull();
  });

  it('keeps the answer markdown and clickable citations intact alongside the badge', () => {
    render(<ExpertResponse {...baseProps} verification={report} language="Russian" />);

    const citationButton = screen.getByRole('button', { name: '[100]' });
    expect(citationButton).toBeTruthy();
    expect(screen.getByText(/советует RAG пайплайн/)).toBeTruthy();
  });
});
