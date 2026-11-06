import { beforeEach, describe, expect, it, vi } from 'vitest';
import { uploadSingleFile } from '@/lib/hooks/upload/upload-single';
import { FileRole } from '@/lib/generated-api';
import { fakeTus, heldUpload, resetFakeTus } from '@/lib/hooks/upload/fake-tus';

vi.mock('@uppy/tus', async () => ({ default: (await import('@/lib/hooks/upload/fake-tus')).FakeTus }));

const auth = vi.hoisted(() => ({ header: vi.fn<() => Promise<string | undefined>>() }));
vi.mock('@/lib/api', () => ({ baseUrl: 'http://api.test', getAuthHeader: auth.header }));

const doc = () => new File(['x'.repeat(200)], 'paper.docx', { type: 'application/msword' });

/** Waits for Uppy's auto-proceed timer to hand the file to the uploader. */
const reachUploader = () => vi.waitFor(() => heldUpload('paper.docx'));

beforeEach(() => {
  resetFakeTus();
  auth.header.mockResolvedValue('Bearer token-1');
});

describe('uploadSingleFile', () => {
  it('uploads the file with its project and role, reports progress, and resolves once it lands', async () => {
    const onProgress = vi.fn();
    let done = false;
    const upload = uploadSingleFile(doc(), { projectId: 'p-1', fileRole: FileRole.Main, onProgress }).then(
      () => (done = true),
    );
    await reachUploader();

    expect(heldUpload('paper.docx').meta).toMatchObject({
      filename: 'paper.docx',
      project_id: 'p-1',
      role: FileRole.Main,
    });
    heldUpload('paper.docx').progress(50, 200);
    expect(onProgress).toHaveBeenLastCalledWith({ uploaded_size: 50, total_size: 200, progress_percent: 25 });
    expect(done).toBe(false);

    heldUpload('paper.docx').succeed();
    await upload;
    expect(done).toBe(true);
  });

  it('rejects with the upload error', async () => {
    const upload = uploadSingleFile(doc(), { projectId: 'p-1', fileRole: FileRole.Main });
    await reachUploader();

    heldUpload('paper.docx').fail(new Error('Server said no'));

    await expect(upload).rejects.toThrow('Server said no');
  });

  it('refuses to start without a signed-in session', async () => {
    auth.header.mockResolvedValue(undefined);

    await expect(uploadSingleFile(doc(), { projectId: 'p-1', fileRole: FileRole.Main })).rejects.toThrow(
      /Authentication required/,
    );
    expect(fakeTus.options).toBeUndefined();
  });
});
