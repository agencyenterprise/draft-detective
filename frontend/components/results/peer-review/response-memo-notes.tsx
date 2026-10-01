'use client';

import { PeerReviewFacts } from '@/components/results/peer-review/peer-review-derive';
import { Button } from '@/components/ui/button';
import { AlertTriangle, FileCheck2, Upload } from 'lucide-react';

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? '' : 's'}`;

/**
 * Above the generated drafts in step 3. The drafts are a starting point that
 * authors edit outside the app, so this is where the final versions come back
 * in — and where it is said that the coverage report reads those, not these.
 */
export function ResponsesCallout({
  facts,
  readOnly,
  onUpload,
}: {
  facts: PeerReviewFacts;
  readOnly: boolean;
  onUpload: () => void;
}) {
  const count = facts.activeResponseMemos.length;

  if (count > 0) {
    return (
      <div className="flex items-start gap-2.5 rounded-md border bg-muted/40 px-3 py-2.5 text-[12.5px] leading-relaxed">
        <FileCheck2 className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
        <p className="text-muted-foreground">
          {plural(count, 'final author response memo')} {count === 1 ? 'is' : 'are'} uploaded. The QA coverage report
          reads {count === 1 ? 'it' : 'those'}, not the drafts below.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border bg-muted/40 px-3 py-2.5 text-[12.5px] leading-relaxed">
      <p className="min-w-0 flex-1 text-muted-foreground">
        These are drafts. Once they have been edited and sent, upload the final versions so the QA coverage report can
        check what the author told each reviewer against the revised draft.
      </p>
      {!readOnly && facts.canUploadResponses && (
        <Button size="xs" variant="outline" onClick={onUpload}>
          <Upload className="size-3" />
          Upload final memos
        </Button>
      )}
    </div>
  );
}

/** Above the coverage report: which inputs it reads, and whether it is behind them. */
export function CoverageInputsNote({ facts, hasReport }: { facts: PeerReviewFacts; hasReport: boolean }) {
  const count = facts.activeResponseMemos.length;

  if (hasReport && facts.responsesNewerThanCoverage) {
    return (
      <p className="flex items-start gap-2 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
        <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
        Response memos were added after this report was generated, so it has not read them. Generate it again to include
        them.
      </p>
    );
  }

  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      {count > 0
        ? `Checks ${plural(count, 'author response memo')} against revision ${facts.currentRevision}.`
        : "No author response memos uploaded, so every verdict comes from comparing the two drafts. Upload the author's final replies in step 3 to have them checked too."}
    </p>
  );
}
