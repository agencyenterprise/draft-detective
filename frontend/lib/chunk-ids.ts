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

    // Poll for the element (sidebar content loads async)
    const elementId = window.location.hash.slice(1);
    let attempts = 0;
    const intervalId = setInterval(() => {
      const element = document.getElementById(elementId);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        clearInterval(intervalId);
      } else if (++attempts >= 20) {
        clearInterval(intervalId);
      }
    }, 100);
  }, [validChunkIndices, onSelectChunk]);
}
