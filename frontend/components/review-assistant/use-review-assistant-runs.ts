'use client';

import { getErrorMessage } from '@/lib/api-error';
import {
  cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost,
  listReviewAssistantRunsEndpointApiReviewAssistantProjectsProjectIdRunsGet,
  ReviewAssistantInputs,
  ReviewAssistantRun,
  startReviewAssistantRunApiReviewAssistantRunsPost,
  WorkflowRunStatus,
} from '@/lib/generated-api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ReviewOutputType } from './outputs';

const POLL_MS = 4000;

export function isRunActive(run: ReviewAssistantRun): boolean {
  return run.run.status === WorkflowRunStatus.Pending || run.run.status === WorkflowRunStatus.Running;
}

/**
 * The output's runs that were started on picked inputs, polled while one is
 * still going, plus start and cancel. Keyed under `['project', id]` so the
 * project-wide invalidations after an upload or a new revision refresh it too.
 */
export function useReviewAssistantRuns(projectId: string, output: ReviewOutputType | null) {
  const queryClient = useQueryClient();
  const queryKey = ['project', projectId, 'review-assistant-runs', output];

  const { data: runs = [], isLoading } = useQuery({
    queryKey,
    enabled: output !== null,
    queryFn: () =>
      listReviewAssistantRunsEndpointApiReviewAssistantProjectsProjectIdRunsGet({
        path: { project_id: projectId },
        query: { output: output! },
      }),
    refetchInterval: (query) => (query.state.data?.some(isRunActive) ? POLL_MS : false),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['project', projectId] });

  const start = useMutation({
    mutationFn: (inputs: ReviewAssistantInputs) =>
      startReviewAssistantRunApiReviewAssistantRunsPost({
        body: { project_id: projectId, output: output!, inputs },
      }),
    onSuccess: () => {
      toast.success('Started');
      invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error, 'Failed to start')),
  });

  const cancel = useMutation({
    mutationFn: async (runId: string) =>
      cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost({ path: { workflow_run_id: runId } }),
    onSuccess: () => {
      toast.success('Cancelled');
      invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error, 'Failed to cancel')),
  });

  return { runs, isLoading, start, cancel };
}
