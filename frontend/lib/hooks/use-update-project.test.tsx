import { QueryObserver } from '@tanstack/react-query';
import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api-error';
import type { Project, ProjectOverview } from '@/lib/generated-api';
import { PROJECT_LIST_QUERY_KEY, projectQueryKeys } from '@/lib/hooks/use-project-data';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { useUpdateProject, type UpdateProjectOptions } from './use-update-project';

const mocks = vi.hoisted(() => ({ patch: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  updateProjectEndpointApiProjectProjectIdPatch: mocks.patch,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const project = (id: string, title: string) => ({ id, title }) as Project;
const overview = (id: string, title: string, revision: number) =>
  ({ project: project(id, title), revision }) as ProjectOverview;

let rendered: Rendered | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
});

/** Project `p` with two revisions' overviews cached, another project's overview, and the project list watched. */
async function mount(projectId: string | null, options: UpdateProjectOptions) {
  const client = testQueryClient();
  client.setQueryData(projectQueryKeys.overview('p', 1), overview('p', 'Old', 1));
  client.setQueryData(projectQueryKeys.overview('p', null), overview('p', 'Old', 2));
  client.setQueryData(projectQueryKeys.overview('q', null), overview('q', 'Other', 1));
  // The refresh stays in flight, so the test sees what the save wrote before it lands.
  const overviewFetch = vi.fn(() => new Promise<ProjectOverview>(() => {}));
  for (const key of [projectQueryKeys.overview('p', 1), projectQueryKeys.overview('p', null)]) {
    new QueryObserver(client, { queryKey: key, queryFn: overviewFetch, staleTime: Infinity }).subscribe(() => {});
  }
  const listFetch = vi.fn().mockResolvedValue([]);
  client.setQueryData([...PROJECT_LIST_QUERY_KEY, ''], []);
  new QueryObserver(client, {
    queryKey: [...PROJECT_LIST_QUERY_KEY, ''],
    queryFn: listFetch,
    staleTime: Infinity,
  }).subscribe(() => {});

  let mutation!: ReturnType<typeof useUpdateProject>;
  function Probe() {
    mutation = useUpdateProject(projectId, options);
    return null;
  }
  rendered = await renderInto(withQueryClient(client, <Probe />));
  return { client, mutation: () => mutation, overviewFetch, listFetch };
}

describe('useUpdateProject', () => {
  it('puts the saved project into every cached overview at once, then refreshes them and the project list', async () => {
    mocks.patch.mockResolvedValue(project('p', 'New'));
    const onSuccess = vi.fn();
    const { client, mutation, overviewFetch, listFetch } = await mount('p', {
      successMessage: 'Saved',
      errorMessage: 'Failed to save',
      onSuccess,
    });

    await act(async () => mutation().mutate({ title: 'New' }));
    await flush();

    expect(mocks.patch).toHaveBeenCalledWith({ path: { project_id: 'p' }, body: { title: 'New' } });
    const titles = [projectQueryKeys.overview('p', 1), projectQueryKeys.overview('p', null)].map(
      (key) => client.getQueryData<ProjectOverview>(key)?.project.title,
    );
    expect(titles).toEqual(['New', 'New']);
    expect(client.getQueryData<ProjectOverview>(projectQueryKeys.overview('p', 1))?.revision).toBe(1);
    expect(client.getQueryData<ProjectOverview>(projectQueryKeys.overview('q', null))?.project.title).toBe('Other');
    expect(overviewFetch).toHaveBeenCalledTimes(2);
    expect(listFetch).toHaveBeenCalledOnce();
    expect(toast.success).toHaveBeenCalledWith('Saved');
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("toasts the server's reason, or the fallback when there is none, and leaves the caches alone", async () => {
    mocks.patch.mockRejectedValueOnce(new ApiError(404, 'Project not found')).mockRejectedValueOnce(new ApiError(502));
    const onError = vi.fn();
    const { client, mutation, listFetch } = await mount('p', { errorMessage: 'Failed to save', onError });

    await act(async () => mutation().mutate({ title: 'New' }));
    await flush();
    await act(async () => mutation().mutate({ title: 'New' }));
    await flush();

    expect(vi.mocked(toast.error).mock.calls).toEqual([['Project not found'], ['Failed to save']]);
    expect(onError).toHaveBeenCalledTimes(2);
    expect(client.getQueryData<ProjectOverview>(projectQueryKeys.overview('p', null))?.project.title).toBe('Old');
    expect(listFetch).not.toHaveBeenCalled();
  });

  it('cancels an overview fetch that left before the save and fetches again, so neither the old project nor the fetch is lost', async () => {
    const client = testQueryClient();
    const key = projectQueryKeys.overview('p', null);
    client.setQueryData(key, overview('p', 'Old', 1));
    // A poll, or the refresh after starting a run, leaves before the save and would answer after it with the old project.
    let answerFirst!: (o: ProjectOverview) => void;
    const overviewFetch = vi
      .fn()
      .mockImplementationOnce(() => new Promise<ProjectOverview>((resolve) => (answerFirst = resolve)))
      .mockResolvedValue({ ...overview('p', 'New', 1), issues_version: 'after' });
    new QueryObserver(client, { queryKey: key, queryFn: overviewFetch, staleTime: Infinity }).subscribe(() => {});
    void client.refetchQueries({ queryKey: key });
    mocks.patch.mockResolvedValue(project('p', 'New'));
    let mutation!: ReturnType<typeof useUpdateProject>;
    function Probe() {
      mutation = useUpdateProject('p', { errorMessage: 'Failed to save' });
      return null;
    }
    rendered = await renderInto(withQueryClient(client, <Probe />));

    await act(async () => mutation.mutate({ title: 'New' }));
    await flush();
    answerFirst(overview('p', 'Old', 1));
    await flush();

    expect(overviewFetch).toHaveBeenCalledTimes(2);
    expect(client.getQueryData<ProjectOverview>(key)).toMatchObject({
      project: { title: 'New' },
      issues_version: 'after',
    });
  });

  it('sends nothing before the project exists', async () => {
    const { mutation } = await mount(null, { errorMessage: 'Failed to save' });

    await act(async () => mutation().mutate({ group_by_severity: false }));
    await flush();

    expect(mocks.patch).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('No project ID');
  });
});
