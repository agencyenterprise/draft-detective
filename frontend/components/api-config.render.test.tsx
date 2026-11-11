import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// `lib/api` reads the env when it loads, so point it at a non-default host before any import.
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_API_URL = 'http://api.test:8087';
});

import { useLayoutEffect } from 'react';
import { ApiConfig } from '@/components/api-config';
import { ApiError } from '@/lib/api-error';
import { listThreadsApiChatThreadsGet } from '@/lib/generated-api';
import { flush, renderInto, type Rendered } from '@/lib/test-render';

const auth = vi.hoisted(() => ({ accessToken: 'first-token' }));

vi.mock('next-auth/react', () => ({
  useSession: () => ({
    status: 'authenticated',
    data: { accessToken: auth.accessToken, expires: '2999-01-01T00:00:00.000Z', user: {} },
    update: async () => null,
  }),
}));

/** Fetches the moment it mounts, before any passive effect in the tree has run. */
function EarlyFetcher() {
  useLayoutEffect(() => {
    void listThreadsApiChatThreadsGet().catch(() => undefined);
  }, []);
  return null;
}

function app(accessToken: string) {
  auth.accessToken = accessToken;
  return (
    <>
      <ApiConfig />
      <EarlyFetcher />
    </>
  );
}

describe('ApiConfig', () => {
  let fetchMock: ReturnType<typeof vi.fn<(input: Request) => Promise<Response>>>;
  let rendered: Rendered | undefined;

  beforeEach(() => {
    fetchMock = vi.fn(async () => Response.json([]));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(async () => {
    await rendered?.unmount();
    rendered = undefined;
    vi.unstubAllGlobals();
  });

  it('sends a fetch made on first mount to the configured host with the session token', async () => {
    rendered = await renderInto(app('first-token'));
    await flush();

    const request = fetchMock.mock.calls[0][0];
    expect(request.url).toBe('http://api.test:8087/api/chat/threads');
    expect(request.headers.get('Authorization')).toBe('Bearer first-token');
  });

  it('uses the refreshed token once the session changes', async () => {
    rendered = await renderInto(app('first-token'));
    await rendered.rerender(app('second-token'));
    fetchMock.mockClear();

    await listThreadsApiChatThreadsGet();

    expect(fetchMock.mock.calls[0][0].headers.get('Authorization')).toBe('Bearer second-token');
  });

  it('turns a failed response into an ApiError from the first request on', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Not found' }, { status: 404 }));

    const error = await listThreadsApiChatThreadsGet().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404 });
  });
});
