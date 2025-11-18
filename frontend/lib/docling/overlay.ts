import type { BBox } from '@/lib/generated-api';

/**
 * Convert Docling bbox to CSS positioning styles
 *
 * Docling uses bottom-left origin (PDF standard: b=bottom, t=top)
 * CSS uses top-left origin, so we flip the Y-axis
 */
export function bboxToStyle(bbox: BBox, pageWidth: number, pageHeight: number): React.CSSProperties {
  const width = bbox.r - bbox.l;
  const height = bbox.t - bbox.b;

  return {
    position: 'absolute',
    left: `${(bbox.l / pageWidth) * 100}%`,
    top: `${((pageHeight - bbox.t) / pageHeight) * 100}%`, // Flip Y-axis for CSS
    width: `${(width / pageWidth) * 100}%`,
    height: `${(height / pageHeight) * 100}%`,
  };
}
