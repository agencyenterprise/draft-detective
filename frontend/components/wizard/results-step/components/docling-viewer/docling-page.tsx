import { useState } from 'react';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';
import type { DoclingPageInfo, DoclingRegion } from '@/lib/generated-api';
import { RegionOverlay } from './region-overlay';
import { getNextChunkIndex, type RegionWithChunks } from './utils';
import { useShare } from '@/context/share-context';

interface DoclingPageProps {
  page: DoclingPageInfo;
  pageNum: number;
  regions: RegionWithChunks[];
  selectedRegions: DoclingRegion[];
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
  const { shareToken } = useShare();
  const imageUrl = shareToken
    ? `${pageImagesBaseUrl}/${pageNum}?share_token=${encodeURIComponent(shareToken)}`
    : `${pageImagesBaseUrl}/${pageNum}`;
  const width = page.width;
  const height = page.height;
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
        width={width ?? 0}
        height={height ?? 0}
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
            const nextChunkIndex = getNextChunkIndex(selectedChunkIndex, region.chunkIndices);
            onChunkSelect(nextChunkIndex);
          };

          return (
            <RegionOverlay
              key={`${region.id}-${idx}`}
              region={region}
              pageWidth={width ?? 0}
              pageHeight={height ?? 0}
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
