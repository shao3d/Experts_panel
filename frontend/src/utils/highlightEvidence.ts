/**
 * Evidence highlighting helpers for the citation verification viewer.
 *
 * The backend reports the author's passage a claim rests on as a plain
 * substring of the source text. The displayed post text may differ slightly
 * from the text the verification ran on (e.g. translation, media
 * placeholders), so we anchor by substring search instead of offsets.
 */

export type HighlightedParts = {
  before: string;
  fragment: string;
  after: string;
};

/**
 * Split text into before/fragment/around parts for highlighting.
 * Returns null when the fragment is not found in the text.
 */
export function splitByFragment(
  text: string,
  fragmentText: string,
): HighlightedParts | null {
  if (!text || !fragmentText) {
    return null;
  }

  const index = text.indexOf(fragmentText);
  if (index === -1) {
    return null;
  }

  return {
    before: text.slice(0, index),
    fragment: text.slice(index, index + fragmentText.length),
    after: text.slice(index + fragmentText.length),
  };
}
