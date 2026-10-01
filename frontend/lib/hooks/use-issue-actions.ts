import {
  resolveIssueEndpointApiIssuesIssueIdResolvePost,
  unresolveIssueEndpointApiIssuesIssueIdUnresolvePost,
} from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { Issue, IssueResponse } from '@/lib/generated-api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { projectIssuesPrefix } from './use-project-data';

export function useIssueActions() {
  const queryClient = useQueryClient();

  // Write the new resolution into the cached issue lists rather than refetching:
  // nothing else about the project changed, and the lists can run to megabytes.
  const applyResolution = (updated: IssueResponse) => {
    queryClient.setQueriesData({ queryKey: projectIssuesPrefix(updated.project_id) }, (issues: Issue[] | undefined) =>
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
  };

  const resolveMutation = useMutation({
    mutationFn: (issueId: string) =>
      resolveIssueEndpointApiIssuesIssueIdResolvePost({
        path: { issue_id: issueId },
      }),
    onSuccess: (updated) => {
      applyResolution(updated);
      toast.success('Issue marked as resolved');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to resolve issue'));
    },
  });

  const unresolveMutation = useMutation({
    mutationFn: (issueId: string) =>
      unresolveIssueEndpointApiIssuesIssueIdUnresolvePost({
        path: { issue_id: issueId },
      }),
    onSuccess: (updated) => {
      applyResolution(updated);
      toast.success('Issue marked as unresolved');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to unresolve issue'));
    },
  });

  return {
    resolveIssue: resolveMutation.mutate,
    unresolveIssue: unresolveMutation.mutate,
    isResolving: resolveMutation.isPending,
    isUnresolving: unresolveMutation.isPending,
  };
}
