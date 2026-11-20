import { act } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { liveReportKey, useLiveReport, type LiveReport } from './use-live-report';

// Report A's turn streams until the test ends it.
let endTurn: () => void = () => {};
vi.mock('@/lib/chat/stream', () => ({
  streamChatTurn: async function* () {
    await new Promise<void>((resolve) => (endTurn = resolve));
    yield { t: 'error', v: "A's turn failed" };
  },
}));
vi.mock('@/lib/chat/follow', () => ({ FOLLOW_INTERVAL_MS: 60_000, fetchThreadMessages: async () => [] }));
const api = vi.hoisted(() => ({
  getThread: vi.fn(async () => ({ is_running: false, title: null, kind: 'live_report' })),
  listFiles: vi.fn(async () => [] as { name: string; content: string }[]),
}));
vi.mock('@/lib/generated-api', () => ({
  getThreadApiChatThreadsThreadIdGet: api.getThread,
  listLiveReportFilesApiLiveReportsThreadIdFilesGet: api.listFiles,
  cancelChatTurnApiChatThreadsThreadIdCancelPost: vi.fn(),
  createThreadApiChatThreadsPost: vi.fn(),
  extractAttachmentTextApiChatExtractPost: vi.fn(),
}));

let report: LiveReport;
const seen = (r: LiveReport) => (report = r);
function Probe({ id }: { id: string | null }) {
  seen(useLiveReport(id));
  return null;
}

describe('useLiveReport across reports (the layout keeps it mounted)', () => {
  it("keeps report A's turn off report B", async () => {
    const client = testQueryClient();
    const view = await renderInto(withQueryClient(client, <Probe id="A" />));
    await flush();
    void report.send('The intake is right. Approved.');
    await flush();
    expect(report.working).toBe(true);

    // The person opens report B from the picker while A's turn runs.
    await view.rerender(withQueryClient(client, <Probe id="B" />));
    await flush();
    // B is not running, so it shows no "working…" pill and no Stop for A's turn.
    expect(report.working).toBe(false);

    await act(async () => endTurn());
    await flush();
    expect(report.error).toBeNull();

    // Back on A, its turn's error is still there.
    await view.rerender(withQueryClient(client, <Probe id="A" />));
    await flush();
    expect(report.error).toBe("A's turn failed");
    await view.unmount();
  });
});

describe('useLiveReport following a turn it is not streaming', () => {
  it('reads the files once more when the turn is seen to end', async () => {
    // Opened mid-turn (after a reload): the turn ends between two polls.
    api.getThread.mockResolvedValueOnce({ is_running: true, title: null, kind: 'live_report' });
    api.listFiles.mockClear();
    const client = testQueryClient();
    const view = await renderInto(withQueryClient(client, <Probe id="R" />));
    await flush();
    expect(report.working).toBe(true);
    const readsWhileRunning = api.listFiles.mock.calls.length;

    api.listFiles.mockResolvedValueOnce([{ name: 'research-brief.md', content: '# Brief' }]);
    await act(() => client.refetchQueries({ queryKey: [...liveReportKey('R'), 'thread'] }));
    await flush();

    expect(api.listFiles.mock.calls.length).toBeGreaterThan(readsWhileRunning);
    expect(report.working).toBe(false);
    expect(report.step).toBe('brief');
    await view.unmount();
  });
});

describe('useLiveReport opening a report', () => {
  it('reads the files once more when the first look finds the turn over', async () => {
    // The turn may have ended while the first files read was in flight.
    api.listFiles.mockClear();
    const client = testQueryClient();
    const view = await renderInto(withQueryClient(client, <Probe id="S" />));
    await flush();
    expect(api.listFiles.mock.calls.length).toBeGreaterThanOrEqual(2);
    await view.unmount();
  });
});
