import type { ChunkToItems, Region } from '@/types/docling';

export function getRegionsForChunk(chunkToItems: ChunkToItems | undefined | null, chunkIndex: number): Region[] {
  if (!chunkToItems) {
    return [];
  }

  const key = String(chunkIndex);
  const regions = chunkToItems[key];

  if (!regions || !Array.isArray(regions)) {
    return [];
  }

  return regions.filter(isValidRegion);
}

function isValidRegion(region: unknown): region is Region {
  return (
    region &&
    typeof region === 'object' &&
    typeof region.id === 'string' &&
    typeof region.page === 'number' &&
    region.bbox &&
    typeof region.bbox === 'object' &&
    typeof region.bbox.l === 'number' &&
    typeof region.bbox.b === 'number' &&
    typeof region.bbox.r === 'number' &&
    typeof region.bbox.t === 'number' &&
    typeof region.kind === 'string'
  );
}

export function hasRegions(chunkToItems: ChunkToItems | undefined | null, chunkIndex: number): boolean {
  return getRegionsForChunk(chunkToItems, chunkIndex).length > 0;
}

export function getChunksWithRegions(chunkToItems: ChunkToItems | undefined | null): number[] {
  if (!chunkToItems) {
    return [];
  }

  return Object.keys(chunkToItems)
    .map((key) => parseInt(key, 10))
    .filter((index) => !isNaN(index))
    .sort((a, b) => a - b);
}

export function getTotalRegionCount(chunkToItems: ChunkToItems | undefined | null): number {
  if (!chunkToItems) {
    return 0;
  }

  const uniqueIds = new Set<string>();
  for (const regions of Object.values(chunkToItems)) {
    if (Array.isArray(regions)) {
      for (const region of regions) {
        if (isValidRegion(region)) {
          uniqueIds.add(region.id);
        }
      }
    }
  }

  return uniqueIds.size;
}

export function validateChunkToItems(chunkToItems: unknown): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!chunkToItems) {
    errors.push('ChunkToItems is null or undefined');
    return { valid: false, errors };
  }

  if (typeof chunkToItems !== 'object') {
    errors.push('ChunkToItems must be an object');
    return { valid: false, errors };
  }

  for (const [key, value] of Object.entries(chunkToItems)) {
    const chunkIndex = parseInt(key, 10);
    if (isNaN(chunkIndex)) {
      errors.push(`Invalid chunk index: "${key}" is not a number`);
      continue;
    }

    if (!Array.isArray(value)) {
      errors.push(`Chunk ${chunkIndex}: value is not an array`);
      continue;
    }

    (value as unknown[]).forEach((region, idx) => {
      if (!isValidRegion(region)) {
        errors.push(`Chunk ${chunkIndex}, region ${idx}: invalid region structure`);
      }
    });
  }

  return { valid: errors.length === 0, errors };
}
