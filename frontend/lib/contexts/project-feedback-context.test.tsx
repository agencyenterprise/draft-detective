import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { ProjectFeedbackProvider, useIssueFeedbackFromContext } from '@/lib/contexts/project-feedback-context';
import { FeedbackType, FeedbackVisibility } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ list: vi.fn(), submit: vi.fn(), patch: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getProjectFeedbackApiFeedbackProjectProjectIdGet: mocks.list,
  submitFeedbackApiFeedbackPost: mocks.submit,
  updateProjectEndpointApiProjectProjectIdPatch: mocks.patch,
}));
// The dialog only collects a choice; the provider decides what happens with it.
const dialog = vi.hoisted(() => ({
  props: null as null | { isOpen: boolean; onConfirm: (v: string) => Promise<void> | void; onCancel: () => void },
}));
vi.mock('@/components/feedback/feedback-privacy-dialog', () => ({
  FeedbackPrivacyDialog: (props: NonNullable<typeof dialog.props>) => {
    dialog.props = props;
    return null;
  },
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => {
  vi.clearAllMocks();
  dialog.props = null;
  mocks.list.mockResolvedValue([]);
  mocks.submit.mockResolvedValue({ id: 'f', issue_id: 'i-1', feedback_type: FeedbackType.ThumbsUp });
  mocks.patch.mockResolvedValue({});
});

async function mountProvider(visibility: FeedbackVisibility | null, readOnly = false) {
  let issue!: ReturnType<typeof useIssueFeedbackFromContext>;
  function Probe() {
    issue = useIssueFeedbackFromContext('i-1');
    return null;
  }
  const view = await renderInto(
    withQueryClient(
      testQueryClient(),
      <ProjectFeedbackProvider projectId="p" feedbackVisibility={visibility} readOnly={readOnly}>
        <Probe />
      </ProjectFeedbackProvider>,
    ),
  );
  await flush();
  const rate = async () => {
    await act(async () => issue.submitFeedback({ feedback_type: FeedbackType.ThumbsUp, feedback_text: 'useful' }));
    await flush();
  };
  return { view, rate };
}

const sentFeedback = { body: { issue_id: 'i-1', feedback_type: FeedbackType.ThumbsUp, feedback_text: 'useful' } };

describe('ProjectFeedbackProvider', () => {
  it('submits straight away once the project has a visibility', async () => {
    const { view, rate } = await mountProvider(FeedbackVisibility.Private);
    await rate();

    expect(mocks.submit).toHaveBeenCalledExactlyOnceWith(sentFeedback);
    expect(dialog.props?.isOpen).toBe(false);
    await view.unmount();
  });

  it('asks who may see feedback first, saves the choice, then submits', async () => {
    const { view, rate } = await mountProvider(null);
    await rate();
    expect(mocks.submit).not.toHaveBeenCalled();
    expect(dialog.props?.isOpen).toBe(true);

    await act(async () => dialog.props?.onConfirm(FeedbackVisibility.IssueOnly));
    await flush();

    expect(mocks.patch).toHaveBeenCalledWith({
      path: { project_id: 'p' },
      body: { feedback_visibility: FeedbackVisibility.IssueOnly },
    });
    expect(mocks.submit).toHaveBeenCalledExactlyOnceWith(sentFeedback);
    expect(mocks.submit.mock.invocationCallOrder[0]).toBeGreaterThan(mocks.patch.mock.invocationCallOrder[0]);
    expect(dialog.props?.isOpen).toBe(false);
    await view.unmount();
  });

  it('drops the rating when the viewer cancels the privacy question', async () => {
    const { view, rate } = await mountProvider(null);
    await rate();

    await act(async () => dialog.props?.onCancel());
    await flush();

    expect(mocks.patch).not.toHaveBeenCalled();
    expect(mocks.submit).not.toHaveBeenCalled();
    expect(dialog.props?.isOpen).toBe(false);
    await view.unmount();
  });

  it('says so and sends nothing when the privacy choice cannot be saved', async () => {
    mocks.patch.mockRejectedValue(new Error('Project not found'));
    const { view, rate } = await mountProvider(null);
    await rate();

    await act(async () => dialog.props?.onConfirm(FeedbackVisibility.Private));
    await flush();

    expect(mocks.submit).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Project not found');
    expect(dialog.props?.isOpen).toBe(false);
    await view.unmount();
  });

  it('never writes feedback on a project the viewer may only read', async () => {
    const { view, rate } = await mountProvider(null, true);
    await rate();

    expect(mocks.submit).not.toHaveBeenCalled();
    expect(dialog.props?.isOpen).toBe(false);
    await view.unmount();
  });
});
