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
  className?: string;
}

/**
 * An example document rendered the way the document explorer renders a draft:
 * the same line gutter, text column and type. The passage being judged is
 * marked in the text, and its paragraph carries the wash and gutter rule a
 * selected finding gets in the explorer.
 */
export function PassageDocument({ document, anchor, className }: PassageDocumentProps) {
  const rehypePlugins: PluggableList = useMemo(
    () => [...REHYPE_PLUGINS, [rehypeHighlightAnchor, { anchor }]],
    [anchor],
  );

  // A ref callback rather than an effect: the content is fixed for the life of
  // the element (callers key it by item), so marking the row once on mount is
  // all there is to do. Scrolls the pane itself, not the page around it.
  const markAndScroll = useCallback((container: HTMLDivElement | null) => {
    const target = container?.querySelector<HTMLElement>(ANCHOR_SELECTOR);
    if (!container || !target) return;
    const row = target.closest<HTMLElement>('[data-block-row]');
    row?.querySelector('[data-block-owner]')?.classList.add(...ROW_WASH);
    const rule = row?.querySelector<HTMLElement>('[data-rule]');
    if (rule) rule.className = ROW_RULE;
    const anchorBox = (row ?? target).getBoundingClientRect();
    const paneBox = container.getBoundingClientRect();
    container.scrollTop += anchorBox.top - paneBox.top - container.clientHeight / 2 + anchorBox.height / 2;
  }, []);

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
