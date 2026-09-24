import { useMemo } from 'react';
import { WorkflowCategoryOrder, WorkflowPreset, WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { useWorkflowTypes } from './use-workflow-types';
import { useExperimentalFeatures } from '@/context/experimental-features-context';

export interface VisibleWorkflowGroup {
  category: WorkflowCategoryOrder;
  workflows: WorkflowTypeDescription[];
}

/**
 * The assessments on offer in the picker, grouped by category.
 *
 * Category membership is what decides whether a workflow is on offer:
 * anything absent from every category (the peer-review workflows, which are
 * started from their own tab) is not listed and not counted. Internal
 * workflows, and experimental ones for users who have not opted in, are
 * filtered out as well.
 */
export function useVisibleWorkflowTypes() {
  const { workflowTypes: allTypes, categories, presets: allPresets, isPending } = useWorkflowTypes();
  const { showExperimentalFeatures } = useExperimentalFeatures();

  const typeMap = useMemo(
    () => new Map(allTypes.filter((wt) => !wt.is_internal).map((wt) => [wt.type, wt])),
    [allTypes],
  );

  const visibleGroups = useMemo<VisibleWorkflowGroup[]>(
    () =>
      categories
        .map((category) => ({
          category,
          workflows: category.workflows
            .map((type) => typeMap.get(type as WorkflowRunType))
            .filter((wt): wt is WorkflowTypeDescription => wt !== undefined)
            .filter((wt) => showExperimentalFeatures || !wt.is_experimental),
        }))
        .filter((group) => group.workflows.length > 0),
    [categories, typeMap, showExperimentalFeatures],
  );

  const visibleTypes = useMemo<WorkflowRunType[]>(
    () => visibleGroups.flatMap((group) => group.workflows.map((wt) => wt.type)),
    [visibleGroups],
  );

  // Presets are themselves an alpha feature for now, so the chips exist only
  // for users who opted in; the API still serves them to everyone. Each one is
  // narrowed to what this user can see, and one whose every assessment is
  // hidden is left out rather than offered as an empty chip.
  const presets = useMemo<WorkflowPreset[]>(
    () =>
      showExperimentalFeatures
        ? allPresets
            .map((preset) => ({
              ...preset,
              workflows: preset.workflows.filter((type) => visibleTypes.includes(type)),
            }))
            .filter((preset) => preset.workflows.length > 0)
        : [],
    [allPresets, showExperimentalFeatures, visibleTypes],
  );

  return { visibleGroups, visibleTypes, presets, isPending };
}
