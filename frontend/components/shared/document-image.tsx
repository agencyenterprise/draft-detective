'use client';

import { ImageOff } from 'lucide-react';
import React from 'react';
import { defaultUrlTransform } from 'react-markdown';
import { useShare } from '@/context/share-context';

/**
 * Converted document markdown references extracted images by a
 * storage-agnostic `draftdetective://{file-id}` src (see the backend's
 * image_extraction service). Each consumer resolves the scheme to its own
 * retrieval mechanism; here that is the file-download endpoint, proxied by
 * the Next route of the same shape.
 */
const IMAGE_REFERENCE_SCHEME = 'draftdetective://';
const EXTRACTED_IMAGE_PATH = '/api/files/download/';

/**
 * `urlTransform` for the document viewers' ReactMarkdown: resolves image
 * references to the download endpoint. Everything else gets react-markdown's
 * default sanitization, which would otherwise strip the unknown protocol
 * before `DocumentImage` could see it.
 */
export function documentUrlTransform(url: string): string {
  if (url.startsWith(IMAGE_REFERENCE_SCHEME)) {
    return `${EXTRACTED_IMAGE_PATH}${url.slice(IMAGE_REFERENCE_SCHEME.length)}`;
  }
  return defaultUrlTransform(url);
}

/**
 * Image renderer for converted document markdown, shared by the document explorer and the
 * document viewers.
 *
 * Documents converted before image extraction existed carry truncated
 * `data:image/png;base64...` stubs, which the url sanitization reduces to an
 * empty src; rendering those as <img> makes the browser refetch the page, so
 * they get an alt-text placeholder instead. In shared views the share token
 * is appended because an <img> request cannot carry the session's
 * Authorization header.
 */
export function DocumentImage({ src, alt, title }: React.ImgHTMLAttributes<HTMLImageElement>) {
  const { shareToken } = useShare();

  if (typeof src !== 'string' || src.length === 0 || src.startsWith('data:')) {
    return (
      <span className="my-1 inline-flex items-center gap-1.5 rounded border border-dashed px-2 py-1 text-xs text-muted-foreground">
        <ImageOff className="size-3" />
        {alt || 'Image not extracted'}
      </span>
    );
  }

  // Extracted images carry the document's intended display size in the
  // reference's query parameters (`?w=&h=`) so the src stays a plain markdown
  // image — see the backend's image_reference. The size parsing/stripping and
  // the share token apply only to that path: user-authored markdown can
  // reference arbitrary images whose query strings must not be touched.
  let resolvedSrc = src;
  let width: string | undefined;
  let height: string | undefined;
  if (src.startsWith(EXTRACTED_IMAGE_PATH)) {
    const [path, query] = src.split('?');
    const params = new URLSearchParams(query);
    width = params.get('w') ?? undefined;
    height = params.get('h') ?? undefined;
    params.delete('w');
    params.delete('h');
    if (shareToken) {
      params.set('share_token', shareToken);
    }
    const remaining = params.toString();
    resolvedSrc = remaining ? `${path}?${remaining}` : path;
  }

  // The declared size wins over the image's intrinsic ratio (Word documents
  // can display images non-proportionally): an explicit aspect-ratio keeps
  // the declared shape even when `max-w-full` shrinks the image. Without a
  // declared size, cap the height so a print-resolution image doesn't dwarf
  // the viewer.
  const sizeClass = width || height ? 'h-auto' : 'max-h-[32rem]';
  const aspectRatio = width && height ? `${width} / ${height}` : undefined;

  // No loading="lazy": Chrome defers lazy images inside this overflow scroll
  // container far too aggressively (deep links land on blank blocks), and a
  // document carries few images anyway.
  return (
    // eslint-disable-next-line @next/next/no-img-element -- document content, not app chrome
    <img
      src={resolvedSrc}
      alt={alt ?? ''}
      width={width}
      height={height}
      title={title}
      style={aspectRatio ? { aspectRatio } : undefined}
      className={`my-2 max-w-full rounded ${sizeClass}`}
    />
  );
}
