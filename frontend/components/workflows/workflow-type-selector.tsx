'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWorkflowDurationEstimates } from '@/lib/hooks/use-workflow-duration-estimates';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { WorkflowPresetChips } from './workflow-presets';
import { useVisibleWorkflowTypes } from '@/lib/hooks/use-visible-workflow-types';
import { filterWorkflowGroups } from '@/lib/workflow-search';

interface WorkflowTypeSelectorProps {
  /** When set, only this workflow type is listed (e.g. config dialog for a specific analysis). */
  restrictToType?: WorkflowRunType;
  /** When provided, an estimated run time is shown per assessment. */
  projectId?: string;
  selectedTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabledTypes?: WorkflowRunType[];
  /** Already running or queued: shown as running, unticked and not selectable. */
  runningTypes?: WorkflowRunType[];
}

export function WorkflowTypeSelector({
  restrictToType,
  projectId,
  selectedTypes,
  onSelectionChange,
  disabledTypes = [],
  runningTypes = [],
}: WorkflowTypeSelectorProps) {
  const { workflowTypes: allTypes, getWorkflowTypeName, isPending: isLoadingWorkflowTypes } = useWorkflowTypes();
  const { getEstimatedSeconds } = useWorkflowDurationEstimates(projectId);
  const { visibleGroups: allVisibleGroups, presets } = useVisibleWorkflowTypes();
  const [query, setQuery] = useState('');
  const isSearching = query.trim() !== '';

  const workflowTypes = useMemo(() => {
    if (restrictToType) {
      return allTypes.filter((wt) => wt.type === restrictToType);
    }
    return allTypes.filter((wt) => !wt.is_internal);
  }, [allTypes, restrictToType]);

  // Memoised so the derived lists below get a stable reference to depend on.
  const visibleGroups = useMemo(() => (restrictToType ? [] : allVisibleGroups), [restrictToType, allVisibleGroups]);
  // The groups after the search box: what the list below actually draws.
  const shownGroups = useMemo(() => filterWorkflowGroups(visibleGroups, query), [visibleGroups, query]);

  // Exactly the checkboxes the picker offers, search aside. The header count
  // works off this so it cannot drift from the list — `selectedTypes` may
  // legitimately hold types this picker does not list, and counting those
  // would show nonsense like "12/11 selected". A search hides rows without
  // unselecting them, so the count keeps covering every row.
  const renderedTypes = useMemo(
    () =>
      restrictToType
        ? workflowTypes.map((wt) => wt.type)
        : visibleGroups.flatMap((group) => group.workflows.map((wt) => wt.type)),
    [restrictToType, workflowTypes, visibleGroups],
  );
  const shownTypes = useMemo(
    () => (restrictToType ? renderedTypes : shownGroups.flatMap((group) => group.workflows.map((wt) => wt.type))),
    [restrictToType, renderedTypes, shownGroups],
  );

  const visibleCount = renderedTypes.length;
  const isSelected = (type: WorkflowRunType) => selectedTypes.includes(type) && !runningTypes.includes(type);
  const selectedVisibleCount = renderedTypes.filter(isSelected).length;

  // Every change drops what is running, so a row ticked before its assessment
  // started elsewhere stays unticked once that run finishes, instead of
  // coming back checked after a Deselect all that could not reach it.
  const commitSelection = (types: WorkflowRunType[]) =>
    onSelectionChange(types.filter((type) => !runningTypes.includes(type)));

  const handleCheckedChange = (type: WorkflowRunType, checked: boolean) => {
    if (checked) {
      commitSelection([...selectedTypes, type]);
    } else {
      commitSelection(selectedTypes.filter((t) => t !== type));
    }
  };

  const isSelectable = (type: WorkflowRunType) => !disabledTypes.includes(type) && !runningTypes.includes(type);
  // Presets choose from every enabled row, whatever the search shows.
  const selectableTypes = renderedTypes.filter(isSelectable);
  // Bulk actions only ever touch the checkboxes actually on screen and enabled,
  // so during a search they act on the matches. Anything else already in
  // `selectedTypes` is left alone, so a caller that seeds the selection with a
  // type this list does not offer keeps it.
  const bulkSelectableTypes = shownTypes.filter(isSelectable);

  const selectedBulkCount = bulkSelectableTypes.filter((type) => selectedTypes.includes(type)).length;

  const handleSelectAll = () => {
    commitSelection([...selectedTypes, ...bulkSelectableTypes.filter((type) => !selectedTypes.includes(type))]);
  };

  const handleDeselectAll = () => {
    commitSelection(selectedTypes.filter((type) => !bulkSelectableTypes.includes(type)));
  };

  const renderCheckbox = (workflowType: WorkflowTypeDescription) => (
    <WorkflowTypeCheckbox
      key={workflowType.type}
      workflowType={workflowType}
      checked={isSelected(workflowType.type)}
      onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
      running={runningTypes.includes(workflowType.type)}
      disabled={
        isLoadingWorkflowTypes || disabledTypes.includes(workflowType.type) || runningTypes.includes(workflowType.type)
      }
      estimatedSeconds={getEstimatedSeconds(workflowType.type)}
    />
  );

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-sm font-medium">
          Assessments
          <span className="text-destructive ml-1">*</span>
          {visibleCount > 0 && (
            <span className="ml-2 text-xs font-normal tabular-nums text-muted-foreground">
              {selectedVisibleCount}/{visibleCount} selected
            </span>
          )}
        </h2>

        {selectableTypes.length > 1 && (
          <div className="flex shrink-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={handleSelectAll}
              disabled={isLoadingWorkflowTypes || selectedBulkCount === bulkSelectableTypes.length}
            >
              {isSearching ? 'Select matches' : 'Select all'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={handleDeselectAll}
              disabled={isLoadingWorkflowTypes || selectedBulkCount === 0}
            >
              {isSearching ? 'Deselect matches' : 'Deselect all'}
            </Button>
          </div>
        )}
      </div>
      {/* Presets and search sit between the header and the list, and stick to
          the top of whatever scrolls it, so both stay in reach halfway down a
          long list. A department picks its set here and the rows below show
          what that set is. Never in single-type mode, where there is nothing
          to choose between. */}
      {restrictToType === undefined && !isLoadingWorkflowTypes && renderedTypes.length > 0 && (
        <div className="sticky top-0 z-10 space-y-3 bg-background py-1">
          {presets.length > 0 && (
            <WorkflowPresetChips
              presets={presets}
              selectedTypes={selectedTypes}
              offeredTypes={selectableTypes}
              onSelectionChange={commitSelection}
              disabled={isLoadingWorkflowTypes}
              getWorkflowTypeName={getWorkflowTypeName}
            />
          )}
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search assessments"
              aria-label="Search assessments"
              className="h-8 pl-7 text-xs"
            />
          </div>
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
        ) : shownGroups.length === 0 && isSearching ? (
          <p className="px-2 text-sm text-muted-foreground">No assessments match “{query.trim()}”.</p>
        ) : (
          // One column of rail-style rows under each category, in the same
          // voice as the assessments tab: the rows are dense enough that the
          // list no longer needs to go two-up to fit.
          shownGroups.map(({ category, workflows }) => (
            <section key={category.slug} aria-label={category.label}>
              <h3 className="px-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                {category.label}
              </h3>
              <div className="mt-1.5 space-y-px">{workflows.map(renderCheckbox)}</div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
