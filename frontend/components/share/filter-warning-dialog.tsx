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
import { SeverityBadge } from '@/components/wizard/results-step/components/severity-badge';
import { SeverityEnum } from '@/lib/generated-api';
import { Filter } from 'lucide-react';

interface FilterWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  severityFilter: SeverityEnum[];
  onConfirm: () => void;
}

export function FilterWarningDialog({ open, onOpenChange, severityFilter, onConfirm }: FilterWarningDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
              <Filter className="h-5 w-5 text-blue-600" />
            </div>
            <AlertDialogTitle>Severity filter active</AlertDialogTitle>
          </div>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>Your export will only include issues with these severity levels:</p>
              <div className="flex gap-2">
                {severityFilter.map((severity) => (
                  <SeverityBadge key={severity} severity={severity} hideIcon />
                ))}
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row gap-2 sm:justify-end">
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Download</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
