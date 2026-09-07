import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { getProjectEndpointApiProjectProjectIdGet, WorkflowRunStatus } from '../generated-api';
import { useShare } from '@/context/share-context';

const REFETCH_INTERVAL_MS = 3000;
// A run waiting on approval can be released from elsewhere (another tab, the
// MCP tool). Poll slowly so the page notices without treating the wait as work.
const AWAITING_APPROVAL_REFETCH_INTERVAL_MS = 15000;

export function useProjectDetails(projectId: string | null, revision?: number | null) {
  const { shareToken } = useShare();

  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useQuery({
    enabled: !!projectId,
    queryKey: ['project', projectId, revision ?? 'latest'],
    staleTime: 60 * 1000 * 5, // 5 minutes
    queryFn: () =>
      getProjectEndpointApiProjectProjectIdGet({
        path: { project_id: projectId! },
        query: { include_internal: true, share_token: shareToken, revision: revision ?? undefined },
      }),
    refetchInterval: (query) => {
      const workflowRuns = query.state.data?.workflow_runs ?? [];
      if (
        workflowRuns.some(
          (w) => w.run.status === WorkflowRunStatus.Running || w.run.status === WorkflowRunStatus.Pending,
        )
      ) {
        return REFETCH_INTERVAL_MS;
      }
      if (workflowRuns.some((w) => w.run.status === WorkflowRunStatus.AwaitingApproval)) {
        return AWAITING_APPROVAL_REFETCH_INTERVAL_MS;
      }
      return false;
    },
  });

  const workflowDetails = useMemo(() => project?.workflow_runs ?? [], [project]);
  const files = useMemo(() => project?.files ?? [], [project]);
  const issues = useMemo(() => project?.issues ?? [], [project]);

  const isProcessing = useMemo(
    () =>
      isProjectLoading ||
      workflowDetails.some(
        (w) => w.run.status === WorkflowRunStatus.Running || w.run.status === WorkflowRunStatus.Pending,
      ),
    [isProjectLoading, workflowDetails],
  );

  return {
    project,
    workflowDetails,
    files,
    issues,
    isProcessing,
    isLoading: isProjectLoading,
    error: projectError,
  };
}
