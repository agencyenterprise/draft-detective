'use client';

import { Issue } from '@/lib/generated-api';
import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react';
import { useState } from 'react';
import { MarginNote } from './margin-note';

/** How many document-level notes stand above the document before folding. */
const COLLAPSED_COUNT = 3;

interface DocumentIssuesProps {
  issues: Issue[];
  activeIssueId: string | null;
  readOnly: boolean;
  onSelect: (issue: Issue) => void;
}

/**
 * The findings that are about the document rather than a place in it, gathered
 * at the top of the margin with no heading of their own: each card says what it
 * is about with a globe where a line label would be (see `IssueMeta`). They are
 * folded after a few: this block sits above
 * the first paragraph, so a long one pushes the document itself off the screen —
 * the opposite of what the margin is for.
 */
export function DocumentIssues({ issues, activeIssueId, readOnly, onSelect }: DocumentIssuesProps) {
  const [expanded, setExpanded] = useState(false);

  // Opening one from the issues list must not leave it folded away, so the
  // block unfolds around whatever is active rather than hiding it.
  const activeIsFolded = issues.findIndex((issue) => issue.id === activeIssueId) >= COLLAPSED_COUNT;
  const showAll = expanded || activeIsFolded;
  const shown = showAll ? issues : issues.slice(0, COLLAPSED_COUNT);
  const hidden = issues.length - shown.length;

  return (
    <>
      {shown.map((issue) => (
        <MarginNote
          key={issue.id}
          issue={issue}
          anchored={false}
          active={activeIssueId === issue.id}
          readOnly={readOnly}
          onSelect={onSelect}
        />
      ))}

      {/* Nothing to offer while the open issue is one of the folded ones:
          collapsing would hide what the reader is reading, so the control would
          be pressed and do nothing. */}
      {!activeIsFolded && (hidden > 0 || (showAll && issues.length > COLLAPSED_COUNT)) && (
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={showAll}
          className="mt-0.5 flex cursor-pointer items-center gap-1 px-2 text-[11px] font-medium text-muted-foreground hover:text-foreground"
        >
          {showAll ? <ChevronUpIcon className="size-3" /> : <ChevronDownIcon className="size-3" />}
          {showAll ? 'Show fewer' : `Show ${hidden} more`}
        </button>
      )}
    </>
  );
}
