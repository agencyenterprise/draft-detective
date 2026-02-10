import { useFeedback } from './use-feedback';

/**
 * Type-safe wrapper for issue-level feedback
 *
 * Uses the generic useFeedback hook with issue-specific entity path
 * @param workflowRunId - The ID of the workflow run that generated the issue
 * @param issueId - The unique hash ID of the issue
 */
export function useIssueFeedback(workflowRunId: string, issueId: string) {
  return useFeedback(workflowRunId, { issue_id: issueId });
}
