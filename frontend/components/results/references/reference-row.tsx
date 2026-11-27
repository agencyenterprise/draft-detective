'use client';

import { Markdown } from '@/components/shared/markdown';
import { ReferenceReviewItem } from '@/components/results/references/types';
import { cn } from '@/lib/utils';
import { FileText, FileX, Loader2 } from 'lucide-react';
import { STATUS } from './status';

interface ReferenceRowProps {
  reference: ReferenceReviewItem;
  active: boolean;
  onSelect: () => void;
}

/**
 * One row of the bibliography: the citation, and whether a source file stands
 * behind it. Nothing else — the file's provenance and the controls that change
 * it live in the detail pane, so scanning fifty references stays scanning.
 */
export function ReferenceRow({ reference, active, onSelect }: ReferenceRowProps) {
  const { index, text, status, matchedFile } = reference;

  return (
    // A div rather than a button: the citation renders as markdown, and block
    // elements are not allowed inside a button.
    <div
      id={`reference-${index}`}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      onClick={onSelect}
      onKeyDown={(event) => {
        // Only when the row itself has focus. The citation renders as markdown
        // and its DOI links are focusable, and swallowing their Enter would
        // select the row instead of following the link.
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className={cn(
        'relative flex cursor-pointer gap-3 px-4 py-3 text-left transition-colors',
        // A bar on the edge rather than a heavier tint: the row is what the
        // detail pane is describing, so it has to be findable at a glance.
        active
          ? 'bg-accent before:bg-primary before:absolute before:inset-y-0 before:left-0 before:w-0.5'
          : 'hover:bg-accent/40',
      )}
    >
      <span className="w-8 shrink-0 pt-0.5 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
        {index + 1}
      </span>

      <div className="min-w-0 flex-1">
        <div className="max-w-4xl text-[13.5px] leading-relaxed [&_p]:mb-0">
          <Markdown>{text}</Markdown>
        </div>

        <p className="mt-1.5 flex min-w-0 items-center gap-1.5 text-[11px]">
          {status === 'fetching' ? (
            <>
              <Loader2 className={cn('size-3 shrink-0 animate-spin', STATUS.fetching.text)} />
              <span className={STATUS.fetching.text}>{STATUS.fetching.label}</span>
            </>
          ) : matchedFile ? (
            <>
              <FileText className={cn('size-3 shrink-0', STATUS.matched.text)} />
              <span className={cn('shrink-0 font-medium', STATUS.matched.text)}>{STATUS.matched.label}:</span>
              <span className={cn('truncate', STATUS.matched.text)}>{matchedFile.name}</span>
            </>
          ) : (
            <>
              <FileX className={cn('size-3 shrink-0', STATUS.unmatched.text)} />
              <span className={cn('font-medium', STATUS.unmatched.text)}>{STATUS.unmatched.label}</span>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
