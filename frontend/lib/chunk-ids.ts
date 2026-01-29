/**
 * Shared utilities for generating stable chunk/claim element IDs.
 * Used for URL hash navigation and scroll-to functionality.
 */

import { useEffect, useRef } from 'react';

export const getChunkId = (chunkIndex: number): string => `chunk-${chunkIndex}`;

export const getClaimId = (chunkIndex: number, claimIndex: number): string => `chunk-${chunkIndex}-claim-${claimIndex}`;

export function getIssueId(chunkIndex: number | null | undefined, claimIndex?: number | null): string | undefined {
  if (chunkIndex == null) return undefined;
  return claimIndex != null ? getClaimId(chunkIndex, claimIndex) : getChunkId(chunkIndex);
}

export function parseChunkHash(hash: string): { chunkIndex: number; claimIndex?: number } | null {
  if (!hash.startsWith('#')) return null;

  const match = hash.match(/^#chunk-(\d+)(?:-claim-(\d+))?$/);
  if (!match) return null;

  return {
    chunkIndex: parseInt(match[1], 10),
    claimIndex: match[2] ? parseInt(match[2], 10) : undefined,
  };
}

/**
 * Parse hash format for multiple chunks: #chunks-1,2,3 | #chunk-3
 * Returns array of chunk indices, or null if invalid format
 */
export function parseMultiChunkHash(hash: string): number[] | null {
  if (!hash.startsWith('#')) return null;

  const multiMatch = hash.match(/^#chunks-(\d+(?:,\d+)*)$/);
  if (multiMatch) {
    return multiMatch[1].split(',').map((s) => parseInt(s, 10));
  }

  const singleMatch = hash.match(/^#chunk-(\d+)$/);
  if (singleMatch) {
    return [parseInt(singleMatch[1], 10)];
  }

  return null;
}

export function useChunkHashNavigation(
  validChunkIndices: number[] | undefined,
  onSelectChunk: (chunkIndex: number) => void,
): void {
  const hasHandled = useRef(false);

  useEffect(() => {
    if (hasHandled.current || !validChunkIndices?.length) return;

    const parsed = parseChunkHash(window.location.hash);
    if (!parsed || !validChunkIndices.includes(parsed.chunkIndex)) return;

    onSelectChunk(parsed.chunkIndex);
    hasHandled.current = true;
  }, [validChunkIndices, onSelectChunk]);
}

/**
 * Hook for handling multi-chunk hash navigation (#chunks-1,2,3 format).
 * Supports both #chunk-N (single) and #chunks-N,M,O (multiple) formats.
 */
export function useMultiChunkHashNavigation(
  validChunkIndices: number[] | undefined,
  onSelectChunks: (chunkIndices: number[]) => void,
): void {
  const lastProcessedHash = useRef<string | null>(null);

  useEffect(() => {
    const handleHashChange = () => {
      if (!validChunkIndices?.length) {
        return;
      }

      const currentHash = window.location.hash;
      const parsed = parseMultiChunkHash(currentHash);

      if (!parsed) {
        return;
      }

      const validParsed = parsed.filter((idx) => validChunkIndices.includes(idx));

      if (validParsed.length === 0) {
        return;
      }

      if (lastProcessedHash.current === currentHash) {
        return;
      }
      lastProcessedHash.current = currentHash;

      onSelectChunks(validParsed);

      let attempts = 0;
      const intervalId = setInterval(() => {
        const element = document.querySelector(`[data-chunk-index="${validParsed[0]}"]`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          clearInterval(intervalId);
        } else if (++attempts >= 20) {
          clearInterval(intervalId);
        }
      }, 100);
    };

    handleHashChange();

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [validChunkIndices, onSelectChunks]);
}
