'use client';

import { Issue, SeverityEnum } from '@/lib/generated-api';
import { SEVERITY } from '@/lib/severity-style';
import { isIssueResolved } from '@/lib/stores/document-explorer-store';
import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { IssueBody, IssueMeta, IssuePreview } from './issue-note';

/** The heading a run of same-severity rows sits under: marker, name, count. */
export function GroupHeader({ severity, count }: { severity: SeverityEnum; count: number }) {
  const style = SEVERITY[severity];
  return (
    <div className="bg-background flex items-center gap-2 border-b px-4 py-2">
      <span className={cn('block size-2 rounded-[2px]', style.dot)} />
      <span className="text-xs font-medium">{style.label}</span>
      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{count}</span>
    </div>
  );
}

interface IssueRowProps {
  issue: Issue;
  active: boolean;
  readOnly: boolean;
  /**
   * Toggles the row. Left out, the heading is plain text and the row stays as
   * `active` says — for a place that shows one issue and has nothing to
   * collapse it into, such as the admin's feedback sheet.
   */
  onSelect?: (issue: Issue) => void;
  /** Passed through to the open body; see {@link IssueBody}. */
  crossLink?: ReactNode;
}

/**
 * One issue as a flat row: two lines closed, expanding in place into the same
 * body the margin note shows. Shared by the explorer's issue queue and an
 * assessment's own results, so an issue reads the same wherever it is met.
 */
export function IssueRow({ issue, active, readOnly, onSelect, crossLink }: IssueRowProps) {
  const resolved = isIssueResolved(issue);
  const style = SEVERITY[issue.severity];

  const heading = (
    <>
      <IssueMeta issue={issue} />
      <span className="mt-1 flex items-start gap-2">
        <span className="flex-1 text-[13.5px] leading-snug font-medium">{issue.title}</span>
        {active && <span className={cn('shrink-0 font-mono text-[10px] uppercase', style.text)}>{style.label}</span>}
      </span>
      {!active && <IssuePreview issue={issue} />}
    </>
  );

  return (
    <div className={cn('border-b transition-colors', active && style.wash, resolved && !active && 'opacity-60')}>
      {/* Only the heading toggles the row, as in the margin. The whole row used
          to be the control, so clicking the description collapsed it — which
          also took away any attempt to select the text or follow a link in it —
          and the buttons an open row carries sat inside another button. */}
      {onSelect ? (
        <button
          onClick={() => onSelect(issue)}
          aria-expanded={active}
          className={cn(
            'block w-full cursor-pointer px-4 pt-3 text-left transition-colors',
            active ? 'pb-2' : 'hover:bg-accent/50 pb-3',
          )}
        >
          {heading}
        </button>
      ) : (
        <div className={cn('px-4 pt-3', active ? 'pb-2' : 'pb-3')}>{heading}</div>
      )}
      {active && (
        <div className="px-4 pb-3">
          <IssueBody issue={issue} readOnly={readOnly} crossLink={crossLink} />
        </div>
      )}
    </div>
  );
}
