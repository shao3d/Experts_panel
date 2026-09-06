import { describe, expect, it } from 'vitest';
import { splitByFragment } from './highlightEvidence';

describe('splitByFragment', () => {
  const text = 'Для продакшена я рекомендую начинать с простого RAG пайплайна и векторной базы Qdrant.';
  const fragment = 'начинать с простого RAG пайплайна';

  it('splits text into before/fragment/around parts', () => {
    const parts = splitByFragment(text, fragment);

    expect(parts).not.toBeNull();
    expect(parts!.before).toBe('Для продакшена я рекомендую ');
    expect(parts!.fragment).toBe(fragment);
    expect(parts!.after).toBe(' и векторной базы Qdrant.');
  });

  it('handles a fragment at the very start', () => {
    const parts = splitByFragment(text, 'Для продакшена');

    expect(parts).not.toBeNull();
    expect(parts!.before).toBe('');
    expect(parts!.after).toBe(' я рекомендую начинать с простого RAG пайплайна и векторной базы Qdrant.');
  });

  it('handles a fragment at the very end', () => {
    const parts = splitByFragment(text, 'Qdrant.');

    expect(parts).not.toBeNull();
    expect(parts!.after).toBe('');
  });

  it('returns null when the fragment is not in the text', () => {
    expect(splitByFragment(text, 'этого предложения тут нет')).toBeNull();
  });

  it('returns null for empty inputs', () => {
    expect(splitByFragment('', fragment)).toBeNull();
    expect(splitByFragment(text, '')).toBeNull();
  });
});
