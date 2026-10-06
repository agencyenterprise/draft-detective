'use client';

import { FeedbackPrivacyDialog } from '@/components/feedback/feedback-privacy-dialog';
import type { FeedbackResponse, FeedbackType, FeedbackVisibility } from '@/lib/generated-api';
import { updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
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
  /** The feedback on show is somebody else's, so it can be read but not changed. */
  isReadOnly: boolean;
}

const ProjectFeedbackContext = createContext<ProjectFeedbackContextValue | null>(null);

interface ProjectFeedbackProviderProps {
  projectId: string | undefined;
  feedbackVisibility: FeedbackVisibility | null | undefined;
  /**
   * Show the feedback but do not let this viewer change it. Set for an admin looking at
   * a project someone else owns: the ratings belong to the author, and the API would
   * refuse a write from anyone but them.
   */
  readOnly?: boolean;
  children: ReactNode;
}

export function ProjectFeedbackProvider({
  projectId,
  feedbackVisibility,
  readOnly = false,
  children,
}: ProjectFeedbackProviderProps) {
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
        // Only the project's own fields changed, which the overview carries.
        queryClient.invalidateQueries({ queryKey: projectQueryKeys.overviews(projectId) });
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
      if (readOnly) return;
      // If visibility hasn't been set yet, show the privacy dialog first
      if (feedbackVisibility == null) {
        setPendingParams(params);
        return;
      }
      doSubmit(params);
    },
    [readOnly, feedbackVisibility, doSubmit],
  );

  const value = useMemo(
    () => ({
      getFeedbackForIssue,
      submitFeedback,
      isLoading,
      isSubmitting,
      isEnabled: !!projectId,
      isReadOnly: readOnly,
    }),
    [getFeedbackForIssue, submitFeedback, isLoading, isSubmitting, projectId, readOnly],
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
      isReadOnly: true,
    };
  }
  return context;
}

/**
 * Hook for issue-level feedback that uses the project-level cache.
 * Much more efficient than individual API calls per issue.
 */
export function useIssueFeedbackFromContext(issueId: string) {
  const { getFeedbackForIssue, submitFeedback, isLoading, isSubmitting, isReadOnly } = useProjectFeedbackContext();

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
    isReadOnly,
  };
}

/**
 * Whether feedback controls should render for an issue at all: only where there is a
 * project whose feedback can be read and written. Shared projects and issues rendered
 * outside the provider (the admin feedback sheet) have no feedback of the viewer's own,
 * so they get no controls rather than dead ones.
 */
export function useIsIssueFeedbackVisible(issueId: string | undefined): boolean {
  const { isEnabled } = useProjectFeedbackContext();
  return !!issueId && isEnabled;
}

/**
 * Whether this viewer can rate an issue, as opposed to only reading how it was rated.
 * False for an admin on someone else's project, where the thumbs would be controls that
 * cannot do anything.
 */
export function useCanSubmitIssueFeedback(issueId: string | undefined): boolean {
  const { isEnabled, isReadOnly } = useProjectFeedbackContext();
  return !!issueId && isEnabled && !isReadOnly;
}
