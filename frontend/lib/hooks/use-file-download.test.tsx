import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api-error';
import { renderInto, type Rendered } from '@/lib/test-render';
import { type FileDownloadMessages, useFileDownload } from './use-file-download';

vi.mock('sonner', () => ({ toast: { loading: vi.fn(() => 't1'), success: vi.fn(), error: vi.fn() } }));

const messages: FileDownloadMessages = {
  loading: 'Preparing...',
  description: 'This may take a few moments',
  success: 'Downloaded',
  error: 'Failed to download',
};

let rendered: Rendered | undefined;
let hook!: ReturnType<typeof useFileDownload>;
beforeEach(async () => {
  vi.clearAllMocks();
  function Probe() {
    hook = useFileDownload();
    return null;
  }
  rendered = await renderInto(<Probe />);
});
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
});

async function run(save: () => Promise<void>) {
  await act(async () => hook.download(save, messages));
}

describe('useFileDownload', () => {
  it('is downloading while the save runs, and replaces the loading toast with the success one', async () => {
    let finish!: () => void;
    let pending!: Promise<void>;
    act(() => {
      pending = hook.download(() => new Promise<void>((resolve) => (finish = resolve)), messages);
    });
    expect(hook.isDownloading).toBe(true);
    expect(toast.loading).toHaveBeenCalledWith('Preparing...', { description: 'This may take a few moments' });

    await act(async () => {
      finish();
      await pending;
    });
    expect(hook.isDownloading).toBe(false);
    expect(toast.success).toHaveBeenCalledWith('Downloaded', { id: 't1', description: null });
  });

  it("shows the server's reason when the download fails", async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await run(() => Promise.reject(new ApiError(404, 'Project not found')));

    expect(toast.error).toHaveBeenCalledWith('Project not found', { id: 't1', description: null });
    expect(hook.isDownloading).toBe(false);
  });

  it('falls back to the given message when the server gives no reason', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await run(() => Promise.reject(new ApiError(502)));
    await run(() => Promise.reject(new TypeError('Failed to fetch')));

    expect(vi.mocked(toast.error).mock.calls.map(([text]) => text)).toEqual([
      'Failed to download',
      'Failed to download',
    ]);
  });
});
