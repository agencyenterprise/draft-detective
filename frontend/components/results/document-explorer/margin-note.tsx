'use client';

import { useSeverityStyle } from '@/context/group-by-severity-context';
import { Issue } from '@/lib/generated-api';
import { isIssueResolved } from '@/lib/stores/document-explorer-store';
import { cn } from '@/lib/utils';
import { IssueBody, IssueMeta, IssuePreview } from './issue-note';

interface MarginNoteProps {
  issue: Issue;
  active: boolean;
  /** Whether the pointer is on this issue's passage in the document. */
  hovered?: boolean;
  readOnly: boolean;
  onSelect: (issue: Issue) => void;
  /**
   * Whether this note belongs to a paragraph. Document-level issues sit at the
   * top of the margin with nothing beside them, so they drop the leader rather
   * than point at a paragraph that is not theirs.
   */
  anchored?: boolean;
}

/**
 * One issue in the document's margin, on the same grid row as the paragraph it
 * belongs to. Collapsed it is two lines, so a document with a hundred issues
 * stays readable; open it carries everything the issue list does.
 *
 * The open note expands in place rather than floating over its neighbours. A
 * paragraph can carry several issues, and a floating card hid the ones beneath
 * it. Growing the row instead pushes the notes below it down and leaves the
 * anchored paragraph where it is, since the text cell sits at the row's top.
 */
export function MarginNote({ issue, active, hovered = false, readOnly, onSelect, anchored = true }: MarginNoteProps) {
  const resolved = isIssueResolved(issue);
  const style = useSeverityStyle()(issue.severity);

  if (active) {
    return (
      <div className="relative mb-1.5">
        {anchored && <Leader dot={style.dot} />}
        <div className={cn('rounded-md border', style.edge, style.wash)}>
          <button
            onClick={() => onSelect(issue)}
            className="w-full cursor-pointer px-2.5 pt-2 text-left"
            aria-label="Collapse issue"
          >
            <IssueMeta issue={issue} />
            <span className="mt-0.5 flex items-start gap-2">
              <span className="flex-1 text-[13px] leading-snug font-medium">{issue.title}</span>
              {style.label && (
                <span className={cn('shrink-0 font-mono text-[10px] uppercase', style.text)}>{style.label}</span>
              )}
            </span>
          </button>
          <div className="px-2.5 pt-1.5 pb-2">
            <IssueBody issue={issue} readOnly={readOnly} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative mb-1">
      <button
        onClick={() => onSelect(issue)}
        aria-expanded={false}
        className={cn(
          'hover:bg-accent/60 w-full cursor-pointer rounded-md px-2 py-1.5 text-left transition-colors',
          hovered && 'bg-accent/60',
          resolved && 'opacity-60',
        )}
      >
        <IssueMeta issue={issue} />
        <span className="mt-0.5 block text-[13px] leading-snug font-medium">{issue.title}</span>
        <IssuePreview issue={issue} />
      </button>
    </div>
  );
}

/** Hairline from the text column into the margin, tying a note to its paragraph. */
function Leader({ dot }: { dot: string }) {
  return <span aria-hidden className={cn('absolute top-3.5 -left-6 h-px w-6 opacity-60', dot)} />;
}
