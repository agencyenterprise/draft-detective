'use client';

import { useMemo } from 'react';
import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { useExperimentalFeatures } from '@/context/experimental-features-context';

interface WorkflowTypeSelectorProps {
  /** When set, only this workflow type is listed (e.g. config dialog for a specific analysis). */
  restrictToType?: WorkflowRunType;
  selectedTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabled?: boolean;
  disabledTypes?: WorkflowRunType[];
  showHeader?: boolean;
  headerDescription?: string;
  error?: string;
}

export function WorkflowTypeSelector({
  restrictToType,
  selectedTypes,
  onSelectionChange,
  disabled = false,
  disabledTypes = [],
  showHeader = true,
  headerDescription,
  error,
}: WorkflowTypeSelectorProps) {
  const { workflowTypes: allTypes, categories, isPending: isLoadingWorkflowTypes } = useWorkflowTypes();
  const { showExperimentalFeatures } = useExperimentalFeatures();

  const workflowTypes = useMemo(() => {
    if (restrictToType) {
      return allTypes.filter((wt) => wt.type === restrictToType);
    }
    return allTypes.filter((wt) => !wt.is_internal);
  }, [allTypes, restrictToType]);

  const experimentalVisible = showExperimentalFeatures;

  const visibleCount = workflowTypes.filter((wt) => !wt.is_experimental || experimentalVisible).length;

  const handleCheckedChange = (type: WorkflowRunType, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedTypes, type]);
    } else {
      onSelectionChange(selectedTypes.filter((t) => t !== type));
    }
  };

  const renderCheckbox = (workflowType: WorkflowTypeDescription) => (
    <WorkflowTypeCheckbox
      key={workflowType.type}
      workflowType={workflowType}
      checked={selectedTypes.includes(workflowType.type)}
      onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
      disabled={controlsDisabled || disabledTypes.includes(workflowType.type)}
    />
  );

  const typeMap = new Map(workflowTypes.map((wt) => [wt.type, wt]));
  const controlsDisabled = disabled || isLoadingWorkflowTypes;

  return (
    <div className="space-y-4">
      {showHeader && (
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">
            Assessment Type Selection{' '}
            {visibleCount > 0 && (
              <span className="text-sm font-normal text-muted-foreground">
                ({selectedTypes.length}/{visibleCount} selected)
              </span>
            )}
            <span className="text-destructive ml-1">*</span>
          </h2>
          {headerDescription && <p className="text-sm text-muted-foreground">{headerDescription}</p>}
        </div>
      )}
      <div className="space-y-2">
        {isLoadingWorkflowTypes ? (
          <p className="text-sm text-muted-foreground">Loading available workflows...</p>
        ) : restrictToType !== undefined ? (
          // Single-type mode: render from API types directly. Category config often omits internal workflows,
          // so walking categories would show nothing even when restrictToType is valid.
          workflowTypes.length > 0 ? (
            <div className="space-y-2">{workflowTypes.map(renderCheckbox)}</div>
          ) : (
            <p className="text-sm text-muted-foreground">This workflow type is not available for your account.</p>
          )
        ) : (
          categories.map((category) => {
            const categoryWorkflows = category.workflows
              .map((type) => typeMap.get(type as WorkflowRunType))
              .filter((wt): wt is WorkflowTypeDescription => wt !== undefined)
              .filter((wt) => experimentalVisible || !wt.is_experimental);

            if (categoryWorkflows.length === 0) return null;

            return (
              <div key={category.slug} className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground pt-2">{category.label}</h3>
                {categoryWorkflows.map(renderCheckbox)}
              </div>
            );
          })
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
