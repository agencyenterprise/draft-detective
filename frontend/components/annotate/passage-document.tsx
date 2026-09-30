'use client';

import { documentUrlTransform } from '@/components/document-image';
import {
  BLOCK_COMPONENTS,
  REHYPE_PLUGINS,
  REMARK_PLUGINS,
  WIDTH_BASE,
} from '@/components/results/document-explorer/document-view';
import { ANCHOR_SELECTOR, rehypeHighlightAnchor } from '@/lib/annotation-highlight';
import { cn } from '@/lib/utils';
import { useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import type { PluggableList } from 'unified';

const ROW_WASH = ['bg-amber-50', 'dark:bg-amber-950/30'];
const ROW_RULE = 'w-[2px] shrink-0 rounded-full bg-amber-500';

interface PassageDocumentProps {
  document: string;
  anchor: string;
  /** The passage's source line, used when the anchor cannot be found in the rendered text. */
  line?: number | null;
  className?: string;
}

/**
 * An example document rendered the way the document explorer renders a draft:
 * the same line gutter, text column and type. The passage being judged is
 * marked in the text, and its paragraph carries the wash and gutter rule a
 * selected finding gets in the explorer.
 */
/** The row holding the passage: where the highlight landed, else the row for its source line. */
function passageRow(container: HTMLElement, line?: number | null): HTMLElement | null {
  const marked = container.querySelector<HTMLElement>(ANCHOR_SELECTOR);
  if (marked) return marked.closest<HTMLElement>('[data-block-row]') ?? marked;
  if (!line) return null;
  for (const block of container.querySelectorAll<HTMLElement>('[data-block-owner][data-line-start]')) {
    const start = Number(block.dataset.lineStart);
    const end = Number(block.dataset.lineEnd ?? start);
    if (start <= line && line <= end) return block.closest<HTMLElement>('[data-block-row]');
  }
  return null;
}

export function PassageDocument({ document, anchor, line, className }: PassageDocumentProps) {
  const rehypePlugins: PluggableList = useMemo(
    () => [...REHYPE_PLUGINS, [rehypeHighlightAnchor, { anchor }]],
    [anchor],
  );

  // A ref callback rather than an effect: the content is fixed for the life of
  // the element (callers key it by item), so marking the row once on mount is
  // all there is to do. Scrolls the pane itself, not the page around it.
  const markAndScroll = useCallback(
    (container: HTMLDivElement | null) => {
      const row = container && passageRow(container, line);
      if (!container || !row) return;
      row.querySelector('[data-block-owner]')?.classList.add(...ROW_WASH);
      const rule = row.querySelector<HTMLElement>('[data-rule]');
      if (rule) rule.className = ROW_RULE;
      const rowBox = row.getBoundingClientRect();
      const paneBox = container.getBoundingClientRect();
      container.scrollTop += rowBox.top - paneBox.top - container.clientHeight / 2 + rowBox.height / 2;
    },
    [line],
  );

  return (
    <div
      ref={markAndScroll}
      className={cn('relative overflow-x-hidden overflow-y-auto px-5 py-5 text-sm break-words', className)}
    >
      <div className={cn('relative mx-auto', WIDTH_BASE)}>
        <ReactMarkdown
          remarkPlugins={REMARK_PLUGINS}
          rehypePlugins={rehypePlugins}
          components={BLOCK_COMPONENTS}
          urlTransform={documentUrlTransform}
        >
          {document}
        </ReactMarkdown>
      </div>
    </div>
  );
}
