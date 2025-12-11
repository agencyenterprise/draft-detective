import { Query, useQueries, useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import {
  getProjectEndpointApiProjectProjectIdGet,
  getWorkflowStateApiWorkflowsWorkflowRunIdGet,
  WorkflowRunDetail,
  WorkflowRunStatus,
} from '../generated-api';

const REFETCH_INTERVAL_MS = 3000;

export function useProjectDetails(projectId: string) {
  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProjectEndpointApiProjectProjectIdGet({ path: { project_id: projectId } }),
    refetchInterval: (query) => {
      const workflowRuns = query.state.data?.workflow_runs ?? [];
      return workflowRuns.some((run) => run.status === WorkflowRunStatus.Running) ? REFETCH_INTERVAL_MS : false;
    },
  });

  const workflowRuns = project?.workflow_runs ?? [];

  const workflowDetailsQueries = useQueries({
    queries: workflowRuns.map((workflowRun) => ({
      queryKey: ['workflowRun', workflowRun.id],
      queryFn: () => getWorkflowStateApiWorkflowsWorkflowRunIdGet({ path: { workflow_run_id: workflowRun.id } }),
      refetchInterval: (query: Query<WorkflowRunDetail>) => {
        return query.state.data?.run.status === WorkflowRunStatus.Running ? REFETCH_INTERVAL_MS : false;
      },
    })),
  });

  const workflowDetails = useMemo(
    () =>
      workflowDetailsQueries.map((query) => query.data).filter((run): run is WorkflowRunDetail => run !== undefined),
    [workflowDetailsQueries],
  );

  const isProcessing = useMemo(
    () => workflowDetails.some((w) => w.run.status === WorkflowRunStatus.Running),
    [workflowDetails],
  );

  const isLoading = isProjectLoading || workflowDetailsQueries.some((query) => query.isLoading);

  return {
    project,
    workflowDetails,
    isProcessing,
    isLoading,
    error: projectError,
  };
}
