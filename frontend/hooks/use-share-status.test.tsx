import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import type { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-error';
import type { ProjectOverview, ShareStatusResponse } from '@/lib/generated-api';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { flush, type Rendered, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useShareStatus } from './use-share-status';

const mocks = vi.hoisted(() => ({ enable: vi.fn(), disable: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  enableProjectSharingApiProjectsProjectIdShareEnablePost: mocks.enable,
  disableProjectSharingApiProjectsProjectIdShareDisablePost: mocks.disable,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const ENABLED: ShareStatusResponse = {
  enabled: true,
  share_link: { token: 'tok-1', url: 'https://example.test/s/tok-1', is_active: true },
};
const DISABLED: ShareStatusResponse = { enabled: false, share_link: null };

const overviewOf = (projectId: string, shareStatus?: ShareStatusResponse | null) =>
  ({ project: { id: projectId }, share_status: shareStatus }) as ProjectOverview;

const mounted: Rendered[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.enable.mockResolvedValue(ENABLED);
  mocks.disable.mockResolvedValue(DISABLED);
});

afterEach(async () => {
  // One at a time: overlapping act() scopes leave React's queue unflushed for the next test.
  for (const view of mounted.splice(0)) await view.unmount();
});

/** Mounts the hook for project p-1, with its latest and revision-1 overviews and another project's in the cache. */
async function mountShare(shareStatus: ShareStatusResponse | null = null) {
  const client = testQueryClient();
  client.setQueryData(projectQueryKeys.overview('p-1', null), overviewOf('p-1', shareStatus));
  client.setQueryData(projectQueryKeys.overview('p-1', 1), overviewOf('p-1', shareStatus));
  client.setQueryData(projectQueryKeys.overview('p-2', null), overviewOf('p-2', shareStatus));
  let share!: ReturnType<typeof useShareStatus>;
  function Probe() {
    share = useShareStatus(overviewOf('p-1', shareStatus));
    return null;
  }
  mounted.push(await renderInto(withQueryClient(client, <Probe />)));
  return { client, share: () => share };
}

const cachedStatus = (client: QueryClient, projectId: string, revision: number | null) =>
  client.getQueryData<ProjectOverview>(projectQueryKeys.overview(projectId, revision))?.share_status;

describe('useShareStatus', () => {
  it('reads the share status from the overview, treating a missing one as not shared', async () => {
    expect((await mountShare(null)).share().isEnabled).toBe(false);
    const { share } = await mountShare(ENABLED);
    expect(share().isEnabled).toBe(true);
    expect(share().shareStatus?.share_link?.token).toBe('tok-1');
  });

  it('enables sharing into every cached overview of the project, and resolves with the link for the download', async () => {
    const { client, share } = await mountShare();

    let resolved: ShareStatusResponse | undefined;
    await act(async () => {
      resolved = await share().enable();
    });

    expect(mocks.enable).toHaveBeenCalledWith({ path: { project_id: 'p-1' } });
    expect(resolved).toEqual(ENABLED);
    expect(cachedStatus(client, 'p-1', null)).toEqual(ENABLED);
    expect(cachedStatus(client, 'p-1', 1)).toEqual(ENABLED);
    expect(cachedStatus(client, 'p-2', null)).toBeNull();
  });

  it('disables sharing in every cached overview of the project and closes the dialog', async () => {
    const { client, share } = await mountShare(ENABLED);
    await act(async () => share().setIsDialogOpen(true));

    await act(async () => share().disable());
    await flush();

    expect(mocks.disable).toHaveBeenCalledWith({ path: { project_id: 'p-1' } });
    expect(cachedStatus(client, 'p-1', null)).toEqual(DISABLED);
    expect(cachedStatus(client, 'p-1', 1)).toEqual(DISABLED);
    expect(cachedStatus(client, 'p-2', null)).toEqual(ENABLED);
    expect(share().isDialogOpen).toBe(false);
    expect(toast.success).toHaveBeenCalled();
  });

  it("closes the dialog on a failed enable, shows the server's reason and rejects for the download", async () => {
    mocks.enable.mockRejectedValue(new ApiError(403, 'Sharing is turned off for this deployment'));
    const { client, share } = await mountShare();
    await act(async () => share().setIsDialogOpen(true));

    let rejection: unknown;
    await act(async () => {
      await share()
        .enable()
        .catch((error: unknown) => {
          rejection = error;
        });
    });

    expect(rejection).toBeInstanceOf(ApiError);
    expect(toast.error).toHaveBeenCalledWith('Sharing is turned off for this deployment');
    expect(share().isDialogOpen).toBe(false);
    expect(cachedStatus(client, 'p-1', null)).toBeNull();
  });

  it('keeps the dialog open and the link live on a failed disable', async () => {
    mocks.disable.mockRejectedValue(new ApiError(500));
    const { client, share } = await mountShare(ENABLED);
    await act(async () => share().setIsDialogOpen(true));

    await act(async () => share().disable());
    await flush();

    expect(toast.error).toHaveBeenCalledWith('Failed to disable sharing');
    expect(share().isDialogOpen).toBe(true);
    expect(cachedStatus(client, 'p-1', null)).toEqual(ENABLED);
  });
});
