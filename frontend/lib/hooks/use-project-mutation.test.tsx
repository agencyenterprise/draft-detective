import { QueryObserver } from '@tanstack/react-query';
import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api-error';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { useProjectMutation, type ProjectMutationOptions } from './use-project-mutation';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

let rendered: Rendered | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
});

/** Watches the overview of projects `p` and `q`, with a refetch the test releases by hand. */
async function mount(options: ProjectMutationOptions<string, void>) {
  const client = testQueryClient();
  const refetches: Record<string, Array<() => void>> = { p: [], q: [] };
  for (const id of ['p', 'q']) {
    client.setQueryData(projectQueryKeys.overview(id, null), 'cached');
    new QueryObserver(client, {
      queryKey: projectQueryKeys.overview(id, null),
      queryFn: () => new Promise<string>((resolve) => refetches[id].push(() => resolve('fresh'))),
      staleTime: Infinity,
    }).subscribe(() => {});
  }

  let mutation!: ReturnType<typeof useProjectMutation<string, void>>;
  function Probe() {
    mutation = useProjectMutation('p', options);
    return null;
  }
  rendered = await renderInto(withQueryClient(client, <Probe />));
  return { mutation: () => mutation, refetches };
}

describe('useProjectMutation', () => {
  it('says so, runs the caller, and with waitForRefresh stays pending until the project has refetched', async () => {
    const order: string[] = [];
    const { mutation, refetches } = await mount({
      mutationFn: async () => 'done',
      successMessage: 'Started',
      errorMessage: 'Failed',
      waitForRefresh: true,
      onSuccess: () => void order.push('caller'),
    });

    await act(async () => mutation().mutate(undefined, { onSuccess: () => void order.push('mutate') }));
    await flush();

    expect(toast.success).toHaveBeenCalledWith('Started');
    expect(order).toEqual(['caller']);
    expect(mutation().isPending).toBe(true);
    // Only this project's queries refetch.
    expect(refetches.p).toHaveLength(1);
    expect(refetches.q).toHaveLength(0);

    await act(async () => refetches.p[0]());
    await flush();
    expect(mutation().isPending).toBe(false);
    expect(order).toEqual(['caller', 'mutate']);
  });

  it("settles without waiting for the refresh by default, so mutate's own callbacks run at once", async () => {
    const onMutateSuccess = vi.fn();
    const { mutation, refetches } = await mount({ mutationFn: async () => 'done', errorMessage: 'Failed' });

    await act(async () => mutation().mutate(undefined, { onSuccess: onMutateSuccess }));
    await flush();

    // The refresh is still in flight, yet the caller has already heard back.
    expect(refetches.p).toHaveLength(1);
    expect(onMutateSuccess).toHaveBeenCalledOnce();
    expect(mutation().isPending).toBe(false);
  });

  it("toasts the server's reason, or the fallback when there is none, then runs the caller", async () => {
    const onError = vi.fn();
    const failures = [new ApiError(409, 'Already running'), new ApiError(502)];
    const { mutation, refetches } = await mount({
      mutationFn: async () => {
        throw failures.shift();
      },
      errorMessage: 'Failed to start',
      onError,
    });

    await act(async () => mutation().mutate());
    await flush();
    await act(async () => mutation().mutate());
    await flush();

    expect(vi.mocked(toast.error).mock.calls).toEqual([['Already running'], ['Failed to start']]);
    expect(onError).toHaveBeenCalledTimes(2);
    expect(toast.success).not.toHaveBeenCalled();
    expect(refetches.p).toHaveLength(0);
  });
});
