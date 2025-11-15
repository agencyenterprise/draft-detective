import type { ChunkToItemsOutput, DoclingRegion } from '@/lib/generated-api';

export type ChunkToItems = Record<string, DoclingRegion[]>;

export function validateChunkToItems(chunkToItems: ChunkToItems | undefined | null): boolean {
  if (!chunkToItems) return false;
  if (typeof chunkToItems !== 'object') return false;

  // Check if all values are arrays
  return Object.values(chunkToItems).every(Array.isArray);
}

export function getRegionsForChunk(chunkToItems: ChunkToItems | undefined | null, chunkIndex: number): DoclingRegion[] {
  if (!validateChunkToItems(chunkToItems)) {
    console.warn('Invalid chunkToItems structure', chunkToItems);
    return [];
  }

  const regions = chunkToItems![String(chunkIndex)];
  return Array.isArray(regions) ? regions : [];
}
