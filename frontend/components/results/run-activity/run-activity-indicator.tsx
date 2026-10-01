'use client';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Progress } from '@/components/ui/progress';
import { WorkflowRunSummary } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { isAnyWorkflowActive } from '@/lib/workflow-state';
import { Loader2 } from 'lucide-react';
import { RunActivityItem, useRunActivity } from './use-run-activity';

interface RunActivityIndicatorProps {
  projectId: string;
  workflowDetails: WorkflowRunSummary[];
}

/**
 * What is running, as one control in the project header instead of a panel over
 * the page.
 *
 * The toast this replaces grew a row per active assessment and, with a dozen of
 * them going, covered the whole right-hand side of every tab — the pane you
 * would be reading while you wait. A header button is the same information at a
 * fixed size: the count is always in view, and the list is one click away in a
 * popover that closes on Escape and never sits on top of the content.
 *
 * Only current work is listed. Finished assessments are read in the Assessments
 * tab, where their results are.
 */
export function RunActivityIndicator({ projectId, workflowDetails }: RunActivityIndicatorProps) {
  const active = isAnyWorkflowActive(workflowDetails);
  const { running, queued } = useRunActivity(projectId, workflowDetails, active);

  if (!active) return null;

  // Naming the one thing that runs beats counting it. Past that the names stop
  // fitting, and the count is what the header can usefully say.
  const summary =
    running.length === 0 ? 'Starting…' : running.length === 1 ? running[0].label : `${running.length} running`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        {/* Ghost, not outlined: this reports state, it does not ask to be
            pressed, and the row already carries three bordered controls and a
            filled one. The spinner keeps its colour so the row still has one
            live thing in it. */}
        <Button
          variant="ghost"
          size="xs"
          className="gap-1.5 px-1.5 text-muted-foreground hover:text-foreground"
          aria-label={`${running.length} assessment${running.length === 1 ? '' : 's'} running. Show details`}
        >
          <Loader2 className="text-primary size-3.5 animate-spin" />
          <span className="hidden max-w-52 truncate sm:inline">{summary}</span>
          {running.length > 1 && <span className="font-mono tabular-nums sm:hidden">{running.length}</span>}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-0">
        {/* A dozen assessments is a normal batch, so the whole list scrolls as
            one region — bounded by whatever room Radix found below the button,
            never by the number of things running. */}
        <div className="max-h-[min(26rem,calc(var(--radix-popover-content-available-height)-4.5rem))] overflow-y-auto">
          <ActivitySection title="Running now" count={running.length}>
            {running.length > 0 ? (
              running.map((item) => <ActivityRow key={item.runId} item={item} />)
            ) : (
              <p className="px-2 py-1.5 text-[13px] text-muted-foreground">Getting the first assessment started…</p>
            )}
          </ActivitySection>

          {queued.length > 0 && (
            <ActivitySection title="Queued" count={queued.length} bordered>
              {queued.map((item) => (
                <ActivityRow key={item.runId} item={item} queued />
              ))}
            </ActivitySection>
          )}
        </div>

        <p className="border-t px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
          Results appear as each assessment finishes.
        </p>
      </PopoverContent>
    </Popover>
  );
}

function ActivitySection({
  title,
  count,
  bordered = false,
  children,
}: {
  title: string;
  count: number;
  bordered?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn(bordered && 'border-t')}>
      {/* Sticky, so a long list never leaves you unsure which section you are
          scrolling through. */}
      <div className="bg-popover sticky top-0 flex items-center justify-between px-3 pt-2.5 pb-1">
        <h3 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">{title}</h3>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{count}</span>
      </div>
      <div className="space-y-px p-1.5 pt-0">{children}</div>
    </div>
  );
}

function ActivityRow({ item, queued = false }: { item: RunActivityItem; queued?: boolean }) {
  // A single-step node has nothing to report but that it is going, and a bar
  // pinned at 0% or 100% would say something untrue about it.
  const showSteps = item.totalSteps > 1;
  const percent = showSteps ? Math.min(100, Math.round((item.currentStep / item.totalSteps) * 100)) : 0;

  return (
    <div className="flex items-start gap-2 rounded-md px-2 py-1.5">
      {/* The same dot the assessment rail uses for the same states. */}
      <span
        className={cn(
          'mt-1.5 size-1.5 shrink-0 rounded-full',
          queued ? 'bg-muted-foreground/40' : 'bg-primary animate-pulse',
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className={cn('min-w-0 flex-1 truncate text-[13px]', queued && 'text-muted-foreground')}>
            {item.label}
          </span>
          {showSteps && (
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {item.currentStep}/{item.totalSteps}
            </span>
          )}
        </div>
        {item.detail && <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{item.detail}</p>}
        {showSteps && <Progress value={percent} className="mt-1.5 h-1" />}
      </div>
    </div>
  );
}
