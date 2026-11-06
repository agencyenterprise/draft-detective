import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import type { QueryClient } from '@tanstack/react-query';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { useUpload } from '@/lib/hooks/upload/use-upload';
import type { UseUploadOptions, UseUploadReturn } from '@/lib/hooks/upload/types';
import { FileRole } from '@/lib/generated-api';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { fakeTus as tus, heldUpload as held, resetFakeTus } from '@/lib/hooks/upload/fake-tus';

vi.mock('@uppy/tus', async () => ({ default: (await import('@/lib/hooks/upload/fake-tus')).FakeTus }));

const auth = vi.hoisted(() => ({ header: vi.fn<() => Promise<string | undefined>>() }));
vi.mock('@/lib/api', () => ({ baseUrl: 'http://api.test', getAuthHeader: auth.header }));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const PROJECT = 'project-1';

function pdf(name: string, size = 100): File {
  return new File(['x'.repeat(size)], name, { type: 'application/pdf' });
}

function Probe({ options, onRender }: { options: UseUploadOptions; onRender: (upload: UseUploadReturn) => void }) {
  onRender(useUpload(options));
  return null;
}

interface Mounted {
  view: Rendered;
  client: QueryClient;
  current: () => UseUploadReturn;
  rerender: (options: UseUploadOptions) => Promise<void>;
}

async function mount(options: Partial<UseUploadOptions> = {}): Promise<Mounted> {
  const client = testQueryClient();
  let latest!: UseUploadReturn;
  const ui = (opts: UseUploadOptions) =>
    withQueryClient(client, <Probe options={opts} onRender={(upload) => (latest = upload)} />);
  const view = await renderInto(ui({ projectId: PROJECT, ...options }));
  return { view, client, current: () => latest, rerender: (opts) => view.rerender(ui(opts)) };
}

/** Runs `fn` inside act() and lets Uppy's promises settle. */
async function step(fn: () => void): Promise<void> {
  await act(async () => fn());
  await flush();
}

const statuses = (upload: UseUploadReturn) => upload.files.map((f) => [f.file.name, f.status]);

let mounted: Mounted | undefined;

beforeEach(() => {
  vi.clearAllMocks();
  resetFakeTus();
  auth.header.mockResolvedValue('Bearer token-1');
});

afterEach(async () => {
  await mounted?.view.unmount();
  mounted = undefined;
});

describe('useUpload', () => {
  it('uploads each file with its project and role, and reports both completions', async () => {
    const onFileComplete = vi.fn();
    const onAllComplete = vi.fn();
    mounted = await mount({ onFileComplete, onAllComplete });
    const invalidate = vi.spyOn(mounted.client, 'invalidateQueries');
    const a = pdf('a.pdf');
    const b = pdf('b.pdf');

    await step(() => mounted!.current().startUpload([a, b]));

    expect(statuses(mounted.current())).toEqual([
      ['a.pdf', 'uploading'],
      ['b.pdf', 'uploading'],
    ]);
    expect(mounted.current().isUploading).toBe(true);
    expect(held('a.pdf').meta).toMatchObject({ filename: 'a.pdf', project_id: PROJECT, role: FileRole.Support });
    expect(held('a.pdf').meta).not.toHaveProperty('reference_id');

    await step(() => held('a.pdf').succeed());
    expect(onFileComplete).toHaveBeenCalledWith(a, expect.objectContaining({ name: 'a.pdf' }));
    expect(onAllComplete).not.toHaveBeenCalled();
    expect(mounted.current().completedCount).toBe(1);

    await step(() => held('b.pdf').succeed());
    expect(onFileComplete).toHaveBeenCalledTimes(2);
    expect(onAllComplete).toHaveBeenCalledOnce();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: projectQueryKeys.all(PROJECT) });
    expect(mounted.current()).toMatchObject({
      isUploading: false,
      completedCount: 2,
      totalCount: 2,
      overallProgress: 100,
    });
  });

  it('sends the role and reference the caller asked for', async () => {
    mounted = await mount({ fileRole: FileRole.ReviewInput, referenceId: 'ref-9' });

    await step(() => mounted!.current().startUpload([pdf('a.pdf')]));

    expect(held('a.pdf').meta).toMatchObject({
      project_id: PROJECT,
      role: FileRole.ReviewInput,
      reference_id: 'ref-9',
    });
  });

  it('signs every TUS request with the current session, and sends no header without one', async () => {
    mounted = await mount();
    await step(() => mounted!.current().addFiles([pdf('a.pdf')]));
    const setHeader = vi.fn();

    await tus.options!.onBeforeRequest({ setHeader });
    auth.header.mockResolvedValue(undefined);
    await tus.options!.onBeforeRequest({ setHeader });

    expect(setHeader).toHaveBeenCalledOnce();
    expect(setHeader).toHaveBeenCalledWith('Authorization', 'Bearer token-1');
  });

  it('tracks byte progress per file and averages it across the batch', async () => {
    mounted = await mount();
    await step(() => mounted!.current().startUpload([pdf('a.pdf'), pdf('b.pdf')]));

    await step(() => held('a.pdf').progress(50, 100));

    expect(mounted.current().files[0].progress).toEqual({ uploaded_size: 50, total_size: 100, progress_percent: 50 });
    expect(mounted.current().overallProgress).toBe(25);
  });

  it('marks a failed file and reports it, and skips the all-complete callback when nothing succeeded', async () => {
    const onError = vi.fn();
    const onAllComplete = vi.fn();
    mounted = await mount({ onError, onAllComplete });
    await step(() => mounted!.current().startUpload([pdf('a.pdf')]));

    await step(() => held('a.pdf').fail(new Error('Server said no')));

    expect(mounted.current().files[0]).toMatchObject({ status: 'error', error: 'Server said no' });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Server said no' }), 'a.pdf');
    expect(onAllComplete).not.toHaveBeenCalled();
    expect(mounted.current().isUploading).toBe(false);
  });

  it('still reports all-complete when one file of the batch failed', async () => {
    const onAllComplete = vi.fn();
    mounted = await mount({ onAllComplete });
    await step(() => mounted!.current().startUpload([pdf('a.pdf'), pdf('b.pdf')]));

    await step(() => held('a.pdf').fail(new Error('boom')));
    await step(() => held('b.pdf').succeed());

    expect(statuses(mounted.current())).toEqual([
      ['a.pdf', 'error'],
      ['b.pdf', 'completed'],
    ]);
    expect(onAllComplete).toHaveBeenCalledOnce();
  });

  it('reports a file Uppy turns away as failed at once, and uploads the rest', async () => {
    const onError = vi.fn();
    mounted = await mount({ onError });
    const exe = new File(['x'], 'tool.exe', { type: 'application/octet-stream' });
    const a = pdf('a.pdf');

    // Uppy refuses the second a.pdf as a duplicate of the first.
    await step(() => mounted!.current().startUpload([exe, a, a]));

    expect(statuses(mounted.current())).toEqual([
      ['tool.exe', 'error'],
      ['a.pdf', 'uploading'],
      ['a.pdf', 'error'],
    ]);
    expect(onError.mock.calls.map(([, name]) => name)).toEqual(['tool.exe', 'a.pdf']);
    expect(tus.held.map((h) => h.name)).toEqual(['a.pdf']);
  });

  it('calls the callbacks from the latest render, not the first', async () => {
    const first = vi.fn();
    const latest = vi.fn();
    mounted = await mount({ onFileComplete: first });
    await step(() => mounted!.current().startUpload([pdf('a.pdf')]));

    await mounted.rerender({ projectId: PROJECT, onFileComplete: latest });
    await step(() => held('a.pdf').succeed());

    expect(first).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledOnce();
  });

  it('drops a removed file so the next upload leaves it out', async () => {
    mounted = await mount();
    await step(() => mounted!.current().addFiles([pdf('a.pdf'), pdf('b.pdf')]));

    await step(() => mounted!.current().removeFile(mounted!.current().files[0].id));
    await step(() => mounted!.current().startUpload());

    expect(statuses(mounted.current())).toEqual([['b.pdf', 'uploading']]);
    expect(tus.held.map((h) => h.name)).toEqual(['b.pdf']);
  });

  it('pauses and resumes one file, or every file in flight', async () => {
    mounted = await mount();
    await step(() => mounted!.current().startUpload([pdf('a.pdf'), pdf('b.pdf')]));
    const [a] = mounted.current().files;

    await step(() => mounted!.current().pauseFile(a.id));
    expect(statuses(mounted.current())).toEqual([
      ['a.pdf', 'paused'],
      ['b.pdf', 'uploading'],
    ]);
    expect([held('a.pdf').isPaused(), held('b.pdf').isPaused()]).toEqual([true, false]);
    await step(() => mounted!.current().resumeFile(a.id));
    expect(mounted.current().files[0].status).toBe('uploading');
    expect(held('a.pdf').isPaused()).toBe(false);

    await step(() => mounted!.current().pauseAll());
    expect(statuses(mounted.current())).toEqual([
      ['a.pdf', 'paused'],
      ['b.pdf', 'paused'],
    ]);
    await step(() => mounted!.current().resumeAll());
    expect(statuses(mounted.current())).toEqual([
      ['a.pdf', 'uploading'],
      ['b.pdf', 'uploading'],
    ]);
  });

  it('cancels unfinished files and keeps the finished ones', async () => {
    mounted = await mount();
    await step(() => mounted!.current().startUpload([pdf('a.pdf'), pdf('b.pdf'), pdf('c.pdf')]));
    await step(() => held('a.pdf').succeed());
    await step(() => mounted!.current().pauseFile(mounted!.current().files[2].id));

    await step(() => mounted!.current().cancelAll());

    expect(mounted.current().files.map((f) => [f.file.name, f.status, f.error])).toEqual([
      ['a.pdf', 'completed', undefined],
      ['b.pdf', 'error', 'Cancelled'],
      ['c.pdf', 'error', 'Cancelled'],
    ]);
    expect(mounted.current().isUploading).toBe(false);
    // Uppy itself dropped the unfinished uploads, so neither can land later.
    expect([held('b.pdf').isGone(), held('c.pdf').isGone()]).toEqual([true, true]);
  });

  it('starts over after reset, sending the props of the latest render', async () => {
    const onAllComplete = vi.fn();
    mounted = await mount({ referenceId: 'ref-A', onAllComplete });
    await step(() => mounted!.current().startUpload([pdf('a.pdf')]));

    // The reference dialogs reset on open so the next upload carries the new reference.
    await mounted.rerender({ projectId: PROJECT, referenceId: 'ref-B', onAllComplete });
    await step(() => mounted!.current().reset());
    expect(mounted.current().files).toEqual([]);

    resetFakeTus();
    await step(() => mounted!.current().startUpload([pdf('b.pdf')]));
    expect(held('b.pdf').meta.reference_id).toBe('ref-B');
    await step(() => held('b.pdf').succeed());

    expect(statuses(mounted.current())).toEqual([['b.pdf', 'completed']]);
    expect(onAllComplete).toHaveBeenCalledOnce();
  });

  it('sends the project, role and reference of the render that added the file, without a reset', async () => {
    mounted = await mount({ referenceId: 'ref-A' });
    await step(() => mounted!.current().addFiles([pdf('first.pdf')]));
    const invalidate = vi.spyOn(mounted.client, 'invalidateQueries');

    await mounted.rerender({ projectId: 'project-2', fileRole: FileRole.ReviewInput, referenceId: 'ref-B' });
    await step(() => mounted!.current().startUpload([pdf('second.pdf')]));

    expect(held('first.pdf').meta).toMatchObject({
      project_id: PROJECT,
      role: FileRole.Support,
      reference_id: 'ref-A',
    });
    expect(held('second.pdf').meta).toMatchObject({
      project_id: 'project-2',
      role: FileRole.ReviewInput,
      reference_id: 'ref-B',
    });

    // Each finished upload refreshes the project it went to.
    await step(() => held('second.pdf').succeed());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: projectQueryKeys.all('project-2') });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: projectQueryKeys.all(PROJECT) });
  });
});
