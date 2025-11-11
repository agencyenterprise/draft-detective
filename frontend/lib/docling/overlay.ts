import type { BBox } from '@/types/docling';

export type CoordinateOrigin = 'top-left' | 'bottom-left';

export type BBoxPercent = {
  left: string;
  top: string;
  width: string;
  height: string;
};

type BBoxWithLegacyFields = BBox & { x0?: number; y0?: number; x1?: number; y1?: number };

export function bboxToPercent(bbox: BBox, pageW: number, pageH: number): BBoxPercent {
  // Docling uses l,b,r,t (left, bottom, right, top)
  const legacyBbox = bbox as BBoxWithLegacyFields;
  const x0 = bbox.l ?? legacyBbox.x0 ?? 0;
  const y0 = bbox.b ?? legacyBbox.y0 ?? 0;
  const x1 = bbox.r ?? legacyBbox.x1 ?? 0;
  const y1 = bbox.t ?? legacyBbox.y1 ?? 0;

  return {
    left: `${(x0 / pageW) * 100}%`,
    top: `${(y0 / pageH) * 100}%`,
    width: `${((x1 - x0) / pageW) * 100}%`,
    height: `${((y1 - y0) / pageH) * 100}%`,
  };
}

export function normalizeOrigin(bbox: BBox, pageW: number, pageH: number, origin: CoordinateOrigin): BBox {
  const legacyBbox = bbox as BBoxWithLegacyFields;
  const x0 = bbox.l ?? legacyBbox.x0 ?? 0;
  const y0 = bbox.b ?? legacyBbox.y0 ?? 0;
  const x1 = bbox.r ?? legacyBbox.x1 ?? 0;
  const y1 = bbox.t ?? legacyBbox.y1 ?? 0;

  if (origin === 'bottom-left') {
    return {
      l: x0,
      r: x1,
      b: pageH - y1,
      t: pageH - y0,
    };
  }
  return bbox;
}

export function bboxToStyle(
  bbox: BBox,
  pageW: number,
  pageH: number,
  origin: CoordinateOrigin = 'bottom-left',
): React.CSSProperties {
  const normalized = normalizeOrigin(bbox, pageW, pageH, origin);
  const percent = bboxToPercent(normalized, pageW, pageH);

  return {
    position: 'absolute',
    left: percent.left,
    top: percent.top,
    width: percent.width,
    height: percent.height,
  };
}
