import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useRecentWorkflowSelection } from '@/lib/hooks/use-recent-workflow-selection';
import { type RecentWorkflowSelectionResponse, WorkflowRunType } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ recent: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getRecentSelectionApiWorkflowTypesRecentSelectionGet: mocks.recent,
}));

beforeEach(() => vi.clearAllMocks());

type Selection = ReturnType<typeof useRecentWorkflowSelection>;

function Probe({ onRender }: { onRender: (selection: Selection) => void }) {
  onRender(useRecentWorkflowSelection());
  return null;
}

describe('useRecentWorkflowSelection', () => {
  it('stays pending on a revisit until the new answer lands, so the wizard never seeds from the previous project', async () => {
    const client = testQueryClient();
    let latest!: Selection;
    const record = (selection: Selection) => (latest = selection);
    mocks.recent.mockResolvedValueOnce({ workflow_types: [WorkflowRunType.AbbreviationScanV2] });
    const first = await renderInto(withQueryClient(client, <Probe onRender={record} />));
    await flush();
    expect(latest).toEqual({ recentTypes: [WorkflowRunType.AbbreviationScanV2], isPending: false });
    await first.unmount();

    let answer!: (value: RecentWorkflowSelectionResponse) => void;
    mocks.recent.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));
    const seen: Selection[] = [];
    const second = await renderInto(withQueryClient(client, <Probe onRender={(s) => seen.push(s)} />));

    // Every render that still holds the cached answer reports itself pending.
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((s) => s.isPending)).toBe(true);
    await act(async () => answer({ workflow_types: [WorkflowRunType.FiguresTablesCheck] }));
    await flush();
    expect(seen.at(-1)).toEqual({ recentTypes: [WorkflowRunType.FiguresTablesCheck], isPending: false });
    expect(mocks.recent).toHaveBeenCalledTimes(2);
    await second.unmount();
  });

  it('settles on no types, without retrying, when the request fails', async () => {
    const client = testQueryClient();
    // The hook turns retries off itself; a default client would retry three times.
    client.setDefaultOptions({ queries: { retry: 3 } });
    let latest!: Selection;
    mocks.recent.mockRejectedValue(new Error('boom'));

    const view = await renderInto(withQueryClient(client, <Probe onRender={(s) => (latest = s)} />));
    await flush();

    expect(latest).toEqual({ recentTypes: [], isPending: false });
    expect(mocks.recent).toHaveBeenCalledOnce();
    await view.unmount();
  });
});
