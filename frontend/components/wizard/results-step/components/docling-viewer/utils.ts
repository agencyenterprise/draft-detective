import type { ChunkToItems, DoclingPage } from '@/types/docling';
import type { RegionWithChunks } from './types';

export const getPageNumber = (page: DoclingPage): number => page.page_no ?? page.page ?? 0;

export function buildRegionsByPage(chunkToItems: ChunkToItems): Record<number, RegionWithChunks[]> {
  const regionMap = new Map<string, RegionWithChunks>();

  for (const [chunkIndexStr, regions] of Object.entries(chunkToItems)) {
    const chunkIndex = parseInt(chunkIndexStr, 10);
    if (isNaN(chunkIndex)) continue;

    for (const region of regions) {
      const existing = regionMap.get(region.id);
      if (existing) {
        existing.chunkIndices.push(chunkIndex);
      } else {
        regionMap.set(region.id, {
          ...region,
          chunkIndices: [chunkIndex],
        });
      }
    }
  }

  const byPage: Record<number, RegionWithChunks[]> = {};
  for (const region of regionMap.values()) {
    region.chunkIndices.sort((a, b) => a - b);
    const pageNum = region.page;
    (byPage[pageNum] ??= []).push(region);
  }

  return byPage;
}

export function getImageUrl(imageData: { uri?: string } | undefined, pageNum: number, baseUrl: string): string {
  if (imageData?.uri) {
    if (imageData.uri.startsWith('data:')) {
      return imageData.uri;
    }
    return `${baseUrl}/${imageData.uri}`;
  }
  return `${baseUrl}/page_${pageNum}.png`;
}

export function formatChunkLabel(region: RegionWithChunks, currentChunkPosition?: number): string {
  const hasMultipleChunks = region.chunkIndices.length > 1;

  if (hasMultipleChunks && currentChunkPosition !== undefined) {
    const currentChunk = region.chunkIndices[currentChunkPosition];
    return `Chunk ${currentChunk} (${currentChunkPosition + 1}/${region.chunkIndices.length})`;
  }

  if (hasMultipleChunks) {
    return `Chunks ${region.chunkIndices.join(', ')}`;
  }

  return `Chunk ${region.chunkIndices[0]}`;
}
