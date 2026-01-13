import { WorkflowRunStatus } from '@/lib/generated-api';
import { formatDuration } from '@/lib/format-duration';
import { cn } from '@/lib/utils';
import { AlertTriangle, Check, Clock, Loader2 } from 'lucide-react';

interface StatusIndicatorProps {
  status: WorkflowRunStatus;
  className?: string;
  /** Duration in milliseconds to display in parentheses */
  durationMs?: number | null;
}

export function StatusIndicator({ status, className, durationMs }: StatusIndicatorProps) {
  const getStatusConfig = (status: WorkflowRunStatus) => {
    switch (status) {
      case 'pending':
        return {
          label: 'Pending',
          className: 'text-yellow-700',
          icon: <Clock className="h-3 w-3" />,
        };
      case 'running':
        return {
          label: 'Running',
          className: 'text-blue-700',
          icon: <Loader2 className="h-3 w-3 animate-spin" />,
        };
      case 'completed':
        return {
          label: 'Completed',
          className: 'text-green-700',
          icon: <Check className="h-3 w-3" />,
        };
      default:
        return {
          label: 'Unknown',
          className: 'text-red-700',
          icon: <AlertTriangle className="h-3 w-3" />,
        };
    }
  };

  const config = getStatusConfig(status);
  const durationText = durationMs != null && durationMs > 0 ? ` (${formatDuration(durationMs)})` : '';

  return (
    <span className={cn('inline-flex text-xs items-center gap-1', config.className, className)}>
      {config.label}
      {durationText}
      {config.icon}
    </span>
  );
}
