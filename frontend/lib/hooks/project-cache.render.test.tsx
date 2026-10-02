import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { projectQueryKeys, useProjectIssues, useWorkflowRunDetail } from '@/lib/hooks/use-project-data';
import { useIssueActions } from '@/lib/hooks/use-issue-actions';
import {
  type Issue,
  type ProjectOverview,
  type WorkflowRunSummary,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ detail: vi.fn(), issues: vi.fn(), resolve: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getWorkflowStateApiWorkflowsWorkflowRunIdGet: mocks.detail,
  getProjectIssuesEndpointApiProjectProjectIdIssuesGet: mocks.issues,
  resolveIssueEndpointApiIssuesIssueIdResolvePost: mocks.resolve,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

describe('run detail', () => {
  it('refetches a running run when its state is written again, to show partial results', async () => {
    const client = testQueryClient();
    const summary = {
      run: {
        id: 'run',
        type: WorkflowRunType.ReferenceValidationV2,
        status: WorkflowRunStatus.Running,
        last_updated_at: '2026-10-01T10:00:00Z',
      },
      errors: [],
    } as unknown as WorkflowRunSummary;
    mocks.detail.mockResolvedValue({ run: summary.run, state: { reference_validations: [] } });
    function Probe({ value }: { value: WorkflowRunSummary }) {
      useWorkflowRunDetail('p', value);
      return null;
    }

    const view = await renderInto(withQueryClient(client, <Probe value={summary} />));
    await flush();
    const written = { ...summary, run: { ...summary.run, last_updated_at: '2026-10-01T10:01:00Z' } };
    await view.rerender(withQueryClient(client, <Probe value={written as unknown as WorkflowRunSummary} />));
    await flush();

    expect(mocks.detail).toHaveBeenCalledTimes(2);
    await view.unmount();
  });
});

describe('issue resolution', () => {
  it('survives an older issues response that lands after it', async () => {
    const client = testQueryClient();
    const issue = { id: 'i', project_id: 'p', resolved_at: null, resolved_by: null, status: 'active' } as Issue;
    const overview = { project: { id: 'p' }, revision: 1, issues_version: 'v1' } as ProjectOverview;
    client.setQueryData([...projectQueryKeys.issues('p', 1), 'v1'], [issue]);
    // The first fetch of the new version hangs, read from before the resolve;
    // the one asked for after the resolve returns the resolved issue.
    let releaseStale!: (value: Issue[]) => void;
    mocks.issues
      .mockImplementationOnce(() => new Promise<Issue[]>((resolve) => (releaseStale = resolve)))
      .mockResolvedValue([{ ...issue, resolved_at: '2026-10-01T10:01:00Z', resolved_by: 'owner' }]);
    mocks.resolve.mockResolvedValue({ ...issue, resolved_at: '2026-10-01T10:01:00Z', resolved_by: 'owner' });
    let resolveIssue!: (id: string) => void;
    let visible: Issue[] | undefined;
    function Probe({ value }: { value: ProjectOverview }) {
      visible = useProjectIssues(value).data;
      resolveIssue = useIssueActions().resolveIssue;
      return null;
    }

    const view = await renderInto(withQueryClient(client, <Probe value={overview} />));
    await view.rerender(withQueryClient(client, <Probe value={{ ...overview, issues_version: 'v2' }} />));
    await flush();
    await act(async () => resolveIssue('i'));
    await flush();
    await act(async () => releaseStale([issue]));
    await flush();

    expect(visible?.[0].resolved_by).toBe('owner');
    await view.unmount();
  });
});
