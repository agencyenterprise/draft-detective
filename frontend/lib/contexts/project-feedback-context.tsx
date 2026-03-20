'use client';

import { FeedbackPrivacyDialog } from '@/components/feedback/feedback-privacy-dialog';
import type { FeedbackResponse, FeedbackType, FeedbackVisibility } from '@/lib/generated-api';
import { updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { useProjectFeedback } from '@/lib/hooks/use-project-feedback';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useMemo, useState, ReactNode } from 'react';

interface SubmitFeedbackParams {
  issueId: string;
  feedbackType: FeedbackType;
  feedbackText?: string | null;
}

interface ProjectFeedbackContextValue {
  getFeedbackForIssue: (issueId: string) => FeedbackResponse | null;
  submitFeedback: (params: SubmitFeedbackParams) => void;
  isLoading: boolean;
  isSubmitting: boolean;
  isEnabled: boolean;
}

const ProjectFeedbackContext = createContext<ProjectFeedbackContextValue | null>(null);

interface ProjectFeedbackProviderProps {
  projectId: string | undefined;
  feedbackVisibility: FeedbackVisibility | null | undefined;
  children: ReactNode;
}

export function ProjectFeedbackProvider({ projectId, feedbackVisibility, children }: ProjectFeedbackProviderProps) {
  const queryClient = useQueryClient();
  const { getFeedbackForIssue, submitFeedback: doSubmit, isLoading, isSubmitting } = useProjectFeedback(projectId);

  const [pendingParams, setPendingParams] = useState<SubmitFeedbackParams | null>(null);
  const [isSavingVisibility, setIsSavingVisibility] = useState(false);

  const handlePrivacyConfirm = useCallback(
    async (visibility: FeedbackVisibility) => {
      if (!projectId || !pendingParams) return;
      setIsSavingVisibility(true);
      try {
        await updateProjectEndpointApiProjectProjectIdPatch({
          path: { project_id: projectId },
          body: { feedback_visibility: visibility },
        });
        // Invalidate the project query so the new visibility is reflected everywhere
        queryClient.invalidateQueries({ queryKey: ['project', projectId] });
        doSubmit(pendingParams);
      } finally {
        setIsSavingVisibility(false);
        setPendingParams(null);
      }
    },
    [projectId, pendingParams, doSubmit, queryClient],
  );

  const handlePrivacyCancel = useCallback(() => {
    setPendingParams(null);
  }, []);

  const submitFeedback = useCallback(
    (params: SubmitFeedbackParams) => {
      // If visibility hasn't been set yet, show the privacy dialog first
      if (feedbackVisibility == null) {
        setPendingParams(params);
        return;
      }
      doSubmit(params);
    },
    [feedbackVisibility, doSubmit],
  );

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

  return (
    <ProjectFeedbackContext.Provider value={value}>
      {children}
      <FeedbackPrivacyDialog
        isOpen={pendingParams !== null}
        onConfirm={handlePrivacyConfirm}
        onCancel={handlePrivacyCancel}
        isSubmitting={isSavingVisibility}
      />
    </ProjectFeedbackContext.Provider>
  );
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
