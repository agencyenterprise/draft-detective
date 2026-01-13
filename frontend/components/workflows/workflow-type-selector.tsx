'use client';

import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';

interface WorkflowTypeSelectorProps {
  isPending?: boolean;
  workflowTypes?: WorkflowTypeDescription[];
  selectedTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabled?: boolean;
  disabledTypes?: WorkflowRunType[];
  showHeader?: boolean;
  headerDescription?: string;
  error?: string;
}

export function WorkflowTypeSelector({
  isPending = false,
  workflowTypes,
  selectedTypes,
  onSelectionChange,
  disabled = false,
  disabledTypes = [],
  showHeader = true,
  headerDescription,
  error,
}: WorkflowTypeSelectorProps) {
  const handleCheckedChange = (type: WorkflowRunType, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedTypes, type]);
    } else {
      onSelectionChange(selectedTypes.filter((t) => t !== type));
    }
  };

  return (
    <div className="space-y-4">
      {showHeader && (
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">
            Analyses Type Selection <span className="text-destructive ml-1">*</span>
          </h2>
          {headerDescription && <p className="text-sm text-muted-foreground">{headerDescription}</p>}
        </div>
      )}
      <div className="space-y-2">
        {workflowTypes?.map((workflowType) => (
          <WorkflowTypeCheckbox
            key={workflowType.type}
            workflowType={workflowType}
            checked={selectedTypes.includes(workflowType.type)}
            onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
            disabled={disabled || disabledTypes.includes(workflowType.type)}
          />
        ))}
        {isPending && <p className="text-sm text-muted-foreground">Loading available analyses...</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
