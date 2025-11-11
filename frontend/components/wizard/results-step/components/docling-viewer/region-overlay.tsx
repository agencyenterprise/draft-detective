import { bboxToStyle } from '@/lib/docling/overlay';
import { cn } from '@/lib/utils';
import type { RegionOverlayProps } from './types';
import { formatChunkLabel } from './utils';

export function RegionOverlay({
  region,
  pageWidth,
  pageHeight,
  isSelected,
  currentChunkPosition,
  onSelect,
}: RegionOverlayProps) {
  const style = bboxToStyle(region.bbox, pageWidth, pageHeight, 'bottom-left');
  const hasMultipleChunks = region.chunkIndices.length > 1;
  const chunkLabel = formatChunkLabel(region, currentChunkPosition);

  return (
    <button
      type="button"
      className={cn(
        'border-2 transition-all hover:bg-blue-200/30',
        'focus:outline-none focus:ring-2 focus:ring-blue-500',
        isSelected
          ? 'bg-blue-300/40 border-blue-600 shadow-lg z-10'
          : 'bg-blue-100/20 border-blue-400/50 hover:border-blue-500',
        hasMultipleChunks && 'border-dashed',
      )}
      style={style}
      onClick={onSelect}
      title={`${chunkLabel} - ${region.kind}${hasMultipleChunks ? ' (click to cycle)' : ''}`}
      aria-label={`Select ${chunkLabel}`}
    />
  );
}
