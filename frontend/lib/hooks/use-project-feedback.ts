import type { FeedbackRequest, FeedbackResponse, FeedbackType } from '@/lib/generated-api';
import { getProjectFeedbackApiFeedbackProjectProjectIdGet, submitFeedbackApiFeedbackPost } from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { toast } from 'sonner';

/**
 * Hook to fetch all issue feedback for a project in a single call.
 * Provides methods to get feedback for individual issues and submit new feedback.
 */
export function useProjectFeedback(projectId: string | undefined) {
  const queryClient = useQueryClient();
  const queryKey = ['feedback', 'project', projectId];

  const { data: feedbackList, isLoading } = useQuery({
    queryKey,
    queryFn: async () => {
      if (!projectId) return [];
      try {
        return await getProjectFeedbackApiFeedbackProjectProjectIdGet({
          path: { project_id: projectId },
        });
      } catch {
        return [];
      }
    },
    enabled: !!projectId,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Create a map for O(1) lookup by issue_id, memoized to avoid
  // re-creating on every render and causing unnecessary consumer re-renders.
  const feedbackByIssueId = useMemo(() => {
    const map = new Map<string, FeedbackResponse>();
    feedbackList?.forEach((f) => {
      if (f.issue_id) {
        map.set(f.issue_id, f);
      }
    });
    return map;
  }, [feedbackList]);

  const getFeedbackForIssue = useCallback(
    (issueId: string): FeedbackResponse | null => {
      return feedbackByIssueId.get(issueId) ?? null;
    },
    [feedbackByIssueId],
  );

  const submitMutation = useMutation({
    mutationFn: async ({
      issueId,
      feedbackType,
      feedbackText,
    }: {
      issueId: string;
      feedbackType: FeedbackType;
      feedbackText?: string | null;
    }) => {
      const body: FeedbackRequest = {
        issue_id: issueId,
        feedback_type: feedbackType,
        feedback_text: feedbackText || null,
      };
      return await submitFeedbackApiFeedbackPost({ body });
    },
    onSuccess: (newFeedback) => {
      // Update the cache optimistically
      queryClient.setQueryData<FeedbackResponse[]>(queryKey, (old) => {
        if (!old) return [newFeedback];
        const issueId = newFeedback.issue_id;
        const existingIndex = old.findIndex((f) => f.issue_id === issueId);
        if (existingIndex >= 0) {
          const updated = [...old];
          updated[existingIndex] = newFeedback;
          return updated;
        }
        return [...old, newFeedback];
      });
      toast.success('Thanks for your feedback!');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to submit feedback'));
    },
  });

  return {
    feedbackList,
    isLoading,
    getFeedbackForIssue,
    submitFeedback: submitMutation.mutate,
    isSubmitting: submitMutation.isPending,
  };
}
