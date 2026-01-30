import { getProjectWorkflowRunsByTypeEndpointApiProjectProjectIdWorkflowRunsGet } from '@/lib/generated-api';
import type { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

interface UseWorkflowSelectionParams {
  projectId: string;
  workflowDetails: WorkflowRunDetail[];
  shareToken?: string | null;
}

export function useWorkflowSelection({ projectId, workflowDetails, shareToken }: UseWorkflowSelectionParams) {
  const [selectedWorkflowType, setSelectedWorkflowType] = useState<WorkflowRunType | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const mainRequestWorkflow = selectedWorkflowType
    ? workflowDetails.find((w) => w.run.type === selectedWorkflowType)
    : null;

  // Query key includes main run info to auto-refetch when status/id changes
  const { data: historyData } = useQuery({
    queryKey: [
      'workflow-runs-history',
      projectId,
      selectedWorkflowType,
      mainRequestWorkflow?.run.id,
      mainRequestWorkflow?.run.status,
    ],
    queryFn: () =>
      getProjectWorkflowRunsByTypeEndpointApiProjectProjectIdWorkflowRunsGet({
        path: { project_id: projectId },
        query: { workflow_type: selectedWorkflowType!, share_token: shareToken },
      }),
    enabled: !!selectedWorkflowType,
    staleTime: 0,
  });

  const selectedWorkflowRun = useMemo(() => {
    if (!selectedWorkflowType) return null;

    if (historyData && historyData.length > 0) {
      if (selectedRunId) {
        const fromHistory = historyData.find((h) => h.run.id === selectedRunId);
        if (fromHistory) return fromHistory;
      }
      return historyData[0];
    }

    return mainRequestWorkflow ?? null;
  }, [selectedWorkflowType, selectedRunId, historyData, mainRequestWorkflow]);

  const handleSelectWorkflowType = (workflowType: WorkflowRunType) => {
    setSelectedWorkflowType(workflowType);
    setSelectedRunId(null);
  };

  const handleSelectRun = (run: WorkflowRunDetail) => {
    setSelectedRunId(run.run.id);
  };

  return {
    selectedWorkflowType,
    selectedWorkflowRun,
    historyData,
    handleSelectWorkflowType,
    handleSelectRun,
  };
}
