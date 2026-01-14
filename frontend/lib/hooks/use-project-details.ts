import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { getProjectEndpointApiProjectProjectIdGet, WorkflowRunStatus } from '../generated-api';

const REFETCH_INTERVAL_MS = 3000;

export function useProjectDetails(projectId: string | null, includeInternal: boolean = false) {
  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useQuery({
    enabled: !!projectId,
    queryKey: ['project', projectId, includeInternal],
    queryFn: () =>
      getProjectEndpointApiProjectProjectIdGet({
        path: { project_id: projectId! },
        query: { include_internal: includeInternal },
      }),
    refetchInterval: (query) => {
      const workflowRuns = query.state.data?.workflow_runs ?? [];
      return workflowRuns.some(
        (w) => w.run.status === WorkflowRunStatus.Running || w.run.status === WorkflowRunStatus.Pending,
      )
        ? REFETCH_INTERVAL_MS
        : false;
    },
  });

  const workflowDetails = useMemo(() => project?.workflow_runs ?? [], [project]);

  const isProcessing = useMemo(
    () =>
      workflowDetails.some(
        (w) => w.run.status === WorkflowRunStatus.Running || w.run.status === WorkflowRunStatus.Pending,
      ),
    [workflowDetails],
  );

  const isLoading = isProjectLoading;

  return {
    project,
    workflowDetails,
    isProcessing,
    isLoading,
    error: projectError,
  };
}
