import { useQuery } from '@tanstack/react-query';
import { getWorkflowProgressEndpointApiProgressWorkflowWorkflowRunIdProgressGet } from '@/lib/generated-api';

const REFETCH_INTERVAL_MS = 2000;

/**
 * Hook to fetch workflow progress for a single workflow run.
 * Automatically stops polling when all progress entries are completed.
 */
export function useWorkflowProgress(workflowRunId: string | null) {
  return useQuery({
    queryKey: ['workflow-progress', workflowRunId],
    queryFn: () =>
      getWorkflowProgressEndpointApiProgressWorkflowWorkflowRunIdProgressGet({
        path: { workflow_run_id: workflowRunId! },
      }),
    enabled: !!workflowRunId,
    refetchInterval: (query) => {
      const progress = query.state.data ?? [];
      const hasActive = progress.some((p) => p.started_at && !p.completed_at);
      return hasActive ? REFETCH_INTERVAL_MS : false;
    },
  });
}
