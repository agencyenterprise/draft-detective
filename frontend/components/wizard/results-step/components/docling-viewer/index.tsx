'use client';

import { getRegionsForChunk } from '@/lib/docling/validateMap';
import { useMemo } from 'react';
import { DoclingPage } from './docling-page';
import type { DoclingViewerProps } from './types';
import { buildRegionsByPage, getPageNumber } from './utils';

export function DoclingViewer({
  docJson,
  chunkToItems,
  pageImagesBaseUrl,
  selectedChunkIndex,
  onChunkSelect,
}: DoclingViewerProps) {
  const pages = useMemo(() => {
    if (!docJson?.pages) return [];
    return Object.values(docJson.pages).sort((a, b) => getPageNumber(a) - getPageNumber(b));
  }, [docJson]);

  const selectedRegions = useMemo(() => {
    if (selectedChunkIndex === null) return [];
    return getRegionsForChunk(chunkToItems, selectedChunkIndex);
  }, [chunkToItems, selectedChunkIndex]);

  const regionsByPage = useMemo(() => buildRegionsByPage(chunkToItems), [chunkToItems]);

  if (pages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p>No pages available for rendering</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-4">
      <div className="space-y-6">
        {pages.map((page) => {
          const pageNum = getPageNumber(page);
          return (
            <DoclingPage
              key={pageNum}
              page={page}
              pageNum={pageNum}
              regions={regionsByPage[pageNum] ?? []}
              selectedRegions={selectedRegions}
              selectedChunkIndex={selectedChunkIndex}
              pageImagesBaseUrl={pageImagesBaseUrl}
              onChunkSelect={onChunkSelect}
            />
          );
        })}
      </div>
    </div>
  );
}
