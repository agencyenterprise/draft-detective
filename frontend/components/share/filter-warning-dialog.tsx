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
import { Badge } from '@/components/ui/badge';
import { SeverityBadge } from '@/components/results/components/severity-badge';
import { SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { Filter } from 'lucide-react';

interface FilterWarningDialogProps {
  open: boolean;
  severityFilter: SeverityEnum[];
  workflowTypeFilter: WorkflowRunType[];
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}

export function FilterWarningDialog({
  open,
  onOpenChange,
  severityFilter,
  workflowTypeFilter,
  onConfirm,
}: FilterWarningDialogProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const hasSeverityFilter = severityFilter.length > 0 && severityFilter.length < 3;
  const hasWorkflowTypeFilter = workflowTypeFilter.length > 0;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
              <Filter className="h-5 w-5 text-blue-600" />
            </div>
            <AlertDialogTitle>Filters active</AlertDialogTitle>
          </div>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>Your export will only include issues matching your active filters:</p>
              {hasSeverityFilter && (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Severity levels:</p>
                  <div className="flex flex-wrap gap-2">
                    {severityFilter.map((severity) => (
                      <SeverityBadge key={severity} severity={severity} hideIcon />
                    ))}
                  </div>
                </div>
              )}
              {hasWorkflowTypeFilter && (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Analysis types:</p>
                  <div className="flex flex-wrap gap-2">
                    {workflowTypeFilter.map((type) => (
                      <Badge key={type} variant="secondary">
                        {getWorkflowTypeName(type)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
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
