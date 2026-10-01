import { parseWorkflowRunType } from '@/components/results/constants';
import { useProjectView } from '@/components/results/project-view-context';
import type { ProjectOverview, WorkflowRunSummary, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowRunHistory } from '@/lib/hooks/use-project-data';
import { findRunByType } from '@/lib/workflow-state';
import { useParams, useRouter, useSearchParams } from 'next/navigation';

interface UseWorkflowSelectionParams {
  overview: ProjectOverview;
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
 *
 * Without a `?run=`, the run shown is the one the rail lists, so the pane and
 * the rail always agree about which run they mean.
 */
export function useWorkflowSelection({ overview, defaultWorkflowType = null }: UseWorkflowSelectionParams) {
  const params = useParams<{ workflowType?: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { assessmentHref } = useProjectView();

  const routedWorkflowType = parseWorkflowRunType(params.workflowType);
  const selectedWorkflowType = routedWorkflowType ?? defaultWorkflowType;
  // The run only means something for the assessment it belongs to.
  const selectedRunId = routedWorkflowType ? searchParams.get('run') : null;

  const mainRun = selectedWorkflowType ? findRunByType(overview.workflow_runs ?? [], selectedWorkflowType) : undefined;

  const { data: historyData } = useWorkflowRunHistory(overview, selectedWorkflowType);

  // An older run is found in the history, so until that loads there is nothing
  // to show for it; the latest run is in the overview already.
  const wantsOlderRun = !!selectedRunId && selectedRunId !== mainRun?.run.id;
  const isResolvingRun = wantsOlderRun && !historyData;
  const routedRun = wantsOlderRun ? historyData?.find((h) => h.run.id === selectedRunId) : undefined;
  const selectedWorkflowRun: WorkflowRunSummary | null = isResolvingRun ? null : (routedRun ?? mainRun ?? null);

  const handleSelectWorkflowType = (workflowType: WorkflowRunType) => {
    router.push(assessmentHref(workflowType));
  };

  const handleSelectRun = (run: WorkflowRunSummary) => {
    router.push(assessmentHref(run.run.type, run.run.id));
  };

  return {
    selectedWorkflowType,
    selectedWorkflowRun,
    isResolvingRun,
    historyData,
    handleSelectWorkflowType,
    handleSelectRun,
  };
}
