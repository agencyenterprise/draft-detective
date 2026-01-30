'use client';

import type { DoclingPageInfo } from '@/lib/generated-api';
import { getRegionsForChunk } from '@/lib/docling/validateMap';
import { useMemo } from 'react';
import { DoclingPage } from './docling-page';
import { buildRegionsByPage, getPageNumber, type ChunkToItems } from './utils';

interface DoclingViewerProps {
  pages: DoclingPageInfo[];
  chunkToItems: ChunkToItems;
  pageImagesBaseUrl: string;
  selectedChunkIndices: number[];
  onChunkSelect: (chunkIndex: number | null) => void;
}

export function DoclingViewer({
  pages,
  chunkToItems,
  pageImagesBaseUrl,
  selectedChunkIndices,
  onChunkSelect,
}: DoclingViewerProps) {
  const sortedPages = useMemo(() => {
    if (!pages) return [];
    return [...pages].sort((a, b) => getPageNumber(a) - getPageNumber(b));
  }, [pages]);

  const selectedRegions = useMemo(() => {
    if (selectedChunkIndices.length === 0) return [];
    return selectedChunkIndices.flatMap((idx) => getRegionsForChunk(chunkToItems, idx));
  }, [chunkToItems, selectedChunkIndices]);

  const regionsByPage = useMemo(() => buildRegionsByPage(chunkToItems), [chunkToItems]);

  if (sortedPages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p>No pages available for rendering</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-4">
      <div className="space-y-6">
        {sortedPages.map((page) => {
          const pageNum = getPageNumber(page);
          return (
            <DoclingPage
              key={pageNum}
              page={page}
              pageNum={pageNum}
              regions={regionsByPage[pageNum] ?? []}
              selectedRegions={selectedRegions}
              selectedChunkIndices={selectedChunkIndices}
              pageImagesBaseUrl={pageImagesBaseUrl}
              onChunkSelect={onChunkSelect}
            />
          );
        })}
      </div>
    </div>
  );
}
