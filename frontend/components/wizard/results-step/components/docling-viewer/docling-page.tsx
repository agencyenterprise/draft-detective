import type { DoclingPageProps } from './types';
import { RegionOverlay } from './region-overlay';
import { getImageUrl } from './utils';

export function DoclingPage({
  page,
  pageNum,
  regions,
  selectedRegions,
  selectedChunkIndex,
  pageImagesBaseUrl,
  onChunkSelect,
}: DoclingPageProps) {
  const imageUrl = getImageUrl(page.image, pageNum, pageImagesBaseUrl);
  const width = page.size?.width ?? page.width ?? 612;
  const height = page.size?.height ?? page.height ?? 792;

  return (
    <div className="relative mx-auto bg-white shadow-lg">
      <img
        src={imageUrl}
        alt={`Page ${pageNum}`}
        className="w-full h-auto block"
        style={{
          maxWidth: '100%',
          height: 'auto',
        }}
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
