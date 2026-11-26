import { documentUrlTransform } from '@/components/shared/document-image';

/** Example documents carry their figures inline, as the backend builds them from the eval datasets. */
const INLINE_IMAGE = /^data:image\/(png|jpeg|gif|webp);base64,/;

export function isInlineImage(url: string): boolean {
  return INLINE_IMAGE.test(url);
}

/** Keeps inline figures, which the document explorer's transform would strip, and treats every other URL as it does. */
export function passageUrlTransform(url: string): string {
  return isInlineImage(url) ? url : documentUrlTransform(url);
}

/**
 * Whether a rendered block holds the passage's source line, read from the
 * block's `data-line-start` / `data-line-end`. A block without an end spans
 * just its first line.
 */
export function blockCoversLine(lines: { lineStart?: string; lineEnd?: string }, line: number): boolean {
  const start = Number(lines.lineStart);
  const end = Number(lines.lineEnd ?? start);
  return start <= line && line <= end;
}
