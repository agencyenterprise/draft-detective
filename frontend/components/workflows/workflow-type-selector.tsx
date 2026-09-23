'use client';

import { useMemo } from 'react';
import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWorkflowDurationEstimates } from '@/lib/hooks/use-workflow-duration-estimates';
import { Button } from '@/components/ui/button';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { useVisibleWorkflowTypes } from '@/lib/hooks/use-visible-workflow-types';

interface WorkflowTypeSelectorProps {
  /** When set, only this workflow type is listed (e.g. config dialog for a specific analysis). */
  restrictToType?: WorkflowRunType;
  /** When provided, an estimated run time is shown per assessment. */
  projectId?: string;
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
  projectId,
  selectedTypes,
  onSelectionChange,
  disabled = false,
  disabledTypes = [],
  showHeader = true,
  headerDescription,
  error,
}: WorkflowTypeSelectorProps) {
  const { workflowTypes: allTypes, isPending: isLoadingWorkflowTypes } = useWorkflowTypes();
  const { getEstimatedSeconds } = useWorkflowDurationEstimates(projectId);
  const { visibleGroups: allVisibleGroups } = useVisibleWorkflowTypes();

  const workflowTypes = useMemo(() => {
    if (restrictToType) {
      return allTypes.filter((wt) => wt.type === restrictToType);
    }
    return allTypes.filter((wt) => !wt.is_internal);
  }, [allTypes, restrictToType]);

  // Memoised so the derived lists below get a stable reference to depend on.
  const visibleGroups = useMemo(() => (restrictToType ? [] : allVisibleGroups), [restrictToType, allVisibleGroups]);

  // Exactly the checkboxes the render path below produces. The header count and
  // the bulk actions both work off this, so neither can drift from what is on
  // screen — `selectedTypes` may legitimately hold types this picker does not
  // list, and counting those would show nonsense like "12/11 selected".
  const renderedTypes = useMemo(
    () =>
      restrictToType
        ? workflowTypes.map((wt) => wt.type)
        : visibleGroups.flatMap((group) => group.workflows.map((wt) => wt.type)),
    [restrictToType, workflowTypes, visibleGroups],
  );

  const visibleCount = renderedTypes.length;
  const selectedVisibleCount = renderedTypes.filter((type) => selectedTypes.includes(type)).length;

  const handleCheckedChange = (type: WorkflowRunType, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedTypes, type]);
    } else {
      onSelectionChange(selectedTypes.filter((t) => t !== type));
    }
  };

  // Bulk actions only ever touch the checkboxes actually on screen and enabled.
  // Anything else already in `selectedTypes` is left alone, so a caller that
  // seeds the selection with a type this list does not offer keeps it.
  const bulkSelectableTypes = useMemo(
    () => renderedTypes.filter((type) => !disabledTypes.includes(type)),
    [renderedTypes, disabledTypes],
  );

  const selectedBulkCount = bulkSelectableTypes.filter((type) => selectedTypes.includes(type)).length;

  const handleSelectAll = () => {
    onSelectionChange([...selectedTypes, ...bulkSelectableTypes.filter((type) => !selectedTypes.includes(type))]);
  };

  const handleDeselectAll = () => {
    onSelectionChange(selectedTypes.filter((type) => !bulkSelectableTypes.includes(type)));
  };

  const renderCheckbox = (workflowType: WorkflowTypeDescription) => (
    <WorkflowTypeCheckbox
      key={workflowType.type}
      workflowType={workflowType}
      checked={selectedTypes.includes(workflowType.type)}
      onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
      disabled={controlsDisabled || disabledTypes.includes(workflowType.type)}
      estimatedSeconds={getEstimatedSeconds(workflowType.type)}
    />
  );

  const controlsDisabled = disabled || isLoadingWorkflowTypes;

  return (
    <div className="space-y-3">
      {showHeader && (
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-medium">
              Assessments
              <span className="text-destructive ml-1">*</span>
              {visibleCount > 0 && (
                <span className="ml-2 text-xs font-normal tabular-nums text-muted-foreground">
                  {selectedVisibleCount}/{visibleCount} selected
                </span>
              )}
            </h2>
            {headerDescription && <p className="text-sm text-muted-foreground">{headerDescription}</p>}
          </div>

          {bulkSelectableTypes.length > 1 && (
            <div className="flex shrink-0 items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={handleSelectAll}
                disabled={controlsDisabled || selectedBulkCount === bulkSelectableTypes.length}
              >
                Select all
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={handleDeselectAll}
                disabled={controlsDisabled || selectedBulkCount === 0}
              >
                Deselect all
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="space-y-4">
        {isLoadingWorkflowTypes ? (
          <p className="text-sm text-muted-foreground">Loading available assessments...</p>
        ) : restrictToType !== undefined ? (
          // Single-type mode: render from API types directly. Category config often omits internal workflows,
          // so walking categories would show nothing even when restrictToType is valid.
          workflowTypes.length > 0 ? (
            <div className="space-y-px">{workflowTypes.map(renderCheckbox)}</div>
          ) : (
            <p className="text-sm text-muted-foreground">This assessment is not available for your account.</p>
          )
        ) : (
          // One column of rail-style rows under each category, in the same
          // voice as the assessments tab: the rows are dense enough that the
          // list no longer needs to go two-up to fit.
          visibleGroups.map(({ category, workflows }) => (
            <section key={category.slug} aria-label={category.label}>
              <h3 className="px-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                {category.label}
              </h3>
              <div className="mt-1.5 space-y-px">{workflows.map(renderCheckbox)}</div>
            </section>
          ))
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
