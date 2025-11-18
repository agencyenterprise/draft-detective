import type { DoclingPageInfo, DoclingRegion } from '@/lib/generated-api';

export type ChunkToItems = Record<string, DoclingRegion[]>;
export type RegionWithChunks = DoclingRegion & { chunkIndices: number[] };

export const getPageNumber = (page: DoclingPageInfo): number => {
  const pageNum = page.pageNo ?? page.page;
  if (pageNum === null || pageNum === undefined) {
    console.warn('Page number not found in DoclingPageInfo', page);
    return 0;
  }
  return pageNum;
};

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

export function getNextChunkIndex(currentChunkIndex: number | null, chunkIndices: number[]): number | null {
  if (chunkIndices.length === 0) return null;

  const currentPosition = chunkIndices.indexOf(currentChunkIndex ?? -1);

  if (currentPosition === -1) return chunkIndices[0];
  if (currentPosition < chunkIndices.length - 1) return chunkIndices[currentPosition + 1];

  return null; // Cycle complete
}

export function formatChunkLabel(
  region: RegionWithChunks,
  currentChunkPosition?: number,
  includeInteractionHint: boolean = false,
): string {
  const hasMultipleChunks = region.chunkIndices.length > 1;

  let label = '';
  if (hasMultipleChunks && currentChunkPosition !== undefined) {
    const currentChunk = region.chunkIndices[currentChunkPosition];
    label = `Chunk ${currentChunk} (${currentChunkPosition + 1}/${region.chunkIndices.length})`;
  } else if (hasMultipleChunks) {
    label = `Chunks ${region.chunkIndices.join(', ')}`;
  } else {
    label = `Chunk ${region.chunkIndices[0]}`;
  }

  if (includeInteractionHint && hasMultipleChunks) label += ' (click to cycle)';

  return label;
}
