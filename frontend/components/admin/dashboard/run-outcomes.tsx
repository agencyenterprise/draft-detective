'use client';

import { DashboardFeedbackSummary, WorkflowUsageItem } from '@/lib/generated-api';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { formatCompact, formatPercent } from './format';

interface Segment {
  label: string;
  count: number;
  color: string;
}

/**
 * Outcome split across every run in the window, plus the feedback signal.
 *
 * The outcome colours come from the reserved status palette and always sit
 * beside their label and count, so the reading never depends on telling green
 * from red.
 */
export function RunOutcomes({
  workflows,
  feedback,
}: {
  workflows: WorkflowUsageItem[];
  feedback: DashboardFeedbackSummary;
}) {
  const totals = workflows.reduce(
    (accumulator, workflow) => ({
      completed: accumulator.completed + workflow.statuses.completed,
      failed: accumulator.failed + workflow.statuses.failed,
      cancelled: accumulator.cancelled + workflow.statuses.cancelled,
      inProgress: accumulator.inProgress + workflow.statuses.running + workflow.statuses.pending,
      // Waiting on a person, not on the pipeline: kept apart from "In progress"
      // so long consent waits do not read as operational load.
      awaitingApproval: accumulator.awaitingApproval + workflow.statuses.awaiting_approval,
    }),
    { completed: 0, failed: 0, cancelled: 0, inProgress: 0, awaitingApproval: 0 },
  );

  const segments: Segment[] = [
    { label: 'Completed', count: totals.completed, color: 'var(--viz-good)' },
    { label: 'Failed', count: totals.failed, color: 'var(--viz-critical)' },
    { label: 'Cancelled', count: totals.cancelled, color: 'var(--viz-neutral)' },
    { label: 'In progress', count: totals.inProgress, color: 'var(--viz-series-1)' },
    { label: 'Awaiting approval', count: totals.awaitingApproval, color: 'var(--viz-warning)' },
  ].filter((segment) => segment.count > 0);

  const runs = segments.reduce((sum, segment) => sum + segment.count, 0);
  const feedbackTotal = feedback.thumbs_up + feedback.thumbs_down;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-medium text-foreground">Run outcomes</h3>
          <span className="text-xs tabular-nums text-muted-foreground">{formatCompact(runs)} runs</span>
        </div>

        {runs === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing ran in this period.</p>
        ) : (
          <>
            <div
              className="mt-3 flex h-3 gap-0.5"
              role="img"
              aria-label={`Run outcomes: ${segments.map((s) => `${s.label} ${s.count}`).join(', ')}`}
            >
              {segments.map((segment) => (
                <div
                  key={segment.label}
                  className="first:rounded-l last:rounded-r"
                  // A category with runs in it never disappears, however small its share.
                  style={{ backgroundColor: segment.color, flexGrow: segment.count, minWidth: '2px' }}
                />
              ))}
            </div>
            <ul className="mt-3 space-y-1.5">
              {segments.map((segment) => (
                <li key={segment.label} className="flex items-center gap-2 text-xs">
                  <span
                    aria-hidden
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: segment.color }}
                  />
                  <span className="text-foreground">{segment.label}</span>
                  <span className="ml-auto tabular-nums text-foreground">{formatCompact(segment.count)}</span>
                  <span className="w-10 text-right tabular-nums text-muted-foreground">
                    {formatPercent(segment.count / runs)}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div>
        <Tooltip>
          <TooltipTrigger asChild>
            <h3
              tabIndex={0}
              className="w-fit cursor-help text-sm font-medium text-foreground underline decoration-dotted underline-offset-2"
            >
              Feedback
            </h3>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            Only feedback whose author chose to share it with administrators. Feedback left as private is never counted
            here.
          </TooltipContent>
        </Tooltip>
        {feedbackTotal === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No feedback in this period.</p>
        ) : (
          <>
            <div className="mt-2 flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-sm">
                <ThumbsUp className="h-4 w-4 text-[var(--viz-good)]" aria-hidden />
                <span className="tabular-nums text-foreground">{formatCompact(feedback.thumbs_up)}</span>
                <span className="text-muted-foreground">up</span>
              </span>
              <span className="flex items-center gap-1.5 text-sm">
                <ThumbsDown className="h-4 w-4 text-[var(--viz-critical)]" aria-hidden />
                <span className="tabular-nums text-foreground">{formatCompact(feedback.thumbs_down)}</span>
                <span className="text-muted-foreground">down</span>
              </span>
            </div>
            <div className="mt-3 h-2 w-full rounded-full bg-[var(--viz-good)]/20">
              {/*
                The exact ratio, not formatPercent: that returns "<1%" / ">99%"
                at the extremes, which is not a CSS length, so the fill would
                silently collapse to nothing under a label reading ">99%".
              */}
              <div
                className="h-2 rounded-full bg-[var(--viz-good)]"
                style={{ width: `${(feedback.thumbs_up / feedbackTotal) * 100}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {formatPercent(feedback.thumbs_up / feedbackTotal)} positive · {formatCompact(feedback.with_comment)} with
              a written comment
            </p>
          </>
        )}
      </div>
    </div>
  );
}
