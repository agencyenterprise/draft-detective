'use client';

import { useState } from 'react';
import { FlaskConical } from 'lucide-react';
import { WorkflowCategoryOrder, WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { Checkbox } from '../ui/checkbox';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { useExperimentalFeatures } from '@/context/experimental-features-context';

interface WorkflowTypeSelectorProps {
  workflowTypes?: WorkflowTypeDescription[];
  categories: WorkflowCategoryOrder[];
  selectedTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabled?: boolean;
  disabledTypes?: WorkflowRunType[];
  showHeader?: boolean;
  headerDescription?: string;
  error?: string;
  defaultShowExperimental?: boolean;
}

export function WorkflowTypeSelector({
  workflowTypes,
  categories,
  selectedTypes,
  onSelectionChange,
  disabled = false,
  disabledTypes = [],
  showHeader = true,
  headerDescription,
  error,
  defaultShowExperimental = false,
}: WorkflowTypeSelectorProps) {
  const [showExperimental, setShowExperimental] = useState(defaultShowExperimental);
  const { showExperimentalFeatures } = useExperimentalFeatures();

  const hasExperimentalWorkflows =
    showExperimentalFeatures && (workflowTypes?.some((wt) => wt.is_experimental) ?? false);

  const visibleCount = workflowTypes?.filter(
    (wt) => !wt.is_experimental || (showExperimentalFeatures && showExperimental),
  ).length;

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
      disabled={disabled || disabledTypes.includes(workflowType.type)}
    />
  );

  const typeMap = new Map(workflowTypes?.map((wt) => [wt.type, wt]) ?? []);

  return (
    <div className="space-y-4">
      {showHeader && (
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold">
              Analyses Type Selection{' '}
              {visibleCount != null && visibleCount > 0 && (
                <span className="text-sm font-normal text-muted-foreground">
                  ({selectedTypes.length}/{visibleCount} selected)
                </span>
              )}
              <span className="text-destructive ml-1">*</span>
            </h2>
            {headerDescription && <p className="text-sm text-muted-foreground">{headerDescription}</p>}
          </div>
          {hasExperimentalWorkflows && (
            <Tooltip>
              <TooltipTrigger asChild>
                <label className="flex items-center gap-2 cursor-pointer shrink-0 mt-0.5">
                  <Checkbox
                    checked={showExperimental}
                    tabIndex={-1}
                    onCheckedChange={(checked) => setShowExperimental(checked === true)}
                  />
                  <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    Show experimental
                    <FlaskConical className="size-3.5" />
                  </span>
                </label>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-xs">
                Experimental analyses are still being refined. Results may vary and features may change in future
                updates.
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      )}
      <div className="space-y-2">
        {categories.map((category) => {
          const categoryWorkflows = category.workflows
            .map((type) => typeMap.get(type as WorkflowRunType))
            .filter((wt): wt is WorkflowTypeDescription => wt !== undefined);

          const regular = categoryWorkflows.filter((wt) => !wt.is_experimental);
          const experimental =
            showExperimentalFeatures && showExperimental ? categoryWorkflows.filter((wt) => wt.is_experimental) : [];

          if (regular.length === 0 && experimental.length === 0) return null;

          return (
            <div key={category.slug} className="space-y-2">
              <h3 className="text-sm font-semibold text-foreground pt-2">{category.label}</h3>
              {regular.map(renderCheckbox)}
              {experimental.map(renderCheckbox)}
            </div>
          );
        })}

        {!workflowTypes && <p className="text-sm text-muted-foreground">Loading available workflows...</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
