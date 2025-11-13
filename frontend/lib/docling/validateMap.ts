import type { ChunkToItems, Region } from '@/types/docling';

export function getRegionsForChunk(chunkToItems: ChunkToItems | undefined | null, chunkIndex: number): Region[] {
  const regions = chunkToItems?.[String(chunkIndex)];
  return Array.isArray(regions) ? regions : [];
}
