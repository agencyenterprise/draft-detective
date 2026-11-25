import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api-error';
import { downloadFile } from '@/lib/file-download';
import { downloadLogApiAdminLogsDownloadFilenameGet, listLogsApiAdminLogsGet } from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { LogsList } from './logs-list';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  listLogsApiAdminLogsGet: vi.fn(),
  downloadLogApiAdminLogsDownloadFilenameGet: vi.fn(),
}));
vi.mock('@/lib/file-download', () => ({ downloadFile: vi.fn() }));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

let rendered: Rendered;

beforeEach(async () => {
  vi.mocked(listLogsApiAdminLogsGet).mockResolvedValue([
    { filename: 'app.log', size_bytes: 10, modified_at: new Date('2026-11-25T10:00:00Z') },
    { filename: 'app.log.2026-11-24', size_bytes: 20, modified_at: new Date('2026-11-24T10:00:00Z') },
  ]);
  rendered = await renderInto(withQueryClient(testQueryClient(), <LogsList />));
  await flush();
});
afterEach(async () => {
  await rendered.unmount();
  vi.clearAllMocks();
});

/** The download button in the row of `filename`. */
function downloadButton(filename: string): HTMLButtonElement {
  const row = [...rendered.container.querySelectorAll('tr')].find((r) => r.textContent?.includes(filename));
  const button = row?.querySelector('button');
  if (!button) throw new Error(`no download button for ${filename}`);
  return button;
}

describe('LogsList download', () => {
  it('saves the log file that was clicked, under its own name', async () => {
    vi.mocked(downloadLogApiAdminLogsDownloadFilenameGet).mockResolvedValue('line one\n');

    await act(async () => downloadButton('app.log.2026-11-24').click());
    await flush();

    expect(downloadLogApiAdminLogsDownloadFilenameGet).toHaveBeenCalledWith({
      path: { filename: 'app.log.2026-11-24' },
    });
    const [{ filename, blob }] = vi.mocked(downloadFile).mock.calls[0];
    expect(filename).toBe('app.log.2026-11-24');
    expect(await blob.text()).toBe('line one\n');
  });

  it('disables only the row being downloaded, until it finishes', async () => {
    let finish!: (content: string) => void;
    vi.mocked(downloadLogApiAdminLogsDownloadFilenameGet).mockReturnValue(
      new Promise((resolve) => (finish = resolve)) as ReturnType<typeof downloadLogApiAdminLogsDownloadFilenameGet>,
    );

    await act(async () => downloadButton('app.log').click());
    await flush();
    expect(downloadButton('app.log').disabled).toBe(true);
    expect(downloadButton('app.log.2026-11-24').disabled).toBe(false);

    await act(async () => finish('done'));
    await flush();
    expect(downloadButton('app.log').disabled).toBe(false);
  });

  it("shows the server's reason when the download is refused", async () => {
    vi.mocked(downloadLogApiAdminLogsDownloadFilenameGet).mockRejectedValue(new ApiError(404, 'Log file not found'));

    await act(async () => downloadButton('app.log').click());
    await flush();

    expect(downloadFile).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Log file not found');
    expect(downloadButton('app.log').disabled).toBe(false);
  });
});
