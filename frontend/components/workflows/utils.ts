import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';

/**
 * Checks if any of the selected workflow types require web search.
 */
export function hasWebSearchRequirement(
  selectedTypes: WorkflowRunType[],
  workflowTypes?: WorkflowTypeDescription[],
): boolean {
  return selectedTypes.some((type) => workflowTypes?.find((wt) => wt.type === type)?.needs_web_search);
}
