import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api-error';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { useToastMutation, type ToastMutationOptions } from './use-toast-mutation';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

let rendered: Rendered | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
});

async function mount(options: ToastMutationOptions<string, void>) {
  let mutation!: ReturnType<typeof useToastMutation<string, void>>;
  function Probe() {
    mutation = useToastMutation(options);
    return null;
  }
  rendered = await renderInto(withQueryClient(testQueryClient(), <Probe />));
  return async () => {
    await act(async () => mutation.mutate());
    await flush();
  };
}

describe('useToastMutation', () => {
  it('toasts the success message, then runs the caller with the result', async () => {
    const onSuccess = vi.fn(() => expect(toast.success).toHaveBeenCalledWith('Saved'));
    const run = await mount({
      mutationFn: async () => 'done',
      successMessage: 'Saved',
      errorMessage: 'Failed',
      onSuccess,
    });

    await run();

    expect(onSuccess).toHaveBeenCalledWith('done', undefined, undefined, expect.anything());
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('toasts nothing on success without a success message', async () => {
    const run = await mount({ mutationFn: async () => 'done', errorMessage: 'Failed' });

    await run();

    expect(toast.success).not.toHaveBeenCalled();
  });

  it("toasts the server's reason on failure, then runs the caller", async () => {
    const failure = new ApiError(409, 'Project is busy');
    const onError = vi.fn();
    const run = await mount({ mutationFn: () => Promise.reject(failure), errorMessage: 'Failed', onError });

    await run();

    expect(toast.error).toHaveBeenCalledWith('Project is busy');
    expect(onError).toHaveBeenCalledWith(failure, undefined, undefined, expect.anything());
  });

  it('toasts the error message when the server gives no reason', async () => {
    const run = await mount({ mutationFn: () => Promise.reject(new ApiError(500)), errorMessage: 'Failed to save' });

    await run();

    expect(toast.error).toHaveBeenCalledWith('Failed to save');
  });
});
