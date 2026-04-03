'use client';

import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/api-error';
import { approveWorkflowRunApiWorkflowRunsWorkflowRunIdApprovePost } from '@/lib/generated-api';

export function useApproveAndNavigate(projectId: string, humanApprovalRunId: string | undefined) {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      if (!humanApprovalRunId) {
        throw new Error('Human approval workflow not found');
      }
      return approveWorkflowRunApiWorkflowRunsWorkflowRunIdApprovePost({
        path: { workflow_run_id: humanApprovalRunId },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Analysis started! Redirecting to your project...');
      router.push(`/projects/${projectId}?fromWizard=true`);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start analysis'));
    },
  });
}
