import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-error';
import { USER_ME_QUERY_KEY } from '@/lib/hooks/use-user-me';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { ApiKeySettings } from './api-key-settings';

const mocks = vi.hoisted(() => ({ save: vi.fn(), remove: vi.fn() }));
// No session, so the user query never fetches and the card shows the user seeded below.
vi.mock('next-auth/react', () => ({ useSession: () => ({ status: 'unauthenticated', data: null }) }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  setApiKeyApiUsersMeApiKeyPut: mocks.save,
  removeApiKeyApiUsersMeApiKeyDelete: mocks.remove,
}));

beforeEach(() => {
  vi.resetAllMocks();
  mocks.save.mockResolvedValue({});
  mocks.remove.mockResolvedValue({});
});

let view: Rendered | undefined;
afterEach(async () => {
  await view?.unmount();
  view = undefined;
});

/** The settings card, for a user who has (or hasn't) saved a key. */
async function mountSettings(hasKey: boolean) {
  const client: QueryClient = testQueryClient();
  client.setQueryData(USER_ME_QUERY_KEY, { has_openai_api_key: hasKey });
  view = await renderInto(withQueryClient(client, <ApiKeySettings />));

  const container = view.container;
  const input = () => container.querySelector<HTMLInputElement>('input[type="password"]')!;
  const button = (label: string) =>
    [...container.querySelectorAll('button')].find((b) => b.textContent?.includes(label));
  return {
    input,
    button,
    text: () => container.textContent ?? '',
    userRefetchRequested: () => client.getQueryState(USER_ME_QUERY_KEY)?.isInvalidated ?? false,
    async type(value: string) {
      const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
      await act(async () => {
        setValue.call(input(), value);
        input().dispatchEvent(new Event('input', { bubbles: true }));
      });
    },
    async submit() {
      await act(async () => container.querySelector('form')!.requestSubmit());
      await flush();
    },
    async click(label: string) {
      await act(async () => button(label)!.click());
      await flush();
    },
  };
}

describe('ApiKeySettings', () => {
  it('saves the trimmed key, then refetches the user and clears the field', async () => {
    const card = await mountSettings(false);

    await card.type(' sk-test-123 ');
    await card.submit();

    expect(mocks.save).toHaveBeenCalledWith({ body: { openai_api_key: 'sk-test-123' } });
    expect(card.userRefetchRequested()).toBe(true);
    expect(card.input().value).toBe('');
  });

  it('offers to replace and remove a saved key, and removing it refetches the user', async () => {
    const card = await mountSettings(true);
    expect(card.button('Replace key')).toBeDefined();

    await card.click('Remove key');

    expect(mocks.remove).toHaveBeenCalledOnce();
    expect(card.userRefetchRequested()).toBe(true);
  });

  it("shows the server's reason for rejecting the key and keeps the key for a retry", async () => {
    mocks.save.mockRejectedValueOnce(new ApiError(422, 'Incorrect API key provided'));
    const card = await mountSettings(false);

    await card.type('sk-wrong');
    await card.submit();

    expect(card.text()).toContain('Incorrect API key provided');
    expect(card.input().value).toBe('sk-wrong');
    expect(card.userRefetchRequested()).toBe(false);
  });

  it.each([
    ['an API error with no reason', new ApiError(502)],
    ['an API error with a blank reason', new ApiError(422, '')],
    ['a network failure', new TypeError('Failed to fetch')],
  ])('falls back to a generic message on %s', async (_case, error) => {
    mocks.save.mockRejectedValueOnce(error);
    const card = await mountSettings(false);

    await card.type('sk-test-123');
    await card.submit();

    expect(card.text()).toContain('Failed to save API key');
    expect(card.text()).not.toContain('HTTP 502');
  });

  it('holds the remove button while a key is being saved, and the form while the key is being removed', async () => {
    mocks.save.mockReturnValueOnce(new Promise(() => {}));
    mocks.remove.mockReturnValueOnce(new Promise(() => {}));
    const saving = await mountSettings(true);
    await saving.type('sk-new');
    await saving.submit();
    expect(saving.button('Remove key')!.disabled).toBe(true);
    await view!.unmount();

    const removing = await mountSettings(true);
    await removing.click('Remove key');
    expect(removing.input().disabled).toBe(true);
    expect(removing.button('Replace key')!.disabled).toBe(true);
  });

  it('says so when removing the key fails', async () => {
    mocks.remove.mockRejectedValueOnce(new ApiError(500));
    const card = await mountSettings(true);

    await card.click('Remove key');

    expect(card.text()).toContain('Failed to remove API key');
    expect(card.userRefetchRequested()).toBe(false);
  });
});
