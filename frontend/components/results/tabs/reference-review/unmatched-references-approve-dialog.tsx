'use client';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { AlertTriangle } from 'lucide-react';

interface UnmatchedReferencesApproveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  unmatchedCount: number;
  onConfirmApprove: () => void;
}

export function UnmatchedReferencesApproveDialog({
  open,
  onOpenChange,
  unmatchedCount,
  onConfirmApprove,
}: UnmatchedReferencesApproveDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <AlertDialogTitle>Some references are missing source documents</AlertDialogTitle>
          </div>
          <AlertDialogDescription className="space-y-3">
            <p>
              <strong>
                {unmatchedCount} reference{unmatchedCount === 1 ? '' : 's'}
              </strong>{' '}
              {unmatchedCount === 1 ? "doesn't" : "don't"} have sources yet.
            </p>
            <p>
              Without source documents, we won&apos;t be able to fully verify claims that cite these references. You can
              still run the analysis, but results may be incomplete.
            </p>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row gap-2 sm:justify-end">
          <AlertDialogAction onClick={onConfirmApprove} className="bg-red-600 hover:bg-red-700 text-white">
            Continue anyway
          </AlertDialogAction>
          <AlertDialogCancel className="mt-0 bg-primary text-primary-foreground hover:bg-primary/90">
            Go back and add sources
          </AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
