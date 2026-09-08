'use client';

import { Issue, SeverityEnum } from '@/lib/generated-api';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ReactNode, Ref, useImperativeHandle, useMemo } from 'react';
import { GroupHeader, IssueRow } from './issue-row';

/** Worst first, matching the order the store already sorts issues into. */
const SEVERITY_ORDER: SeverityEnum[] = [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low, SeverityEnum.None];

type Row = { kind: 'header'; severity: SeverityEnum; count: number } | { kind: 'issue'; issue: Issue };

export interface IssuesListHandle {
  scrollToIssue: (issue: Issue) => void;
}

interface IssuesListProps {
  ref?: Ref<IssuesListHandle>;
  issues: Issue[];
  scrollElement: HTMLElement | null;
  activeIssueId: string | null;
  readOnly: boolean;
  onSelect: (issue: Issue) => void;
  /** The open row's way out of the issue; see {@link IssueBody}. Defaults to its assessment's report. */
  crossLink?: (issue: Issue) => ReactNode;
}

/**
 * The issue queue: grouped by severity, one flat row per issue, expanding in
 * place into the same body the margin note shows. Virtualised, because turning
 * passing checks on can push this past six hundred rows.
 */
export function IssuesList({
  ref,
  issues,
  scrollElement,
  activeIssueId,
  readOnly,
  onSelect,
  crossLink,
}: IssuesListProps) {
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const severity of SEVERITY_ORDER) {
      const group = issues.filter((issue) => issue.severity === severity);
      if (group.length === 0) continue;
      out.push({ kind: 'header', severity, count: group.length });
      for (const issue of group) out.push({ kind: 'issue', issue });
    }
    return out;
  }, [issues]);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollElement,
    estimateSize: (index) => (rows[index].kind === 'header' ? 33 : 56),
    overscan: 8,
    getItemKey: (index) => {
      const row = rows[index];
      return row.kind === 'header' ? `header-${row.severity}` : row.issue.id;
    },
  });

  // Expanding a row in place should not yank the scroll position around it.
  virtualizer.shouldAdjustScrollPositionOnItemSizeChange = () => false;

  useImperativeHandle(
    ref,
    () => ({
      scrollToIssue: (issue: Issue) => {
        const index = rows.findIndex((row) => row.kind === 'issue' && row.issue.id === issue.id);
        if (index >= 0) virtualizer.scrollToIndex(index, { align: 'start' });
      },
    }),
    [rows, virtualizer],
  );

  return (
    <div style={{ height: virtualizer.getTotalSize(), position: 'relative', width: '100%' }}>
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const row = rows[virtualItem.index];
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
            {row.kind === 'header' ? (
              <GroupHeader severity={row.severity} count={row.count} />
            ) : (
              <IssueRow
                issue={row.issue}
                active={activeIssueId === row.issue.id}
                readOnly={readOnly}
                onSelect={onSelect}
                crossLink={crossLink?.(row.issue)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
