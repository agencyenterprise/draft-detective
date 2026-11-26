import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';

const mocks = vi.hoisted(() => ({
  createRevision: vi.fn(),
  startWorkflows: vi.fn(),
  upload: vi.fn(),
}));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  createRevisionEndpointApiProjectProjectIdRevisionsPost: mocks.createRevision,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost: mocks.startWorkflows,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), loading: vi.fn() } }));

let view: Rendered;

beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  mocks.createRevision.mockResolvedValue({ previous_workflow_types: [] });
  mocks.startWorkflows.mockResolvedValue({});
  mocks.upload.mockResolvedValue(undefined);
});

afterEach(async () => {
  await view.unmount();
});

/**
 * Renders a fresh copy of the dialog and submits a file. The dialog loads the upload client with
 * import(); when `uploadModuleLoads` is false, a throwing factory stands in for a chunk that fails to load.
 */
async function submitFile(uploadModuleLoads: boolean) {
  vi.doMock('@/lib/hooks/upload/upload-single', () => {
    if (!uploadModuleLoads) throw new Error('Failed to load chunk');
    return { uploadSingleFile: mocks.upload };
  });
  const { ReplaceMainDocumentDialog } = await import('./replace-main-document-dialog');
  view = await renderInto(
    withQueryClient(testQueryClient(), <ReplaceMainDocumentDialog isOpen projectId="p-1" onClose={() => undefined} />),
  );
  const input = document.body.querySelector<HTMLInputElement>('input[type="file"]')!;
  const file = new File(['# New draft'], 'draft.md', { type: 'text/markdown' });
  await act(async () => {
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  const submit = Array.from(document.body.querySelectorAll('button')).find((b) =>
    /create|replace|upload/i.test(b.textContent ?? ''),
  )!;
  await act(async () => submit.click());
  await flush();
  await flush();
}

describe('ReplaceMainDocumentDialog', () => {
  it('creates the revision, then uploads the file to it', async () => {
    await submitFile(true);

    expect(mocks.createRevision).toHaveBeenCalledWith({ path: { project_id: 'p-1' } });
    expect(mocks.upload).toHaveBeenCalledWith(expect.objectContaining({ name: 'draft.md' }), expect.anything());
    expect(mocks.createRevision.mock.invocationCallOrder[0]).toBeLessThan(mocks.upload.mock.invocationCallOrder[0]);
  });

  it('leaves the project unchanged when the upload client fails to load', async () => {
    await submitFile(false);

    expect(mocks.createRevision).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });
});
