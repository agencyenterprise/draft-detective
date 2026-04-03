import {
  resolveIssueEndpointApiIssuesIssueIdResolvePost,
  unresolveIssueEndpointApiIssuesIssueIdUnresolvePost,
} from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export function useIssueActions() {
  const queryClient = useQueryClient();

  const resolveMutation = useMutation({
    mutationFn: (issueId: string) =>
      resolveIssueEndpointApiIssuesIssueIdResolvePost({
        path: { issue_id: issueId },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project'] });
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project'] });
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
