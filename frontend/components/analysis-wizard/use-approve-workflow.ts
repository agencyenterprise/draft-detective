'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/api-error';
import { approveWorkflowRunApiWorkflowRunsWorkflowRunIdApprovePost } from '@/lib/generated-api';

function approveRun(humanApprovalRunId: string | undefined) {
  if (!humanApprovalRunId) {
    throw new Error('Human approval workflow not found');
  }
  return approveWorkflowRunApiWorkflowRunsWorkflowRunIdApprovePost({
    path: { workflow_run_id: humanApprovalRunId },
  });
}

/**
 * Approves the HumanApproval workflow run, shows a success toast, and invalidates project queries.
 * Used from the project results UI (References tab and reference-review banner), not the create-project wizard.
 */
export function useApproveWorkflow(projectId: string, humanApprovalRunId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => approveRun(humanApprovalRunId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Analysis started!');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start analysis'));
    },
  });
}
