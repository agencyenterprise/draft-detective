import { ProjectListItem, WorkflowRunStatus } from '@/lib/generated-api';

/**
 * What a project is doing, read off its runs.
 *
 * The list endpoint returns runs rather than run details, so this cannot reuse
 * the helpers in `lib/workflow-state` — those want the detailed shape. The
 * questions are simpler here anyway: is it working, is it stuck on me, did
 * something break.
 */
export type ProjectState = 'waiting' | 'running' | 'failed' | 'done' | 'empty';

const ACTIVE: WorkflowRunStatus[] = [WorkflowRunStatus.Pending, WorkflowRunStatus.Running];

export function readProjectState(item: ProjectListItem): ProjectState {
  const runs = item.workflow_runs ?? [];
  if (runs.length === 0) return 'empty';

  if (runs.some((run) => ACTIVE.includes(run.status))) return 'running';
  // Only once nothing is running does a run awaiting approval define the
  // project: the reader is the one who can move it along.
  if (runs.some((run) => run.status === WorkflowRunStatus.AwaitingApproval)) return 'waiting';
  if (runs.some((run) => run.status === WorkflowRunStatus.Failed)) return 'failed';
  // Ready to read has to mean something finished. A project whose runs were all
  // cancelled has produced nothing, and calling it ready would send the reader
  // to an empty document explorer.
  if (runs.some((run) => run.status === WorkflowRunStatus.Completed)) return 'done';
  return 'empty';
}

export const PROJECT_STATE: Record<ProjectState, { label: string; dot: string; text: string }> = {
  waiting: {
    label: 'Waiting on you',
    dot: 'bg-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
  },
  running: {
    label: 'Running',
    dot: 'bg-primary',
    text: 'text-primary',
  },
  failed: {
    label: 'Something failed',
    dot: 'bg-red-500',
    text: 'text-red-700 dark:text-red-400',
  },
  done: {
    label: 'Ready to read',
    dot: 'bg-green-500',
    text: 'text-green-700 dark:text-green-400',
  },
  empty: {
    label: 'Nothing run yet',
    dot: 'bg-muted-foreground/40',
    text: 'text-muted-foreground',
  },
};
