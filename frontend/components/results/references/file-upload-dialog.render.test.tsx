import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api-error';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost, WorkflowRunType } from '@/lib/generated-api';
import { QueryObserver, type QueryClient } from '@tanstack/react-query';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { heldUpload, resetFakeTus } from '@/lib/hooks/upload/fake-tus';

vi.mock('@uppy/tus', async () => ({ default: (await import('@/lib/hooks/upload/fake-tus')).FakeTus }));
vi.mock('@/lib/api', () => ({ baseUrl: 'http://api.test', getAuthHeader: async () => 'Bearer token-1' }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  startMultipleWorkflowsApiWorkflowsStartMultiplePost: vi.fn(),
}));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const onCancel = vi.fn();
const onComplete = vi.fn();
let rendered: Rendered | undefined;

function button(name: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === name);
}

async function click(name: string): Promise<void> {
  const target = button(name);
  if (!target) throw new Error(`no "${name}" button in: ${document.body.textContent}`);
  await act(async () => target.click());
  await flush();
}

/** Picks files through the dialog's file input, as the native picker would. */
async function pick(files: File[]): Promise<void> {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, 'files', { value: files, configurable: true });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  await flush();
}

async function pressEscape(): Promise<void> {
  await act(async () =>
    document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })),
  );
  await flush();
}

async function renderDialog(referenceId: string | undefined, client: QueryClient = testQueryClient()): Promise<void> {
  await rendered?.unmount();
  rendered = await renderInto(
    withQueryClient(
      client,
      <FileUploadDialog
        isOpen
        projectId="project-1"
        referenceId={referenceId}
        title="Add files"
        description="Add source documents."
        multiple
        onCancel={onCancel}
        onComplete={onComplete}
      />,
    ),
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  resetFakeTus();
  await renderDialog('ref-1');
});

afterEach(async () => {
  await rendered?.unmount();
});

describe('FileUploadDialog', () => {
  it('can be closed after every file failed', async () => {
    // The picker's accept filter doesn't stop a dragged-in file; Uppy refuses it on upload.
    await pick([new File(['x'], 'tool.exe', { type: 'application/octet-stream' })]);
    await click('Upload 1 file');

    await click('Done');

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('closes on Escape once the uploads have failed', async () => {
    await pick([new File(['x'.repeat(10)], 'paper.pdf', { type: 'application/pdf' })]);
    await click('Upload 1 file');
    await act(async () => heldUpload('paper.pdf').fail(new Error('Server said no')));
    await flush();

    await pressEscape();

    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('hands a file uploaded for a reference to onComplete', async () => {
    await pick([new File(['x'.repeat(10)], 'paper.pdf', { type: 'application/pdf' })]);
    await click('Upload 1 file');
    expect(heldUpload('paper.pdf').meta).toMatchObject({ project_id: 'project-1', reference_id: 'ref-1' });

    await act(async () => heldUpload('paper.pdf').succeed());
    await flush();

    expect(onComplete).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('cannot be dismissed while a file is still uploading', async () => {
    await pick([new File(['x'.repeat(10)], 'paper.pdf', { type: 'application/pdf' })]);
    await click('Upload 1 file');

    await pressEscape();

    expect(button('Done')).toBeUndefined();
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe('FileUploadDialog without a reference', () => {
  beforeEach(async () => {
    await renderDialog(undefined);
  });

  async function uploadOne(): Promise<void> {
    await pick([new File(['x'.repeat(10)], 'paper.pdf', { type: 'application/pdf' })]);
    await click('Upload 1 file');
    await act(async () => heldUpload('paper.pdf').succeed());
    await flush();
  }

  it('starts reference matching once the files are uploaded', async () => {
    vi.mocked(startMultipleWorkflowsApiWorkflowsStartMultiplePost).mockResolvedValue({
      project_id: 'project-1',
      types: [WorkflowRunType.ReferenceFileMatching],
      workflow_run_ids: ['run-1'],
      message: 'Started',
    });

    await uploadOne();

    expect(startMultipleWorkflowsApiWorkflowsStartMultiplePost).toHaveBeenCalledWith({
      body: { project_id: 'project-1', workflow_types: [WorkflowRunType.ReferenceFileMatching] },
    });
    expect(toast.success).toHaveBeenCalledWith('Files uploaded. Matching them to your references.');
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("doesn't hold the dialog open while the project's data refetches", async () => {
    vi.mocked(startMultipleWorkflowsApiWorkflowsStartMultiplePost).mockResolvedValue({
      project_id: 'project-1',
      types: [WorkflowRunType.ReferenceFileMatching],
      workflow_run_ids: ['run-1'],
      message: 'Started',
    });
    // An active project query whose refetch never ends, as a slow overview would.
    const client = testQueryClient();
    const observer = new QueryObserver(client, {
      queryKey: projectQueryKeys.all('project-1'),
      queryFn: () => new Promise<never>(() => {}),
    });
    const unsubscribe = observer.subscribe(() => {});
    await renderDialog(undefined, client);

    await uploadOne();

    expect(onComplete).toHaveBeenCalledOnce();
    unsubscribe();
  });

  it("still completes when matching can't start, and says why", async () => {
    vi.mocked(startMultipleWorkflowsApiWorkflowsStartMultiplePost).mockRejectedValue(
      new ApiError(409, 'A matching run is already going'),
    );

    await uploadOne();

    expect(toast.error).toHaveBeenCalledWith('A matching run is already going');
    expect(toast.success).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledOnce();
  });
});
