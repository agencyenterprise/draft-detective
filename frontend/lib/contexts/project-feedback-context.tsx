'use client';

import type { FeedbackResponse, FeedbackType } from '@/lib/generated-api';
import { useProjectFeedback } from '@/lib/hooks/use-project-feedback';
import { createContext, useContext, ReactNode, useMemo, useCallback } from 'react';

interface ProjectFeedbackContextValue {
  getFeedbackForIssue: (issueId: string) => FeedbackResponse | null;
  submitFeedback: (params: { issueId: string; feedbackType: FeedbackType; feedbackText?: string | null }) => void;
  isLoading: boolean;
  isSubmitting: boolean;
  isEnabled: boolean;
}

const ProjectFeedbackContext = createContext<ProjectFeedbackContextValue | null>(null);

interface ProjectFeedbackProviderProps {
  projectId: string | undefined;
  children: ReactNode;
}

export function ProjectFeedbackProvider({ projectId, children }: ProjectFeedbackProviderProps) {
  const { getFeedbackForIssue, submitFeedback, isLoading, isSubmitting } = useProjectFeedback(projectId);

  const value = useMemo(
    () => ({
      getFeedbackForIssue,
      submitFeedback,
      isLoading,
      isSubmitting,
      isEnabled: !!projectId,
    }),
    [getFeedbackForIssue, submitFeedback, isLoading, isSubmitting, projectId],
  );

  return <ProjectFeedbackContext.Provider value={value}>{children}</ProjectFeedbackContext.Provider>;
}

export function useProjectFeedbackContext() {
  const context = useContext(ProjectFeedbackContext);
  if (!context) {
    // Return a no-op context for components outside the provider (e.g., readOnly mode)
    return {
      getFeedbackForIssue: () => null,
      submitFeedback: () => {},
      isLoading: false,
      isSubmitting: false,
      isEnabled: false,
    };
  }
  return context;
}

/**
 * Hook for issue-level feedback that uses the project-level cache.
 * Much more efficient than individual API calls per issue.
 */
export function useIssueFeedbackFromContext(issueId: string) {
  const { getFeedbackForIssue, submitFeedback, isLoading, isSubmitting } = useProjectFeedbackContext();

  const feedback = getFeedbackForIssue(issueId);

  const submit = useCallback(
    (params: { feedback_type: FeedbackType; feedback_text?: string | null }) => {
      submitFeedback({
        issueId,
        feedbackType: params.feedback_type,
        feedbackText: params.feedback_text,
      });
    },
    [issueId, submitFeedback],
  );

  return {
    feedback,
    isLoading,
    submitFeedback: submit,
    isSubmitting,
  };
}
