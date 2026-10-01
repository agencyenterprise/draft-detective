import { describe, expect, it } from 'vitest';
import { type ProjectOverview, WorkflowRunStatus } from '@/lib/generated-api';
import { overviewRefetchInterval } from './use-project-data';

function withRuns(...statuses: WorkflowRunStatus[]) {
  const data = {
    workflow_runs: statuses.map((status) => ({ run: { status }, errors: [] })),
  } as unknown as ProjectOverview;
  return { state: { data } };
}

describe('overviewRefetchInterval', () => {
  it('polls briskly while anything is working', () => {
    expect(overviewRefetchInterval(withRuns(WorkflowRunStatus.Completed, WorkflowRunStatus.Running))).toBe(3000);
    expect(overviewRefetchInterval(withRuns(WorkflowRunStatus.Pending))).toBe(3000);
  });

  it('polls slowly while a run waits on approval', () => {
    expect(overviewRefetchInterval(withRuns(WorkflowRunStatus.AwaitingApproval))).toBe(15000);
  });

  it('stops once nothing is left to change', () => {
    expect(overviewRefetchInterval(withRuns(WorkflowRunStatus.Completed, WorkflowRunStatus.Failed))).toBe(false);
    expect(overviewRefetchInterval({ state: {} })).toBe(false);
  });
});
