import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { toast } from 'sonner';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useProjectFeedback } from '@/lib/hooks/use-project-feedback';
import { FeedbackType, type FeedbackResponse } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ list: vi.fn(), submit: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getProjectFeedbackApiFeedbackProjectProjectIdGet: mocks.list,
  submitFeedbackApiFeedbackPost: mocks.submit,
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

function feedback(issueId: string, type: FeedbackType = FeedbackType.ThumbsUp): FeedbackResponse {
  return { id: `f-${issueId}-${type}`, issue_id: issueId, feedback_type: type } as unknown as FeedbackResponse;
}

async function mountFeedback(projectId: string | undefined) {
  const client = testQueryClient();
  let hook!: ReturnType<typeof useProjectFeedback>;
  function Probe() {
    hook = useProjectFeedback(projectId);
    return null;
  }
  const view = await renderInto(withQueryClient(client, <Probe />));
  await flush();
  return { client, view, hook: () => hook };
}

describe('useProjectFeedback', () => {
  it("loads the project's feedback once and looks it up by issue", async () => {
    mocks.list.mockResolvedValue([feedback('a'), feedback('b', FeedbackType.ThumbsDown)]);
    const { view, hook } = await mountFeedback('p');

    expect(mocks.list).toHaveBeenCalledExactlyOnceWith({ path: { project_id: 'p' } });
    expect(hook().getFeedbackForIssue('b')).toEqual(feedback('b', FeedbackType.ThumbsDown));
    expect(hook().getFeedbackForIssue('missing')).toBeNull();
    await view.unmount();
  });

  it('asks for nothing without a project', async () => {
    const { view, hook } = await mountFeedback(undefined);

    expect(mocks.list).not.toHaveBeenCalled();
    expect(hook().isLoading).toBe(false);
    expect(hook().getFeedbackForIssue('a')).toBeNull();
    await view.unmount();
  });

  it('treats a failed load as no feedback yet, so the issues still render', async () => {
    mocks.list.mockRejectedValue(new Error('500'));
    const { view, hook } = await mountFeedback('p');

    expect(hook().feedbackList).toEqual([]);
    expect(hook().getFeedbackForIssue('a')).toBeNull();
    await view.unmount();
  });

  it("replaces the issue's earlier rating in the cache, sending blank text as null", async () => {
    mocks.list.mockResolvedValue([feedback('a'), feedback('b')]);
    const changed = feedback('a', FeedbackType.ThumbsDown);
    mocks.submit.mockResolvedValue(changed);
    const { client, view, hook } = await mountFeedback('p');

    await act(async () =>
      hook().submitFeedback({ issueId: 'a', feedbackType: FeedbackType.ThumbsDown, feedbackText: '' }),
    );
    await flush();

    expect(mocks.submit).toHaveBeenCalledWith({
      body: { issue_id: 'a', feedback_type: FeedbackType.ThumbsDown, feedback_text: null },
    });
    expect(client.getQueryData(['feedback', 'project', 'p'])).toEqual([changed, feedback('b')]);
    expect(hook().getFeedbackForIssue('a')).toEqual(changed);
    expect(mocks.list).toHaveBeenCalledOnce();
    expect(toast.success).toHaveBeenCalledOnce();
    await view.unmount();
  });

  it("adds a first rating for an issue to the project's list", async () => {
    mocks.list.mockResolvedValue([feedback('a')]);
    mocks.submit.mockResolvedValue(feedback('c'));
    const { view, hook } = await mountFeedback('p');

    await act(async () => hook().submitFeedback({ issueId: 'c', feedbackType: FeedbackType.ThumbsUp }));
    await flush();

    expect(hook().feedbackList).toEqual([feedback('a'), feedback('c')]);
    await view.unmount();
  });

  it('keeps the cached feedback and says so when a submit fails', async () => {
    mocks.list.mockResolvedValue([feedback('a')]);
    mocks.submit.mockRejectedValue(new Error('Feedback is closed'));
    const { view, hook } = await mountFeedback('p');

    await act(async () => hook().submitFeedback({ issueId: 'a', feedbackType: FeedbackType.ThumbsDown }));
    await flush();

    expect(hook().feedbackList).toEqual([feedback('a')]);
    expect(toast.error).toHaveBeenCalledWith('Feedback is closed');
    await view.unmount();
  });
});
