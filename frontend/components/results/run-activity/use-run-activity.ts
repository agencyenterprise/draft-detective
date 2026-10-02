'use client';

import { useShare } from '@/context/share-context';
import {
  getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet,
  WorkflowProgressResponse,
  WorkflowRunSummary,
  WorkflowRunStatus,
} from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

const REFETCH_INTERVAL_MS = 3000;

/** One assessment that is working right now, or waiting its turn to. */
export interface RunActivityItem {
  runId: string;
  /** The assessment, named the way the rest of the view names it. */
  label: string;
  /** What it is doing right now, when that says more than the label does. */
  detail: string | null;
  currentStep: number;
  totalSteps: number;
}

export interface RunActivity {
  running: RunActivityItem[];
  queued: RunActivityItem[];
}

const EMPTY: RunActivity = { running: [], queued: [] };

/**
 * What the project is doing at this moment: one entry per active workflow run,
 * carrying the step counts of whatever it is working on.
 *
 * Progress rows accumulate for the life of a revision, so the finished ones are
 * dropped here rather than being offered as history — a run that has already
 * delivered its results is read in the Assessments tab, not in a progress list.
 * Rows are keyed back to their run so twelve concurrent assessments read as
 * twelve lines instead of however many nodes they happen to have open.
 */
export function useRunActivity(
  projectId: string,
  workflowDetails: WorkflowRunSummary[],
  enabled: boolean,
): RunActivity {
  const { shareToken } = useShare();
  const { getWorkflowTypeName } = useWorkflowTypes();

  const { data: progress } = useQuery({
    queryKey: ['project-workflow-progress', projectId],
    queryFn: () =>
      getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet({
        path: { project_id: projectId },
        query: { share_token: shareToken },
      }),
    enabled,
    refetchInterval: REFETCH_INTERVAL_MS,
  });

  return useMemo(() => {
    if (!enabled) return EMPTY;

    const openByRun = new Map<string, WorkflowProgressResponse[]>();
    for (const entry of progress ?? []) {
      if (entry.completed_at || !entry.started_at) continue;
      const open = openByRun.get(entry.workflow_run_id);
      if (open) open.push(entry);
      else openByRun.set(entry.workflow_run_id, [entry]);
    }

    const running: RunActivityItem[] = [];
    const queued: RunActivityItem[] = [];

    for (const { run } of workflowDetails) {
      const isRunning = run.status === WorkflowRunStatus.Running;
      const isQueued = run.status === WorkflowRunStatus.Pending;
      if (!isRunning && !isQueued) continue;

      const open = openByRun.get(run.id) ?? [];
      const label = getWorkflowTypeName(run.type);
      // Parallel nodes of the same name batch into one row upstream, so what is
      // left here is genuinely distinct work. A node named after its own
      // assessment would only repeat the line above it.
      const names = Array.from(new Set(open.map((entry) => entry.name))).filter((name) => name !== label);

      (isRunning ? running : queued).push({
        runId: run.id,
        label,
        detail: names.length > 0 ? names.join(' · ') : null,
        currentStep: open.reduce((sum, entry) => sum + (entry.current_step ?? 0), 0),
        totalSteps: open.reduce((sum, entry) => sum + (entry.total_steps ?? 0), 0),
      });
    }

    return { running, queued };
  }, [enabled, progress, workflowDetails, getWorkflowTypeName]);
}
