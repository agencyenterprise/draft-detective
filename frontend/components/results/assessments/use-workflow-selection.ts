import { parseWorkflowRunType } from '@/components/results/constants';
import { useProjectView } from '@/components/results/project-view-context';
import { getProjectWorkflowRunsByTypeEndpointApiProjectProjectIdWorkflowRunsGet } from '@/lib/generated-api';
import type { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useMemo } from 'react';

interface UseWorkflowSelectionParams {
  projectId: string;
  workflowDetails: WorkflowRunDetail[];
  shareToken?: string | null;
  /**
   * Shown until the reader picks one. Views that put the assessment list in a
   * rail pass the first entry, so the pane opens on something rather than on a
   * prompt to click the thing already in front of you.
   */
  defaultWorkflowType?: WorkflowRunType | null;
}

/**
 * Which assessment the tab shows, read from the URL: `/analyses/<type>` names
 * the assessment and `?run=<id>` one run of it. Being in the URL is what lets
 * an issue in the document explorer link to the report it came from, and what
 * makes a selection survive a reload or a shared link.
 */
export function useWorkflowSelection({
  projectId,
  workflowDetails,
  shareToken,
  defaultWorkflowType = null,
}: UseWorkflowSelectionParams) {
  const params = useParams<{ workflowType?: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { assessmentHref } = useProjectView();

  const routedWorkflowType = parseWorkflowRunType(params.workflowType);
  const selectedWorkflowType = routedWorkflowType ?? defaultWorkflowType;
  // The run only means something for the assessment it belongs to.
  const selectedRunId = routedWorkflowType ? searchParams.get('run') : null;

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
    router.push(assessmentHref(workflowType));
  };

  const handleSelectRun = (run: WorkflowRunDetail) => {
    router.push(assessmentHref(run.run.type, run.run.id));
  };

  return {
    selectedWorkflowType,
    selectedWorkflowRun,
    historyData,
    handleSelectWorkflowType,
    handleSelectRun,
  };
}
