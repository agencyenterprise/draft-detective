'use client';

import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

interface ProcessingErrorsBannerProps {
  onViewAssessments: () => void;
  /** Why the document itself could not be processed, when that is the cause. */
  documentFailure?: string | null;
}

/**
 * The strip that appears when an assessment on this revision hit an error it
 * could not recover from. It matches the reference-review and old-revision
 * strips so the chrome reads as one set of notices, and it points at the
 * Assessments tab because that is where the failing run and its message live.
 * Document processing is not listed there, so its failure is told here.
 */
export function ProcessingErrorsBanner({ onViewAssessments, documentFailure }: ProcessingErrorsBannerProps) {
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b bg-amber-50 px-3 py-2 dark:bg-amber-950/30">
      <div className="flex min-w-0 grow basis-96 items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" />
        {documentFailure ? (
          <p className="min-w-0 text-sm">
            <strong className="font-medium">The document could not be processed.</strong>{' '}
            <span className="break-words text-muted-foreground">{documentFailure}</span>
          </p>
        ) : (
          <p className="min-w-0 text-sm">
            <strong className="font-medium">Unexpected processing errors occurred.</strong>{' '}
            <span className="text-muted-foreground">
              One or more assessments stopped before finishing, so their results may be incomplete.
            </span>
          </p>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <Button size="xs" variant="outline" className="h-6" onClick={onViewAssessments}>
          View assessments
        </Button>
      </div>
    </div>
  );
}
