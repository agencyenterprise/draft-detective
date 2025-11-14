import { useState } from 'react';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';
import type { DoclingPage, Region } from '@/types/docling';
import { RegionOverlay } from './region-overlay';
import { getImageUrl, type RegionWithChunks } from './utils';

interface DoclingPageProps {
  page: DoclingPage;
  pageNum: number;
  regions: RegionWithChunks[];
  selectedRegions: Region[];
  selectedChunkIndex: number | null;
  pageImagesBaseUrl: string;
  onChunkSelect: (chunkIndex: number | null) => void;
}

export function DoclingPage({
  page,
  pageNum,
  regions,
  selectedRegions,
  selectedChunkIndex,
  pageImagesBaseUrl,
  onChunkSelect,
}: DoclingPageProps) {
  const [isLoading, setIsLoading] = useState(true);
  const imageUrl = getImageUrl(page.image as { uri?: string }, pageNum, pageImagesBaseUrl);
  const width = page.size?.width ?? page.width ?? 612;
  const height = page.size?.height ?? page.height ?? 792;
  const isFirstPage = pageNum === 0 || pageNum === 1;

  return (
    <div className="relative mx-auto bg-white shadow-lg" style={{ aspectRatio: `${width}/${height}` }}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 animate-pulse">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}
      <Image
        src={imageUrl}
        alt={`Page ${pageNum}`}
        width={width}
        height={height}
        className="w-full h-auto block"
        unoptimized
        loading={isFirstPage ? undefined : 'lazy'}
        priority={isFirstPage}
        onLoad={() => setIsLoading(false)}
      />

      <div className="absolute inset-0">
        {regions.map((region, idx) => {
          const isSelected = selectedRegions.some((r) => r.id === region.id);
          const currentChunkPosition = region.chunkIndices.indexOf(selectedChunkIndex ?? -1);
          const hasSelectedChunk = currentChunkPosition !== -1;

          const handleRegionClick = () => {
            if (currentChunkPosition === -1) {
              onChunkSelect(region.chunkIndices[0]);
            } else if (currentChunkPosition < region.chunkIndices.length - 1) {
              onChunkSelect(region.chunkIndices[currentChunkPosition + 1]);
            } else {
              onChunkSelect(null);
            }
          };

          return (
            <RegionOverlay
              key={`${region.id}-${idx}`}
              region={region}
              pageWidth={width}
              pageHeight={height}
              isSelected={isSelected || hasSelectedChunk}
              currentChunkPosition={hasSelectedChunk ? currentChunkPosition : undefined}
              onSelect={handleRegionClick}
            />
          );
        })}
      </div>
    </div>
  );
}
