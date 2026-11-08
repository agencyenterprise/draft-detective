import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants';
import { FileRole, WorkflowRunType } from '@/lib/generated-api';
import type { UploadProgress } from '@/lib/hooks/upload';
import { useStepUpload } from './use-step-upload';
import { useWizard, WizardProvider } from './wizard-context';

const mocks = vi.hoisted(() => ({ create: vi.fn(), start: vi.fn(), upload: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  createProjectEndpointApiProjectsPost: mocks.create,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost: mocks.start,
}));
vi.mock('@/lib/hooks/upload', async (original) => ({
  ...(await original<typeof import('@/lib/hooks/upload')>()),
  uploadSingleFile: mocks.upload,
}));
// The provider's assessment defaults are step 2's concern; step 1 only needs the provider to mount.
vi.mock('@/lib/hooks/use-visible-workflow-types', () => ({ useVisibleWorkflowTypes: () => ({ visibleTypes: [] }) }));
vi.mock('@/lib/hooks/use-workflow-types', () => ({ useWorkflowTypes: () => ({ workflowTypes: [] }) }));
vi.mock('@/lib/hooks/use-recent-workflow-selection', () => ({
  useRecentWorkflowSelection: () => ({ recentTypes: [], isPending: false }),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.create.mockResolvedValue({ project: { id: 'p-1', group_by_severity: false } });
  mocks.upload.mockResolvedValue(undefined);
  mocks.start.mockResolvedValue([]);
});

const doc = (size = 1024) => {
  const file = new File(['x'], 'draft.docx');
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

async function mountStep() {
  const onComplete = vi.fn();
  let step!: ReturnType<typeof useStepUpload>;
  let wizard!: ReturnType<typeof useWizard>;
  function Probe() {
    step = useStepUpload(onComplete);
    wizard = useWizard();
    return null;
  }
  const view = await renderInto(
    withQueryClient(
      testQueryClient(),
      <WizardProvider>
        <Probe />
      </WizardProvider>,
    ),
  );
  return { onComplete, view, step: () => step, wizard: () => wizard };
}

describe('useStepUpload', () => {
  it('creates the project, uploads the draft as its main file, starts the first workflows and hands over', async () => {
    const { onComplete, view, step, wizard } = await mountStep();
    await act(async () => step().handleDocumentChange([doc()]));
    expect(step().canContinue).toBe(true);

    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.create).toHaveBeenCalledWith({ body: { title: 'draft.docx' } });
    expect(mocks.upload).toHaveBeenCalledWith(
      step().mainDocument,
      expect.objectContaining({ projectId: 'p-1', fileRole: FileRole.Main }),
    );
    expect(mocks.start).toHaveBeenCalledWith({
      body: {
        project_id: 'p-1',
        workflow_types: [
          WorkflowRunType.DocumentProcessing,
          WorkflowRunType.ReferenceExtraction,
          WorkflowRunType.DocumentSummarization,
        ],
      },
    });
    expect(mocks.start.mock.invocationCallOrder[0]).toBeGreaterThan(mocks.upload.mock.invocationCallOrder[0]);
    expect(wizard().projectId).toBe('p-1');
    expect(wizard().groupBySeverity).toBe(false);
    expect(step().uploadStage).toBe('complete');
    expect(onComplete).toHaveBeenCalledOnce();
    await view.unmount();
  });

  it('reports upload progress against the file size, and disables Continue while running', async () => {
    let report!: (progress: UploadProgress) => void;
    let land!: () => void;
    mocks.upload.mockImplementation(
      (_file: File, opts: { onProgress: (p: UploadProgress) => void }) =>
        new Promise<void>((resolve) => {
          report = opts.onProgress;
          land = resolve;
        }),
    );
    const { view, step } = await mountStep();
    await act(async () => step().handleDocumentChange([doc(2048)]));

    await act(async () => step().handleContinue());
    await flush();
    expect(step().uploadStage).toBe('uploading');
    expect(step().canContinue).toBe(false);

    await act(async () => report({ uploaded_size: 1024, total_size: 2048, progress_percent: 50 }));
    expect(step().stageMessage).toBe('Uploading document... 50% (1 KB / 2 KB)');

    await act(async () => land());
    await flush();
    expect(step().uploadStage).toBe('complete');
    await view.unmount();
  });

  it('refuses an oversized draft before calling the API', async () => {
    const { onComplete, view, step } = await mountStep();
    await act(async () => step().handleDocumentChange([doc(MAX_FILE_SIZE_BYTES + 1)]));
    expect(step().preflightStatus.format).toBe('invalid');
    expect(step().canContinue).toBe(false);

    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.create).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
    await view.unmount();
  });

  it('returns to a retryable state when a step fails, without handing over', async () => {
    mocks.upload.mockRejectedValue(new Error('Upload failed: network down'));
    const { onComplete, view, step, wizard } = await mountStep();
    await act(async () => step().handleDocumentChange([doc()]));

    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.start).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Upload failed: network down');
    expect(step().uploadStage).toBe('idle');
    expect(step().uploadProgress).toBeNull();
    expect(step().canContinue).toBe(true);
    expect(wizard().projectId).toBeNull();
    expect(onComplete).not.toHaveBeenCalled();
    await view.unmount();
  });

  it('retries a failed upload into the project it already created', async () => {
    mocks.upload.mockRejectedValueOnce(new Error('Upload failed: network down'));
    const { onComplete, view, step, wizard } = await mountStep();
    await act(async () => step().handleDocumentChange([doc()]));

    await act(async () => step().handleContinue());
    await flush();
    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.create).toHaveBeenCalledOnce();
    expect(mocks.upload).toHaveBeenCalledTimes(2);
    expect(mocks.upload).toHaveBeenLastCalledWith(step().mainDocument, expect.objectContaining({ projectId: 'p-1' }));
    expect(mocks.start).toHaveBeenCalledOnce();
    expect(wizard().projectId).toBe('p-1');
    expect(onComplete).toHaveBeenCalledOnce();
    await view.unmount();
  });

  it('retries a failed workflow start without creating or uploading again', async () => {
    mocks.start.mockRejectedValueOnce(new Error('Could not start workflows'));
    const { onComplete, view, step } = await mountStep();
    await act(async () => step().handleDocumentChange([doc()]));

    await act(async () => step().handleContinue());
    await flush();
    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.create).toHaveBeenCalledOnce();
    expect(mocks.upload).toHaveBeenCalledOnce();
    expect(mocks.start).toHaveBeenCalledTimes(2);
    expect(mocks.start).toHaveBeenLastCalledWith(
      expect.objectContaining({ body: expect.objectContaining({ project_id: 'p-1' }) }),
    );
    expect(onComplete).toHaveBeenCalledOnce();
    await view.unmount();
  });

  it('creates a new project when a different draft is picked after a failure', async () => {
    mocks.upload.mockRejectedValueOnce(new Error('Upload failed: network down'));
    mocks.create
      .mockResolvedValueOnce({ project: { id: 'p-1', group_by_severity: true } })
      .mockResolvedValueOnce({ project: { id: 'p-2', group_by_severity: true } });
    const { view, step, wizard } = await mountStep();
    await act(async () => step().handleDocumentChange([doc()]));
    await act(async () => step().handleContinue());
    await flush();

    await act(async () => step().handleDocumentChange([doc()]));
    await act(async () => step().handleContinue());
    await flush();

    expect(mocks.create).toHaveBeenCalledTimes(2);
    expect(mocks.upload).toHaveBeenLastCalledWith(step().mainDocument, expect.objectContaining({ projectId: 'p-2' }));
    expect(wizard().projectId).toBe('p-2');
    await view.unmount();
  });

  it('groups by severity when the new project does not say', async () => {
    mocks.create.mockResolvedValue({ project: { id: 'p-2', group_by_severity: null } });
    const { view, step, wizard } = await mountStep();
    await act(async () => wizard().setGroupBySeverity(false));
    await act(async () => step().handleDocumentChange([doc()]));

    await act(async () => step().handleContinue());
    await flush();

    expect(wizard().groupBySeverity).toBe(true);
    await view.unmount();
  });
});
