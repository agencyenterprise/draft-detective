'use client';

import {
  cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost,
  listReviewAssistantRequestsEndpointApiProjectProjectIdReviewAssistantRequestsGet,
  ReviewAssistantOutput,
  startReviewAssistantRequestEndpointApiProjectProjectIdReviewAssistantRequestsPost,
} from '@/lib/generated-api';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useProjectMutation } from '@/lib/hooks/use-project-mutation';
import { isWorkflowProcessing } from '@/lib/workflow-state';
import { useQuery } from '@tanstack/react-query';

/** Polled while a request is queued or running, so its status and results arrive on their own. */
const ACTIVE_POLL_MS = 4000;

/** The project's Review Assistant requests, newest first, across every revision. */
export function useReviewAssistantRequests(projectId: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    enabled,
    queryKey: projectQueryKeys.reviewAssistantRequests(projectId),
    queryFn: () =>
      listReviewAssistantRequestsEndpointApiProjectProjectIdReviewAssistantRequestsGet({
        path: { project_id: projectId },
      }),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((request) => isWorkflowProcessing(request)) ? ACTIVE_POLL_MS : false,
  });
}

export interface StartRequestArgs {
  outputs: ReviewAssistantOutput[];
  fileIds: string[];
}

/**
 * Starts a request. Its run id arrives through `mutate`'s own `onSuccess`,
 * which runs once the project's caches carry the new run.
 */
export function useStartReviewAssistantRequest(projectId: string) {
  return useProjectMutation(projectId, {
    mutationFn: ({ outputs, fileIds }: StartRequestArgs) =>
      startReviewAssistantRequestEndpointApiProjectProjectIdReviewAssistantRequestsPost({
        path: { project_id: projectId },
        body: { outputs, file_ids: fileIds },
      }),
    errorMessage: 'Failed to start the Review Assistant',
  });
}

export function useCancelReviewAssistantRequest(projectId: string) {
  return useProjectMutation(projectId, {
    mutationFn: (runId: string) =>
      cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost({ path: { workflow_run_id: runId } }),
    successMessage: 'Request cancelled',
    errorMessage: 'Failed to cancel the request',
  });
}
