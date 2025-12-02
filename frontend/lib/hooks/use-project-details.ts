import { Query, useQueries, useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { projectsApi, workflowsApi } from '../api';
import { WorkflowRun, WorkflowRunStatus, WorkflowRunType } from '../generated-api';
import { WorkflowRunDetail } from '../workflow-state';

const REFETCH_INTERVAL_MS = 3000;

export function useProjectDetails(projectId: string) {
  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.getProjectEndpointApiProjectProjectIdGet({ projectId }),
    refetchInterval: (query) => {
      const workflowRuns = query.state.data?.workflowRuns ?? [];
      return workflowRuns.some((run) => run.status === WorkflowRunStatus.Running) ? REFETCH_INTERVAL_MS : false;
    },
  });

  const workflowRuns = project?.workflowRuns ?? [];

  const workflowDetailsQueries = useQueries({
    queries: workflowRuns.map((workflowRun) => ({
      queryKey: ['workflowRun', workflowRun.id],
      queryFn: () => fetchWorkflowState(workflowRun),
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

function fetchWorkflowState(workflowRun: WorkflowRun): Promise<WorkflowRunDetail> {
  switch (workflowRun.type) {
    case WorkflowRunType.ClaimSubstantiation:
      return workflowsApi.getClaimSubstantiationWorkflowStateApiWorkflowsClaimSubstantiationWorkflowRunIdGet({
        workflowRunId: workflowRun.id,
      });
    case WorkflowRunType.MethodologicalAlignment:
      return workflowsApi.getMethodologicalAlignmentWorkflowStateApiWorkflowsMethodologicalAlignmentWorkflowRunIdGet({
        workflowRunId: workflowRun.id,
      });
    default:
      throw new Error(`Unknown workflow type: ${workflowRun.type satisfies never}`);
  }
}
