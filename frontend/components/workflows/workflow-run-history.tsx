'use client';

import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { History, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkflowRunStatus, WorkflowRunSummary } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { getDisplayStatus } from '@/lib/workflow-state';

interface WorkflowRunHistoryProps {
  currentRunId: string;
  onSelectRun: (run: WorkflowRunSummary) => void;
  /** Every run of the assessment, newest first; undefined while it loads. */
  historyData?: WorkflowRunSummary[];
  /** Match the button to the toolbar it sits in. */
  size?: 'sm' | 'xs';
  /** Shown on hover. */
  tooltip?: React.ReactNode;
}

export function WorkflowRunHistory({
  currentRunId,
  onSelectRun,
  historyData,
  size = 'sm',
  tooltip,
}: WorkflowRunHistoryProps) {
  const [isOpen, setIsOpen] = useState(false);

  const isLoading = !historyData;

  const handleSelectRun = (run: WorkflowRunSummary) => {
    onSelectRun(run);
    setIsOpen(false);
  };

  // Don't show history button if there's only one run or less
  const runCount = historyData?.length ?? 0;

  const trigger = (
    <PopoverTrigger asChild>
      <Button variant="ghost" size={size} className="gap-1.5">
        <History className={size === 'xs' ? 'size-3' : 'h-4 w-4'} />
        History
        {runCount > 1 && <span className="text-muted-foreground">({runCount})</span>}
      </Button>
    </PopoverTrigger>
  );

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      {tooltip ? (
        <Tooltip>
          <TooltipTrigger asChild>{trigger}</TooltipTrigger>
          <TooltipContent className="max-w-xs">{tooltip}</TooltipContent>
        </Tooltip>
      ) : (
        trigger
      )}
      <PopoverContent align="end" className="w-80 p-0">
        <div className="p-3 border-b">
          <h4 className="font-medium text-sm">Run History</h4>
          <p className="text-xs text-muted-foreground mt-0.5">Select a previous run to view its results</p>
        </div>
        <div className="max-h-64 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : historyData && historyData.length > 0 ? (
            <div className="py-1">
              {historyData.map((detail, index) => (
                <RunHistoryItem
                  key={detail.run.id}
                  detail={detail}
                  isLatest={index === 0}
                  isSelected={detail.run.id === currentRunId}
                  onSelect={() => handleSelectRun(detail)}
                />
              ))}
            </div>
          ) : (
            <div className="py-6 text-center text-sm text-muted-foreground">No runs found</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

interface RunHistoryItemProps {
  detail: WorkflowRunSummary;
  isLatest: boolean;
  isSelected: boolean;
  onSelect: () => void;
}

function RunHistoryItem({ detail, isLatest, isSelected, onSelect }: RunHistoryItemProps) {
  const { run } = detail;
  const isProcessing = run.status === WorkflowRunStatus.Running || run.status === WorkflowRunStatus.Pending;
  const displayStatus = getDisplayStatus(detail);

  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full px-3 py-2 text-left hover:bg-muted/50 transition-colors flex items-center gap-3',
        isSelected && 'bg-muted',
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{formatDistanceToNow(run.created_at, { addSuffix: true })}</span>
          {isLatest && <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded">Latest</span>}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <StatusIndicator status={displayStatus} />
          {isProcessing && <span className="text-xs text-muted-foreground">In progress...</span>}
        </div>
      </div>
      {isSelected && <CheckCircle className="h-4 w-4 text-primary shrink-0" />}
    </button>
  );
}
