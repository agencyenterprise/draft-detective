import type { FeedbackRequest, FeedbackType } from '@/lib/generated-api';
import { submitFeedbackApiFeedbackPost } from '@/lib/generated-api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { makeFeedbackKey, useBatchFeedbackContext } from './use-batch-feedback';

/**
 * Generic feedback hook for any entity.
 *
 * When used inside a BatchFeedbackProvider, reads from the pre-fetched
 * feedback map (zero additional requests). Falls back to returning null
 * if no batch context is available.
 *
 * @example
 * // For a claim
 * const claim = useFeedback(workflowId, { chunk_index: 0, claim_index: 1 });
 *
 * // For an issue (uses string hash ID)
 * const issue = useFeedback(workflowId, { issue_id: 'abc123' });
 */
export function useFeedback(workflowRunId: string, entityPath: Record<string, number | string>) {
  const queryClient = useQueryClient();
  const batchContext = useBatchFeedbackContext();

  const lookupKey = makeFeedbackKey(workflowRunId, entityPath as Record<string, unknown>);
  const feedback = batchContext?.feedbackMap.get(lookupKey) ?? null;
  const isLoading = batchContext?.isLoading ?? false;

  const submitMutation = useMutation({
    mutationFn: async (request: { feedback_type: FeedbackType; feedback_text?: string | null }) => {
      const feedbackRequest: FeedbackRequest = {
        workflow_run_id: workflowRunId,
        entity_path: entityPath,
        feedback_type: request.feedback_type,
        feedback_text: request.feedback_text || null,
      };

      return await submitFeedbackApiFeedbackPost({
        body: feedbackRequest,
      });
    },
    onSuccess: () => {
      // Invalidate the batch query so it re-fetches with the new feedback
      queryClient.invalidateQueries({ queryKey: ['workflow-feedback', workflowRunId] });
    },
  });

  return {
    feedback,
    isLoading,
    submitFeedback: submitMutation.mutate,
    isSubmitting: submitMutation.isPending,
  };
}
