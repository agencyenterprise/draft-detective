import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { QueryObserver } from '@tanstack/react-query';
import { toast } from 'sonner';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useIssueActions } from '@/lib/hooks/use-issue-actions';
import type { Issue } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ issues: vi.fn(), resolve: vi.fn(), unresolve: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getProjectIssuesEndpointApiProjectProjectIdIssuesGet: mocks.issues,
  resolveIssueEndpointApiIssuesIssueIdResolvePost: mocks.resolve,
  unresolveIssueEndpointApiIssuesIssueIdUnresolvePost: mocks.unresolve,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

const RESOLVED_AT = '2026-10-01T10:00:00Z';

function issue(id: string, projectId = 'p', resolved = false): Issue {
  return {
    id,
    project_id: projectId,
    resolved_at: resolved ? RESOLVED_AT : null,
    resolved_by: resolved ? 'owner' : null,
    status: resolved ? 'resolved' : 'active',
  } as unknown as Issue;
}

async function mountActions() {
  const client = testQueryClient();
  let actions!: ReturnType<typeof useIssueActions>;
  function Probe() {
    actions = useIssueActions();
    return null;
  }
  const view = await renderInto(withQueryClient(client, <Probe />));
  return { client, view, actions: () => actions };
}

describe('useIssueActions', () => {
  it('writes a resolution into every cached issue list of the project, without refetching', async () => {
    const { client, view, actions } = await mountActions();
    // Wire the lists to the issues endpoint, so a refetch would show up as a call.
    client.setQueryDefaults(projectQueryKeys.allIssues('p'), { queryFn: () => mocks.issues() });
    const rev1 = [...projectQueryKeys.issues('p', 1), 'v1'];
    const rev2 = [...projectQueryKeys.issues('p', 2), 'v1'];
    const otherProject = [...projectQueryKeys.issues('q', 1), 'v1'];
    client.setQueryData(rev1, [issue('a'), issue('b')]);
    client.setQueryData(rev2, [issue('a')]);
    client.setQueryData(otherProject, [issue('a', 'q')]);
    // One list is on screen, as the results page keeps it: only a watched list refetches on invalidation.
    const watching = new QueryObserver(client, { queryKey: rev1, staleTime: Infinity }).subscribe(() => {});
    mocks.resolve.mockResolvedValue({ ...issue('a', 'p', true) });

    await act(async () => actions().resolveIssue('a'));
    await flush();

    expect(mocks.resolve).toHaveBeenCalledWith({ path: { issue_id: 'a' } });
    expect(client.getQueryData<Issue[]>(rev1)).toEqual([issue('a', 'p', true), issue('b')]);
    expect(client.getQueryData<Issue[]>(rev2)).toEqual([issue('a', 'p', true)]);
    expect(client.getQueryData<Issue[]>(otherProject)).toEqual([issue('a', 'q')]);
    expect(mocks.issues).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledOnce();
    watching();
    await view.unmount();
  });

  it('asks again for a list that was in flight, so its stale answer never lands', async () => {
    const { client, view, actions } = await mountActions();
    const key = [...projectQueryKeys.issues('p', 1), 'v1'];
    client.setQueryData(key, [issue('a')]);
    let stale!: (value: Issue[]) => void;
    mocks.issues
      .mockImplementationOnce(() => new Promise<Issue[]>((resolve) => (stale = resolve)))
      .mockResolvedValueOnce([issue('a', 'p', true)]);
    void client.fetchQuery({ queryKey: key, queryFn: () => mocks.issues() }).catch(() => undefined);
    mocks.resolve.mockResolvedValue(issue('a', 'p', true));

    await act(async () => actions().resolveIssue('a'));
    await act(async () => stale([issue('a')]));
    await flush();

    expect(mocks.issues).toHaveBeenCalledTimes(2);
    expect(client.getQueryData<Issue[]>(key)).toEqual([issue('a', 'p', true)]);
    await view.unmount();
  });

  it('clears the resolution when an issue is unresolved', async () => {
    const { client, view, actions } = await mountActions();
    const key = [...projectQueryKeys.issues('p', 1), 'v1'];
    client.setQueryData(key, [issue('a', 'p', true)]);
    mocks.unresolve.mockResolvedValue(issue('a'));

    await act(async () => actions().unresolveIssue('a'));
    await flush();

    expect(mocks.unresolve).toHaveBeenCalledWith({ path: { issue_id: 'a' } });
    expect(client.getQueryData<Issue[]>(key)).toEqual([issue('a')]);
    await view.unmount();
  });

  it('leaves the cache alone and reports the error when the request fails', async () => {
    const { client, view, actions } = await mountActions();
    const key = [...projectQueryKeys.issues('p', 1), 'v1'];
    client.setQueryData(key, [issue('a')]);
    mocks.resolve.mockRejectedValue(new Error('Issue not found'));

    await act(async () => actions().resolveIssue('a'));
    await flush();

    expect(client.getQueryData<Issue[]>(key)).toEqual([issue('a')]);
    expect(toast.error).toHaveBeenCalledWith('Issue not found');
    expect(toast.success).not.toHaveBeenCalled();
    await view.unmount();
  });

  it('reports a pending resolve until the request settles', async () => {
    const { view, actions } = await mountActions();
    let settle!: (value: Issue) => void;
    mocks.resolve.mockImplementation(() => new Promise<Issue>((resolve) => (settle = resolve)));

    await act(async () => actions().resolveIssue('a'));
    await flush();
    expect(actions().isResolving).toBe(true);
    expect(actions().isUnresolving).toBe(false);

    await act(async () => settle(issue('a', 'p', true)));
    await flush();
    expect(actions().isResolving).toBe(false);
    await view.unmount();
  });
});
