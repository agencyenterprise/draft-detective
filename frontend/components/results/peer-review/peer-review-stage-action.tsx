'use client';

import { Button } from '@/components/ui/button';
import { WorkflowRunSummary } from '@/lib/generated-api';
import { isWorkflowProcessing } from '@/lib/workflow-state';
import { Loader2, X } from 'lucide-react';

interface StageActionProps {
  label: string;
  /** Overrides the "Re-run" text when a result already exists. */
  reRunLabel?: string;
  run?: WorkflowRunSummary;
  disabled: boolean;
  isStarting: boolean;
  variant?: 'default' | 'outline';
  /** CTA buttons render at the default size; toolbar ones stay small. */
  size?: 'xs' | 'sm' | 'default';
  onStart: () => void;
  onCancel: (runId: string) => void;
}

/**
 * Start / cancel / re-run for one deliverable.
 *
 * Not `StartWorkflowButton`: that opens `WorkflowConfigDialog`, the dialog this
 * tab exists to remove, and none of these workflows needs web-search consent or
 * a publication date, so there is nothing to configure.
 */
export function PeerReviewStageAction({
  label,
  reRunLabel,
  run,
  disabled,
  isStarting,
  variant = 'default',
  size = 'sm',
  onStart,
  onCancel,
}: StageActionProps) {
  if (run && isWorkflowProcessing(run)) {
    return (
      <Button variant="outline" size={size} onClick={() => onCancel(run.run.id)}>
        <Loader2 className={size === 'xs' ? 'size-3 animate-spin' : 'size-4 animate-spin'} />
        Running
        <X className={size === 'xs' ? 'size-3' : 'size-4'} />
      </Button>
    );
  }

  const hasResult = !!run;
  return (
    <Button variant={hasResult ? 'outline' : variant} size={size} disabled={disabled || isStarting} onClick={onStart}>
      {isStarting && <Loader2 className={size === 'xs' ? 'size-3 animate-spin' : 'size-4 animate-spin'} />}
      {hasResult ? (reRunLabel ?? 'Re-run') : label}
    </Button>
  );
}
