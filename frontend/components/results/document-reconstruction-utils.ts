/**
 * Detects block-level markdown syntax from a chunk.
 * Returns the block prefix (e.g., "# ", "- ", "> ") or null for paragraphs.
 */
export function detectBlockSyntax(chunk: string): string | null {
  if (!chunk || !chunk.trim()) {
    return null;
  }

  const trimmed = chunk.trimStart();

  // Headings: #, ##, ###, etc. (1-6 # characters followed by space)
  const headingMatch = trimmed.match(/^(#{1,6})\s/);
  if (headingMatch) {
    return headingMatch[0];
  }

  // Unordered lists: -, *, + followed by space
  if (/^[-*+]\s/.test(trimmed)) {
    return trimmed.match(/^[-*+]\s/)?.[0] || null;
  }

  // Ordered lists: digits followed by . and space
  // const orderedListMatch = trimmed.match(/^\d+\.\s/);
  // if (orderedListMatch) {
  //   return orderedListMatch[0];
  // }

  // Blockquotes: > followed by space
  if (/^>\s/.test(trimmed)) {
    return '> ';
  }

  // Paragraphs: no block-level syntax
  return null;
}

/**
 * Extracts content from a chunk by removing block-level syntax.
 * Preserves inline markdown and returns the content without the block prefix.
 */
export function extractChunkContent(chunk: string, blockPrefix: string | null): string {
  if (!chunk) {
    return '';
  }

  if (!blockPrefix) {
    return chunk.trim();
  }

  // Remove the block prefix from the start of the chunk
  const trimmed = chunk.trimStart();
  if (trimmed.startsWith(blockPrefix)) {
    return trimmed.slice(blockPrefix.length).trim();
  }

  // If the prefix doesn't match (shouldn't happen, but handle gracefully)
  return chunk.trim();
}
