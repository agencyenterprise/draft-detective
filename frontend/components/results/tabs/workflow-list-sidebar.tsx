'use client';

import { Button } from '@/components/ui/button';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import { getDisplayStatus, hasCurrentRunErrors } from '@/lib/workflow-state';
import { formatDistanceToNow } from 'date-fns';
import { AlertTriangleIcon, InfoIcon, PlusIcon } from 'lucide-react';

interface WorkflowListItemProps {
  workflowDetail: WorkflowRunDetail;
  isSelected: boolean;
  onSelect: () => void;
}

function WorkflowListItem({ workflowDetail, isSelected, onSelect }: WorkflowListItemProps) {
  const displayStatus = getDisplayStatus(workflowDetail);
  const hasErrors = hasCurrentRunErrors(workflowDetail);
  const { getWorkflowTypeName } = useWorkflowTypes();

  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer shadow-xs',
        isSelected && 'bg-muted border-primary shadow',
      )}
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 font-medium text-sm">
          {getWorkflowTypeName(workflowDetail.run.type)}
          {hasErrors && (
            <Tooltip>
              <TooltipTrigger asChild>
                <AlertTriangleIcon className="w-4 h-4 text-destructive cursor-help" />
              </TooltipTrigger>
              <TooltipContent>This workflow completed with errors. Please check them and try again.</TooltipContent>
            </Tooltip>
          )}
        </div>
        <div className="flex items-center gap-2 justify-between">
          <div className="text-xs text-muted-foreground">
            {formatDistanceToNow(workflowDetail.run.last_updated_at, { addSuffix: true })}
          </div>
          <StatusIndicator status={displayStatus} />
        </div>
      </div>
    </button>
  );
}

interface WorkflowListSidebarProps {
  workflowDetails: WorkflowRunDetail[];
  selectedWorkflowType: WorkflowRunType | null;
  onSelectWorkflowType: (type: WorkflowRunType) => void;
  onStartNewAnalysis: () => void;
  readOnly?: boolean;
}

export function WorkflowListSidebar({
  workflowDetails,
  selectedWorkflowType,
  onSelectWorkflowType,
  onStartNewAnalysis,
  readOnly,
}: WorkflowListSidebarProps) {
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  const visibleWorkflows = workflowDetails.filter((wd) => isWorkflowTypeVisible(wd.run.type));
  const internalWorkflows = workflowDetails.filter((wd) => !isWorkflowTypeVisible(wd.run.type));

  return (
    <div className="w-1/4 overflow-y-auto border-r pr-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Analyses</h3>
          {!readOnly && (
            <Button size="xs" variant="outline" onClick={onStartNewAnalysis}>
              <PlusIcon className="size-3" />
              New Analysis
            </Button>
          )}
        </div>
        {visibleWorkflows.map((workflowDetail) => (
          <WorkflowListItem
            key={workflowDetail.run.id}
            workflowDetail={workflowDetail}
            isSelected={selectedWorkflowType === workflowDetail.run.type}
            onSelect={() => onSelectWorkflowType(workflowDetail.run.type)}
          />
        ))}
        {internalWorkflows.length > 0 && (
          <div className="pt-4">
            <div className="flex items-center gap-1 mb-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Internal Analyses</h4>
              <Tooltip>
                <TooltipTrigger asChild>
                  <InfoIcon className="w-3 h-3 text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent>
                  These analyses run automatically as part of the analysis pipeline and are not user-triggered.
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="space-y-2">
              {internalWorkflows.map((workflowDetail) => (
                <div key={workflowDetail.run.id} className="opacity-70">
                  <WorkflowListItem
                    workflowDetail={workflowDetail}
                    isSelected={selectedWorkflowType === workflowDetail.run.type}
                    onSelect={() => onSelectWorkflowType(workflowDetail.run.type)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
