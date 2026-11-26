'use client';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { listThreadsApiChatThreadsGet } from '@/lib/generated-api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { ConversationSheet } from './conversation-sheet';
import { GuidedSteps } from './guided-steps';
import { useLiveReport } from './use-live-report';

const LIST_KEY = ['live-reports', 'list'] as const;

/**
 * The /live-reports page: a published report brought up to date in guided
 * steps. The conversation with the agent runs behind the buttons; the sheet
 * shows it. The open report is in the path, `/live-reports/<id>`.
 */
export function LiveReportsView({ threadId }: { threadId: string | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const report = useLiveReport(threadId);
  const reports = useQuery({
    queryKey: LIST_KEY,
    queryFn: () => listThreadsApiChatThreadsGet({ query: { kind: 'live_report' } }),
  });

  const open = (id: string | null) => router.push(id ? `/live-reports/${id}` : '/live-reports');

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b px-6 py-3">
        <h1 className="mr-auto text-lg font-semibold">Live reports</h1>
        <Select value={threadId ?? ''} onValueChange={(id) => open(id)}>
          <SelectTrigger className="w-72">
            <SelectValue placeholder="Open a live report" />
          </SelectTrigger>
          <SelectContent>
            {(reports.data ?? []).map((thread) => (
              <SelectItem key={thread.id} value={thread.id}>
                {thread.title ?? 'Untitled report'}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={() => open(null)}>
          <Plus className="size-4" /> New live report
        </Button>
        {threadId && <ConversationSheet messages={report.messages} running={report.working} />}
      </header>

      {report.failed ? (
        <LoadFailure failed={report.failed} onRetry={report.refresh} />
      ) : report.loading ? (
        <p className="text-muted-foreground p-6 text-sm">Loading…</p>
      ) : (
        <GuidedSteps
          key={threadId ?? 'new'}
          report={report}
          onStart={(file) =>
            report.start(file, (id) => {
              // Reading a large report takes a while: open it only if the page is
              // still on the new report, not on one the person has opened since.
              if (window.location.pathname === '/live-reports') open(id);
              queryClient.invalidateQueries({ queryKey: LIST_KEY });
            })
          }
        />
      )}
    </div>
  );
}

/** A report that couldn't be read: never shown as an empty one, which would offer a new upload. */
function LoadFailure({ failed, onRetry }: { failed: 'not-found' | 'error'; onRetry: () => void }) {
  if (failed === 'not-found') {
    return (
      <p className="text-muted-foreground p-6 text-sm">
        This live report doesn&apos;t exist, or it isn&apos;t yours. Open another from the list, or start a new one.
      </p>
    );
  }
  return (
    <div className="flex items-center gap-3 p-6 text-sm">
      <p className="text-destructive">The report couldn&apos;t be loaded.</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
