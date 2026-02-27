import { Issue } from '@/lib/generated-api';
import { DocumentExplorerFilter } from '@/lib/stores/document-explorer-store';
import { SeverityFilter } from './severity-filter';
import { WorkflowTypeFilter } from './workflow-type-filter';

interface DocumentExplorerSidebarFilterProps {
  issues: Issue[];
  filter: DocumentExplorerFilter;
  onFilterChange: (partial: Partial<DocumentExplorerFilter>) => void;
  resolvedCount: number;
  passingCount: number;
}

export function DocumentExplorerSidebarFilter({
  issues,
  filter,
  onFilterChange,
  resolvedCount,
  passingCount,
}: DocumentExplorerSidebarFilterProps) {
  return (
    <>
      <SeverityFilter value={filter.severity} onChange={(severity) => onFilterChange({ severity })} />
      <WorkflowTypeFilter
        issues={issues}
        value={filter.workflowType}
        onChange={(workflowType) => onFilterChange({ workflowType })}
        showPassing={filter.showPassing}
        onShowPassingChange={(showPassing) => onFilterChange({ showPassing })}
        showResolved={filter.showResolved}
        onShowResolvedChange={(showResolved) => onFilterChange({ showResolved })}
        resolvedCount={resolvedCount}
        passingCount={passingCount}
      />
    </>
  );
}
