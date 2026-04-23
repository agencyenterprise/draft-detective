/**
 * Utilities for parsing line-range selections from the URL hash.
 */

import { useEffect, useRef } from 'react';
import type { LineRange } from '@/lib/stores/document-explorer-store';

/**
 * Parse hash format for line ranges: #L5 (single line) or #L5-15 (range).
 * Returns a [start, end] tuple, or null if the hash doesn't match.
 */
export function parseLineHash(hash: string): LineRange | null {
  if (!hash.startsWith('#')) return null;

  const rangeMatch = hash.match(/^#L(\d+)-(\d+)$/);
  if (rangeMatch) {
    const start = parseInt(rangeMatch[1], 10);
    const end = parseInt(rangeMatch[2], 10);
    return [Math.min(start, end), Math.max(start, end)];
  }

  const singleMatch = hash.match(/^#L(\d+)$/);
  if (singleMatch) {
    const line = parseInt(singleMatch[1], 10);
    return [line, line];
  }

  return null;
}

/**
 * Hook for handling line-range hash navigation.
 * Supports #L5 (single) and #L5-15 (range) formats.
 */
export function useLineHashNavigation(onSelectRange: (range: LineRange) => void): void {
  const lastProcessedHash = useRef<string | null>(null);

  useEffect(() => {
    const handleHashChange = () => {
      const currentHash = window.location.hash;
      const parsed = parseLineHash(currentHash);
      if (!parsed) return;

      if (lastProcessedHash.current === currentHash) return;
      lastProcessedHash.current = currentHash;

      onSelectRange(parsed);
    };

    handleHashChange();

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [onSelectRange]);
}
