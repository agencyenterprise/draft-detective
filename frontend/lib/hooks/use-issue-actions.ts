import {
  resolveIssueEndpointApiIssuesIssueIdResolvePost,
  unresolveIssueEndpointApiIssuesIssueIdUnresolvePost,
} from '@/lib/generated-api';
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
    onError: () => {
      toast.error('Failed to resolve issue');
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
    onError: () => {
      toast.error('Failed to unresolve issue');
    },
  });

  return {
    resolveIssue: resolveMutation.mutate,
    unresolveIssue: unresolveMutation.mutate,
    isResolving: resolveMutation.isPending,
    isUnresolving: unresolveMutation.isPending,
  };
}
