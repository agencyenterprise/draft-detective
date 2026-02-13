import { Button } from '@/components/ui/button';
import { Issue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { EyeIcon, EyeOffIcon } from 'lucide-react';
import { SeverityFilter } from './severity-filter';
import { WorkflowTypeFilter } from './workflow-type-filter';

interface DocumentExplorerSidebarFilterProps {
  issues: Issue[];
  severityFilter: SeverityEnum[];
  onSeverityFilterChange: (value: SeverityEnum[]) => void;
  workflowTypeFilter: WorkflowRunType[];
  onWorkflowTypeFilterChange: (value: WorkflowRunType[]) => void;
  resolvedCount: number;
  showResolved: boolean;
  onShowResolvedChange: (value: boolean) => void;
}

export function DocumentExplorerSidebarFilter({
  issues,
  severityFilter,
  onSeverityFilterChange,
  workflowTypeFilter,
  onWorkflowTypeFilterChange,
  resolvedCount,
  showResolved,
  onShowResolvedChange,
}: DocumentExplorerSidebarFilterProps) {
  return (
    <>
      {resolvedCount > 0 && (
        <Button
          variant={showResolved ? 'secondary' : 'outline'}
          size="sm"
          className="text-xs h-6 px-2 gap-1 shadow-xs"
          onClick={() => onShowResolvedChange(!showResolved)}
          title={showResolved ? 'Hide resolved issues' : 'Show resolved issues'}
        >
          {showResolved ? <EyeIcon className="size-3" /> : <EyeOffIcon className="size-3" />}
          {resolvedCount} resolved
        </Button>
      )}
      <SeverityFilter value={severityFilter} onChange={onSeverityFilterChange} />
      <WorkflowTypeFilter issues={issues} value={workflowTypeFilter} onChange={onWorkflowTypeFilterChange} />
    </>
  );
}
