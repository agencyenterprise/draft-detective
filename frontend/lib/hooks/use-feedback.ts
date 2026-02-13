import type { FeedbackRequest, FeedbackType } from '@/lib/generated-api';
import { submitFeedbackApiFeedbackPost } from '@/lib/generated-api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { makeFeedbackKey, useFeedbackContext } from './use-batch-feedback';

/**
 * Generic feedback hook for any entity.
 *
 * Reads from the FeedbackProvider context (populated from ProjectDetailed.feedbacks)
 * so there are zero additional HTTP requests for reading feedback.
 *
 * On submit, invalidates the project query so the feedbacks list refreshes.
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
  const feedbackCtx = useFeedbackContext();

  const lookupKey = makeFeedbackKey(workflowRunId, entityPath as Record<string, unknown>);
  const feedback = feedbackCtx?.feedbackMap.get(lookupKey) ?? null;

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
      // Invalidate the project query so feedbacks refresh from ProjectDetailed
      queryClient.invalidateQueries({ queryKey: ['project'] });
    },
  });

  return {
    feedback,
    isLoading: false,
    submitFeedback: submitMutation.mutate,
    isSubmitting: submitMutation.isPending,
  };
}
