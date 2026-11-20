import {
  resolveIssueEndpointApiIssuesIssueIdResolvePost,
  unresolveIssueEndpointApiIssuesIssueIdUnresolvePost,
} from '@/lib/generated-api';
import { Issue, IssueResponse } from '@/lib/generated-api';
import { useToastMutation } from '@/lib/hooks/use-toast-mutation';
import { writeServerAnswer } from '@/lib/query-cache';
import { useQueryClient } from '@tanstack/react-query';
import { projectQueryKeys } from './use-project-data';

interface ResolutionChange {
  send: (options: { path: { issue_id: string } }) => Promise<IssueResponse>;
  success: string;
  failure: string;
}

/**
 * Resolves or unresolves an issue, then writes the new resolution into the
 * cached issue lists rather than refetching them: nothing else about the
 * project changed, and the lists can run to megabytes.
 */
function useResolutionChange({ send, success, failure }: ResolutionChange) {
  const queryClient = useQueryClient();
  return useToastMutation({
    mutationFn: (issueId: string) => send({ path: { issue_id: issueId } }),
    successMessage: success,
    errorMessage: failure,
    onSuccess: async (updated) => {
      await writeServerAnswer<Issue[]>(
        queryClient,
        { queryKey: projectQueryKeys.allIssues(updated.project_id) },
        (issues) =>
          issues?.map((issue) =>
            issue.id === updated.id
              ? {
                  ...issue,
                  // Generated `Date` fields arrive as ISO strings, which is what this is.
                  resolved_at: updated.resolved_at as unknown as Issue['resolved_at'],
                  resolved_by: updated.resolved_by,
                  status: updated.status,
                }
              : issue,
          ),
      );
    },
  });
}

export function useIssueActions() {
  const resolveMutation = useResolutionChange({
    send: resolveIssueEndpointApiIssuesIssueIdResolvePost,
    success: 'Issue marked as resolved',
    failure: 'Failed to resolve issue',
  });
  const unresolveMutation = useResolutionChange({
    send: unresolveIssueEndpointApiIssuesIssueIdUnresolvePost,
    success: 'Issue marked as unresolved',
    failure: 'Failed to unresolve issue',
  });

  return {
    resolveIssue: resolveMutation.mutate,
    unresolveIssue: unresolveMutation.mutate,
    isResolving: resolveMutation.isPending,
    isUnresolving: unresolveMutation.isPending,
  };
}
