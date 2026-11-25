import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api-error';
import { downloadFile } from '@/lib/file-download';
import {
  exportAdminFeedbacksCsvApiAdminFeedbacksExportGet,
  getAdminFeedbacksApiAdminFeedbacksGet,
  getWorkflowTypesApiWorkflowTypesGet,
} from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { FeedbacksList } from './feedbacks-list';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getAdminFeedbacksApiAdminFeedbacksGet: vi.fn(),
  exportAdminFeedbacksCsvApiAdminFeedbacksExportGet: vi.fn(),
  getWorkflowTypesApiWorkflowTypesGet: vi.fn(),
}));
vi.mock('@/lib/file-download', () => ({ downloadFile: vi.fn() }));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

let rendered: Rendered;

beforeEach(async () => {
  vi.mocked(getAdminFeedbacksApiAdminFeedbacksGet).mockResolvedValue([]);
  vi.mocked(getWorkflowTypesApiWorkflowTypesGet).mockResolvedValue({ workflow_types: [], categories: [], presets: [] });
  rendered = await renderInto(withQueryClient(testQueryClient(), <FeedbacksList />));
  await flush();
});
afterEach(async () => {
  await rendered.unmount();
  vi.clearAllMocks();
});

async function exportCsv(): Promise<void> {
  const button = [...rendered.container.querySelectorAll('button')].find((b) =>
    b.textContent?.includes('Export to CSV'),
  );
  if (!button) throw new Error('no "Export to CSV" button');
  await act(async () => button.click());
  await flush();
}

describe('FeedbacksList export', () => {
  it('saves the CSV the server sends', async () => {
    vi.mocked(exportAdminFeedbacksCsvApiAdminFeedbacksExportGet).mockResolvedValue('id,rating\n1,up\n');

    await exportCsv();

    const [{ filename, blob }] = vi.mocked(downloadFile).mock.calls[0];
    expect(filename).toBe('feedbacks.csv');
    expect(await blob.text()).toBe('id,rating\n1,up\n');
  });

  it('tells the admin when the export fails', async () => {
    vi.mocked(exportAdminFeedbacksCsvApiAdminFeedbacksExportGet).mockRejectedValue(new ApiError(502));

    await exportCsv();

    expect(downloadFile).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Failed to export feedback');
  });
});
