'use client';

import { StatusIndicator } from '@/components/ui/status-indicator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkflowRun, WorkflowRunStatus } from '@/lib/generated-api';
import { useWorkflowDuration } from '@/lib/hooks/use-workflow-duration';
import { format } from 'date-fns';

interface WorkflowStatusWithDurationProps {
  run: WorkflowRun;
  className?: string;
}

function formatTimestamp(date: Date | null | undefined): string {
  if (!date) return '—';
  return format(date, 'MMM d, yyyy h:mm:ss a');
}

/**
 * StatusIndicator with live-updating duration for workflow runs.
 * Shows duration inline like "Completed (3m) ✔" or "Running (2m 23s) ↺"
 * Includes tooltip showing start and end timestamps.
 */
export function WorkflowStatusWithDuration({ run, className }: WorkflowStatusWithDurationProps) {
  const durationMs = useWorkflowDuration(run);

  if (!run.started_at && !run.completed_at) {
    return <StatusIndicator status={run.status} durationMs={durationMs} className={className} />;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          <StatusIndicator status={run.status} durationMs={durationMs} className={className} />
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <div className="flex flex-col gap-1">
          <div>
            <span className="font-medium">Started:</span> {formatTimestamp(run.started_at)}
          </div>
          {run.status === WorkflowRunStatus.Completed && (
            <div>
              <span className="font-medium">Finished:</span> {formatTimestamp(run.completed_at)}
            </div>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
