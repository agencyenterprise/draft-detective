'use client';

import { Issue } from '@/lib/generated-api';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Ref, useImperativeHandle } from 'react';
import { DocumentIssueCard } from './document-issue-card';

export interface DocumentIssuesListHandle {
  scrollToIssue: (issue: Issue) => void;
}

interface DocumentIssuesListProps {
  ref?: Ref<DocumentIssuesListHandle>;
  issues: Issue[];
  scrollElement: HTMLElement | null;
  hideJumpButton?: boolean;
  onSelect: (issue: Issue) => void;
  readOnly?: boolean;
}

export function DocumentIssuesList({
  ref,
  issues,
  scrollElement,
  hideJumpButton = false,
  onSelect,
  readOnly,
}: DocumentIssuesListProps) {
  const virtualizer = useVirtualizer({
    count: issues.length,
    getScrollElement: () => scrollElement,
    estimateSize: () => 140,
    overscan: 6,
    gap: 8,
    getItemKey: (index) => issues[index].id,
  });

  // Disable scroll anchoring on item resize so expanding a card in-place
  // (e.g. "Show details") doesn't cause the scroll position to flicker.
  virtualizer.shouldAdjustScrollPositionOnItemSizeChange = () => false;

  useImperativeHandle(
    ref,
    () => ({
      scrollToIssue: (issue: Issue) => {
        const index = issues.findIndex((i) => i.id === issue.id);
        if (index >= 0) {
          virtualizer.scrollToIndex(index, { align: 'start' });
        }
      },
    }),
    [issues, virtualizer],
  );

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div style={{ height: virtualizer.getTotalSize(), position: 'relative', width: '100%' }}>
      {virtualItems.map((virtualItem) => {
        const issue = issues[virtualItem.index];
        return (
          <div
            key={virtualItem.key}
            data-index={virtualItem.index}
            ref={virtualizer.measureElement}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <DocumentIssueCard issue={issue} hideJumpButton={hideJumpButton} onSelect={onSelect} readOnly={readOnly} />
          </div>
        );
      })}
    </div>
  );
}
