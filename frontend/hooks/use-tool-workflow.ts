import { WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useMemo } from 'react';

/**
 * Generic hook for polling workflow state by projectId with type filtering.
 * Encapsulates the useProjectDetails + filter pattern used by tools.
 *
 * @param projectId - The project ID to poll
 * @param workflowTypes - Array of workflow types to filter for
 * @returns Object containing filtered workflow details and processing state
 */
export function useToolWorkflow(projectId: string | null, workflowTypes: WorkflowRunType[]) {
  const { workflowDetails, isProcessing: isWorkflowProcessing, error } = useProjectDetails(projectId, true);

  const filteredWorkflows = useMemo(() => {
    return workflowDetails.filter((w) => workflowTypes.includes(w.run.type));
  }, [workflowDetails, workflowTypes]);

  const isProcessing = projectId ? isWorkflowProcessing : false;

  return {
    workflowDetails: filteredWorkflows,
    allWorkflowDetails: workflowDetails,
    isProcessing,
    error,
  };
}
