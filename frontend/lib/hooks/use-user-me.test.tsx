import { describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useUserMe } from '@/lib/hooks/use-user-me';

const mocks = vi.hoisted(() => ({ me: vi.fn(), status: 'loading' as string }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getCurrentUserInfoApiUsersMeGet: mocks.me,
}));
vi.mock('next-auth/react', () => ({ useSession: () => ({ status: mocks.status }) }));

describe('useUserMe', () => {
  it('asks who the user is only once the session is authenticated', async () => {
    mocks.me.mockResolvedValue({ id: 'u-1', role: 'user' });
    let user: ReturnType<typeof useUserMe>['data'];
    function Probe() {
      user = useUserMe().data;
      return null;
    }
    const client = testQueryClient();
    const view = await renderInto(withQueryClient(client, <Probe />));

    for (const status of ['loading', 'unauthenticated']) {
      mocks.status = status;
      await view.rerender(withQueryClient(client, <Probe />));
      await flush();
      expect(mocks.me).not.toHaveBeenCalled();
    }

    mocks.status = 'authenticated';
    await view.rerender(withQueryClient(client, <Probe />));
    await flush();
    expect(mocks.me).toHaveBeenCalledOnce();
    expect(user).toEqual({ id: 'u-1', role: 'user' });
    await view.unmount();
  });
});
