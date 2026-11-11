import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-error';
import { USER_ME_QUERY_KEY } from '@/lib/hooks/use-user-me';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { StepApiKeyConfig } from './step-api-key-config';

const mocks = vi.hoisted(() => ({ save: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  setApiKeyApiUsersMeApiKeyPut: mocks.save,
}));

/** A promise the test settles by hand, to look at the step while the key is being saved. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.save.mockResolvedValue({});
});

let view: Rendered | undefined;
afterEach(async () => {
  await view?.unmount();
  view = undefined;
});

/** The step, with the signed-in user already loaded as the page loads it before showing the step. */
async function mountStep() {
  const client: QueryClient = testQueryClient();
  client.setQueryData(USER_ME_QUERY_KEY, { has_openai_api_key: false });
  view = await renderInto(withQueryClient(client, <StepApiKeyConfig />));

  const container = view.container;
  const input = () => container.querySelector<HTMLInputElement>('#api-key-input')!;
  const save = () => container.querySelector<HTMLButtonElement>('button[type="submit"]')!;
  return {
    input,
    save,
    message: () => container.querySelector('form')!.textContent ?? '',
    userRefetchRequested: () => client.getQueryState(USER_ME_QUERY_KEY)?.isInvalidated ?? false,
    async type(value: string) {
      // React tracks the input's value; set it through the native setter so the change event registers.
      const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
      await act(async () => {
        setValue.call(input(), value);
        input().dispatchEvent(new Event('input', { bubbles: true }));
      });
    },
    // Submitting the form is what both the button and Enter in the field do.
    async submit() {
      await act(async () => container.querySelector('form')!.requestSubmit());
      await flush();
    },
  };
}

describe('StepApiKeyConfig', () => {
  it('saves the key without surrounding whitespace, then refetches the user and clears the field', async () => {
    const step = await mountStep();

    await step.type('  sk-test-123 \n');
    await step.submit();

    expect(mocks.save).toHaveBeenCalledOnce();
    expect(mocks.save).toHaveBeenCalledWith({ body: { openai_api_key: 'sk-test-123' } });
    // The page leaves this step once the refetched user has a key.
    expect(step.userRefetchRequested()).toBe(true);
    expect(step.input().value).toBe('');
  });

  it('sends nothing for a blank key', async () => {
    const step = await mountStep();
    expect(step.save().disabled).toBe(true);

    await step.type('   ');
    expect(step.save().disabled).toBe(true);
    await step.submit();

    expect(mocks.save).not.toHaveBeenCalled();
  });

  it('holds the field and the button while the key is being saved', async () => {
    const pending = deferred<object>();
    mocks.save.mockReturnValue(pending.promise);
    const step = await mountStep();

    await step.type('sk-test-123');
    await step.submit();
    expect(step.input().disabled).toBe(true);
    expect(step.save().disabled).toBe(true);
    expect(step.userRefetchRequested()).toBe(false);

    await act(async () => pending.resolve({}));
    await flush();
    expect(step.input().disabled).toBe(false);
    expect(step.userRefetchRequested()).toBe(true);
  });

  it("shows the server's reason for rejecting the key, keeps the key for a retry, and clears the reason on edit", async () => {
    mocks.save.mockRejectedValueOnce(new ApiError(422, 'Incorrect API key provided'));
    const step = await mountStep();

    await step.type('sk-wrong');
    await step.submit();

    expect(step.message()).toContain('Incorrect API key provided');
    expect(step.userRefetchRequested()).toBe(false);
    expect(step.input().value).toBe('sk-wrong');
    expect(step.save().disabled).toBe(false);

    await step.type('sk-right');
    expect(step.message()).not.toContain('Incorrect API key provided');

    await step.submit();
    expect(mocks.save).toHaveBeenLastCalledWith({ body: { openai_api_key: 'sk-right' } });
    expect(step.userRefetchRequested()).toBe(true);
  });

  it.each([
    ['an API error with no reason', new ApiError(502)],
    ['a network failure', new TypeError('Failed to fetch')],
  ])('falls back to a generic message on %s', async (_case, error) => {
    mocks.save.mockRejectedValueOnce(error);
    const step = await mountStep();

    await step.type('sk-test-123');
    await step.submit();

    expect(step.message()).toContain('Failed to save API key');
    expect(step.message()).not.toContain('HTTP 502');
  });
});
