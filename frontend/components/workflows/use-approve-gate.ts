'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/api-error';
import { approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost, WorkflowGate } from '@/lib/generated-api';

/**
 * Approves a gate for the project's current revision, which starts every
 * assessment awaiting that gate. Shows a success toast and invalidates
 * project queries.
 */
export function useApproveGate(projectId: string, gate: WorkflowGate) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost({
        path: { project_id: projectId, gate },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Analysis started!');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start analysis'));
    },
  });
}
