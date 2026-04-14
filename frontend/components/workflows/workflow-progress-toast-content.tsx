'use client';

import { WorkflowProgressResponse } from '@/lib/generated-api';
import { Progress } from '@/components/ui/progress';
import { CheckCircle2, Circle, Loader2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

type ProgressStatus = 'pending' | 'in_progress' | 'completed';

export function getProgressStatus(item: WorkflowProgressResponse): ProgressStatus {
  if (item.completed_at) return 'completed';
  if (item.started_at) return 'in_progress';
  return 'pending';
}

const STATUS_STYLES = {
  pending: { icon: Circle, iconClass: 'text-gray-400', bgClass: 'bg-white border-gray-200' },
  in_progress: { icon: Loader2, iconClass: 'text-blue-600 animate-spin', bgClass: 'bg-blue-50 border-blue-200' },
  completed: { icon: CheckCircle2, iconClass: 'text-green-500', bgClass: 'bg-gray-50/80 border-gray-200/80' },
} as const;

export function ProgressItem({
  item,
  isNewlyCompleted,
}: {
  item: WorkflowProgressResponse;
  isNewlyCompleted?: boolean;
}) {
  const status = getProgressStatus(item);
  const { icon: Icon, iconClass, bgClass } = STATUS_STYLES[status];
  const totalSteps = item.total_steps ?? 0;
  const currentStep = item.current_step ?? 0;
  const showProgress = totalSteps > 1;
  const percentage = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0;
  const isCompleted = status === 'completed';

  return (
    <div
      className={cn(
        'flex items-center gap-3 p-2.5 rounded-lg border',
        'transition-all duration-500 ease-out',
        isNewlyCompleted && 'bg-green-50 border-green-300 shadow-sm',
        !isNewlyCompleted && bgClass,
        isCompleted && !isNewlyCompleted && 'opacity-50 scale-[0.98]',
      )}
    >
      <Icon className={cn('h-4 w-4 shrink-0 transition-colors duration-300', iconClass)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              'text-[13px] truncate transition-opacity duration-300',
              isCompleted && !isNewlyCompleted ? 'text-muted-foreground' : 'text-foreground',
            )}
          >
            {item.name}
          </span>
          {showProgress && (
            <span className="text-xs text-muted-foreground tabular-nums shrink-0">
              {currentStep} / {totalSteps}
            </span>
          )}
        </div>
        {showProgress && status === 'in_progress' && (
          <div className="mt-1 flex items-center gap-2">
            <Progress value={percentage} className="h-1.5 flex-1" />
            <span className="text-xs font-medium text-blue-600 tabular-nums min-w-[3ch]">{percentage}%</span>
          </div>
        )}
      </div>
      {isNewlyCompleted && (
        <span className="text-xs font-medium text-green-600 animate-in fade-in zoom-in-95 duration-200">✓</span>
      )}
    </div>
  );
}

function TransitionMessage() {
  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 bg-gray-50/80">
      <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
      <span className="text-[13px] text-muted-foreground">Going to next step...</span>
    </div>
  );
}

function ToastWrapper({ children, actions }: { children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="w-96 space-y-2.5 p-4 bg-background border rounded-lg shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold tracking-tight text-foreground">Assessment in Progress</span>
        {actions}
      </div>
      <div className="max-h-[80vh] overflow-y-auto space-y-1.5">{children}</div>
    </div>
  );
}

export interface ToastContentProps {
  progress: WorkflowProgressResponse[];
  newlyCompletedIds: Set<string>;
  showCompleted: boolean;
  showAll: boolean;
  onToggleCompleted: () => void;
  onShowAll: () => void;
}

export function ToastContent({
  progress,
  newlyCompletedIds,
  showCompleted,
  showAll,
  onToggleCompleted,
  onShowAll,
}: ToastContentProps) {
  const inProgress = progress.filter((p) => getProgressStatus(p) === 'in_progress');
  const completed = progress.filter((p) => getProgressStatus(p) === 'completed');
  const recentlyCompleted = completed.filter((p) => newlyCompletedIds.has(p.id));
  const history = completed.filter((p) => !newlyCompletedIds.has(p.id));

  const activeItems = [...inProgress, ...recentlyCompleted];
  const displayedHistory = showAll ? history : history.slice(-5);
  const hasHistory = history.length > 0;

  const historyToggle = hasHistory && (
    <Button
      variant="outline"
      size="sm"
      onClick={onToggleCompleted}
      className="h-5 text-[11px] px-2 border-muted-foreground/20 text-muted-foreground hover:text-foreground"
    >
      {showCompleted ? 'Hide' : 'Show'}
    </Button>
  );

  return (
    <ToastWrapper actions={historyToggle}>
      {activeItems.length > 0 ? (
        activeItems.map((item) => (
          <ProgressItem key={item.id} item={item} isNewlyCompleted={newlyCompletedIds.has(item.id)} />
        ))
      ) : (
        <TransitionMessage />
      )}

      {showCompleted && history.length > 0 && (
        <>
          {activeItems.length > 0 && <div className="border-t mt-2 pt-2" />}
          {displayedHistory.map((item) => (
            <ProgressItem key={item.id} item={item} />
          ))}
          {!showAll && history.length > 5 && (
            <Button variant="outline" size="sm" onClick={onShowAll} className="w-full h-7 text-xs mt-1">
              <ChevronDown className="h-3 w-3 mr-1" />
              Show all {history.length + activeItems.length} steps
            </Button>
          )}
        </>
      )}
    </ToastWrapper>
  );
}

export function LoadingToastContent() {
  return (
    <ToastWrapper>
      <div className="flex items-center gap-3 p-2.5 rounded-lg border border-blue-200 bg-blue-50">
        <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
        <span className="text-[13px] text-muted-foreground">Starting assessment...</span>
      </div>
    </ToastWrapper>
  );
}
