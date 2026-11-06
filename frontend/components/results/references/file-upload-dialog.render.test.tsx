import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { heldUpload, resetFakeTus } from '@/lib/hooks/upload/fake-tus';

vi.mock('@uppy/tus', async () => ({ default: (await import('@/lib/hooks/upload/fake-tus')).FakeTus }));
vi.mock('@/lib/api', () => ({ baseUrl: 'http://api.test', getAuthHeader: async () => 'Bearer token-1' }));
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

beforeEach(async () => {
  vi.clearAllMocks();
  resetFakeTus();
  rendered = await renderInto(
    withQueryClient(
      testQueryClient(),
      <FileUploadDialog
        isOpen
        projectId="project-1"
        referenceId="ref-1"
        title="Add files"
        description="Add source documents."
        multiple
        onCancel={onCancel}
        onComplete={onComplete}
      />,
    ),
  );
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
