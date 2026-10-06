'use client';

import { getErrorMessage } from '@/lib/api-error';
import {
  cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost,
  ProjectOverview,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  WorkflowRunSummary,
  WorkflowRunType,
} from '@/lib/generated-api';
import { useProjectOverview } from '@/lib/hooks/use-project-data';
import { findRunByType } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { toast } from 'sonner';
import { derivePeerReviewFacts, PeerReviewFacts } from './peer-review-derive';

interface UsePeerReviewStateArgs {
  overview: ProjectOverview;
}

/** A planning summary that lives on an earlier revision than the one on screen. */
export interface PlanFallback {
  run: WorkflowRunSummary;
  revision: number;
  /** That revision's overview, so the run's own issues resolve correctly. */
  overview: ProjectOverview;
}

export interface PeerReviewState {
  facts: PeerReviewFacts;
  planFallback?: PlanFallback;
  startStage: (types: WorkflowRunType[]) => void;
  cancelRun: (runId: string) => void;
  isStarting: boolean;
}

/**
 * Derived peer-review state plus the two mutations the tab needs.
 *
 * These workflows are startable only from this tab, so start/cancel live here
 * rather than going through StartWorkflowButton — that opens WorkflowConfigDialog,
 * which is the dialog this tab exists to remove, and none of the three has
 * anything to configure.
 */
export function usePeerReviewState({ overview }: UsePeerReviewStateArgs): PeerReviewState {
  const projectId = overview.project.id;
  const queryClient = useQueryClient();

  const facts = useMemo(() => derivePeerReviewFacts(overview), [overview]);

  // Workflow runs are scoped to a revision, so the planning summary disappears
  // from view the moment a revised draft creates a new one — even though it is
  // still the summary for the memos being worked through. Fetch the reviewed
  // revision's overview to keep showing it. Same query key as the revision
  // switcher, so this usually resolves from cache, and the project-wide
  // invalidation below clears it too.
  const needsPlanFallback =
    facts.reviewedRevision !== null && facts.reviewedRevision !== facts.viewedRevision && !facts.runs.plan;
  const { data: reviewedRevisionOverview } = useProjectOverview(
    needsPlanFallback ? projectId : null,
    facts.reviewedRevision,
  );

  const planFallback = useMemo<PlanFallback | undefined>(() => {
    if (!needsPlanFallback || !reviewedRevisionOverview || facts.reviewedRevision === null) return undefined;
    const run = findRunByType(reviewedRevisionOverview.workflow_runs ?? [], WorkflowRunType.RevisionPlanningSummary);
    return run ? { run, revision: facts.reviewedRevision, overview: reviewedRevisionOverview } : undefined;
  }, [needsPlanFallback, reviewedRevisionOverview, facts.reviewedRevision]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['project', projectId] });

  const startMutation = useMutation({
    mutationFn: async (workflowTypes: WorkflowRunType[]) =>
      startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: { project_id: projectId, workflow_types: workflowTypes },
      }),
    onSuccess: (_data, workflowTypes) => {
      toast.success(workflowTypes.length > 1 ? 'Assessments started' : 'Assessment started');
      invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error, 'Failed to start assessment')),
  });

  const cancelMutation = useMutation({
    mutationFn: async (runId: string) =>
      cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost({
        path: { workflow_run_id: runId },
      }),
    onSuccess: () => {
      toast.success('Assessment cancelled');
      invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error, 'Failed to cancel assessment')),
  });

  return {
    facts,
    planFallback,
    startStage: startMutation.mutate,
    cancelRun: cancelMutation.mutate,
    isStarting: startMutation.isPending,
  };
}
