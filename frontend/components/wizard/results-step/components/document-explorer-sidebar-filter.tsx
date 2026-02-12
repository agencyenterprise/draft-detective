import { DocumentIssue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { SeverityFilter } from './severity-filter';
import { WorkflowTypeFilter } from './workflow-type-filter';

interface DocumentExplorerSidebarFilterProps {
  issues: DocumentIssue[];
  severityFilter: SeverityEnum[];
  onSeverityFilterChange: (value: SeverityEnum[]) => void;
  workflowTypeFilter: WorkflowRunType[];
  onWorkflowTypeFilterChange: (value: WorkflowRunType[]) => void;
}

export function DocumentExplorerSidebarFilter({
  issues,
  severityFilter,
  onSeverityFilterChange,
  workflowTypeFilter,
  onWorkflowTypeFilterChange,
}: DocumentExplorerSidebarFilterProps) {
  return (
    <>
      <SeverityFilter value={severityFilter} onChange={onSeverityFilterChange} />
      <WorkflowTypeFilter issues={issues} value={workflowTypeFilter} onChange={onWorkflowTypeFilterChange} />
    </>
  );
}
