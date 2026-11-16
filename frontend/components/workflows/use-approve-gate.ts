'use client';

import { approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost, WorkflowGate } from '@/lib/generated-api';
import { useProjectMutation } from '@/lib/hooks/use-project-mutation';

/**
 * Approves a gate for the project's current revision, which starts every
 * assessment awaiting that gate. Shows a success toast and refreshes the
 * project's queries.
 */
export function useApproveGate(projectId: string, gate: WorkflowGate) {
  return useProjectMutation(projectId, {
    mutationFn: () =>
      approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost({
        path: { project_id: projectId, gate },
      }),
    successMessage: 'Analysis started!',
    errorMessage: 'Failed to start analysis',
  });
}
