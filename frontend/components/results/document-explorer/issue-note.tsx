'use client';

import { Markdown } from '@/components/markdown';
import { useProjectView } from '@/components/results/project-view-context';
import { feedbackLabel, IssueFeedbackButtons } from '@/components/results/components/issue-feedback-buttons';
import {
  useCanSubmitIssueFeedback,
  useIsIssueFeedbackVisible,
  useIssueFeedbackFromContext,
} from '@/lib/contexts/project-feedback-context';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { FeedbackType, Issue } from '@/lib/generated-api';
import { useIssueActions } from '@/lib/hooks/use-issue-actions';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { SEVERITY } from '@/lib/severity-style';
import { isIssueResolved } from '@/lib/stores/document-explorer-store';
import { cn } from '@/lib/utils';
import {
  ArrowUpRightIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  LightbulbIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  UndoIcon,
} from 'lucide-react';
import Link from 'next/link';
import { ReactNode, useState } from 'react';

export function issueLineRange(issue: Issue): [number, number] | null {
  const { start_line: start, end_line: end } = issue as Issue & {
    start_line?: number | null;
    end_line?: number | null;
  };
  if (typeof start !== 'number' || typeof end !== 'number') return null;
  return [start, end];
}

export function lineLabel(issue: Issue): string | null {
  const range = issueLineRange(issue);
  if (!range) return null;
  const [start, end] = range;
  return start === end ? `L${start}` : `L${start}–${end}`;
}

/**
 * The description as one line of plain prose, for a note that is closed.
 *
 * Descriptions are markdown, and a preview cannot render it: block elements
 * would break the single line, and the raw source would show its own asterisks
 * and brackets. So the markup is flattened to the text it stands for, and the
 * line is cut by CSS rather than by counting characters, which keeps the cut at
 * the edge of whatever width the note happens to have.
 */
function previewText(description: string): string {
  return description
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, '$1')
    .replace(/^\s*(?:[#>]+|[-+*]|\d+\.)\s*/gm, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** One line of the description, shown under the title while the note is closed. */
export function IssuePreview({ issue }: { issue: Issue }) {
  const text = previewText(issue.description ?? '');
  if (!text) return null;

  return <span className="mt-0.5 block truncate text-[12px] leading-snug text-muted-foreground">{text}</span>;
}

/**
 * A closed issue says nothing about whether it was rated, so a whole margin of them hides
 * where the reader has already been. This marks the ones carrying feedback, and its
 * tooltip carries the note that was written with it — the thumb alone says a judgement
 * was made but not what it was about.
 *
 * The trigger is a span, not the button Radix renders by default: this sits inside the
 * heading button that opens the issue, and a button within a button is invalid markup.
 * The padding is there to give a 12px icon something to hover.
 */
function IssueFeedbackIndicator({ issueId }: { issueId: string }) {
  const { feedback, isReadOnly } = useIssueFeedbackFromContext(issueId);
  if (!feedback) return null;

  const label = feedbackLabel(feedback.feedback_type, feedback.feedback_text, isReadOnly);
  const Icon = feedback.feedback_type === FeedbackType.ThumbsUp ? ThumbsUpIcon : ThumbsDownIcon;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          aria-label={label}
          className="-my-1 inline-flex shrink-0 items-center px-0.5 py-1 text-muted-foreground hover:text-foreground"
        >
          <Icon className="size-3" />
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{label}</TooltipContent>
    </Tooltip>
  );
}

/** The line above an issue's title: its severity, where it came from, where it lands. */
export function IssueMeta({ issue }: { issue: Issue }) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const resolved = isIssueResolved(issue);
  const line = lineLabel(issue);
  const feedbackVisible = useIsIssueFeedbackVisible(issue.id);

  return (
    <span className="flex items-center gap-1.5">
      <span className={cn('block size-1.5 shrink-0 rounded-full', SEVERITY[issue.severity].dot)} />
      <span className="truncate font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
        {getWorkflowTypeName(issue.workflow_type)}
      </span>
      {resolved && (
        <span className="inline-flex shrink-0 items-center gap-0.5 font-mono text-[10px] text-muted-foreground uppercase">
          <CheckIcon className="size-3" />
          Resolved
        </span>
      )}
      {feedbackVisible && issue.id && <IssueFeedbackIndicator issueId={issue.id} />}
      {line && (
        <span className="ml-auto shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">{line}</span>
      )}
    </span>
  );
}

/**
 * A way from an issue to the assessment run that raised it: the run's report
 * (the reproducibility check, say, writes one the issues only itemise), its
 * history, and every other issue it found.
 */
function AssessmentReportLink({ issue }: { issue: Issue }) {
  const { assessmentHref } = useProjectView();

  return (
    <Link
      href={assessmentHref(issue.workflow_type, issue.workflow_run_id)}
      className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
    >
      View full assessment report
      <ArrowUpRightIcon className="size-3" />
    </Link>
  );
}

/**
 * The counterpart of the report link, for an issue read from its assessment's
 * own results: the way to the passage it is about. An issue with no lines still
 * gets one — it opens the explorer, which is where the rest of them are.
 *
 * `label` overrides the default wording for a host where the line number means
 * nothing to the reader, such as the Word add-in selecting a paragraph.
 */
export function IssueDocumentLink({
  issue,
  onNavigate,
  label,
}: {
  issue: Issue;
  onNavigate: (lineRange?: [number, number]) => void;
  label?: string;
}) {
  const range = issueLineRange(issue);
  const line = lineLabel(issue);

  return (
    <button
      type="button"
      onClick={() => onNavigate(range ?? undefined)}
      className="inline-flex cursor-pointer items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
    >
      {label ?? (line ? `View in document at ${line}` : 'View in document')}
      <ArrowUpRightIcon className="size-3" />
    </button>
  );
}

/**
 * Everything an open issue shows below its title — description, suggested
 * action, details, and the actions that change it. Shared so the margin note and
 * the list row cannot drift apart.
 *
 * `crossLink` is the way out of the issue to wherever it was not met: by
 * default its assessment's report, since the body is read from the document.
 * Read from the assessment instead, that link would only point at the page it
 * is on, so callers there pass the document link (or null for none).
 */
export function IssueBody({ issue, readOnly, crossLink }: { issue: Issue; readOnly: boolean; crossLink?: ReactNode }) {
  const { resolveIssue, unresolveIssue, isResolving, isUnresolving } = useIssueActions();
  const canRate = useCanSubmitIssueFeedback(issue.id);
  const [showDetails, setShowDetails] = useState(false);

  const resolved = isIssueResolved(issue);
  const busy = isResolving || isUnresolving;

  return (
    <div className="space-y-2">
      <div className="text-foreground/80 text-xs leading-relaxed [&_p]:mb-1 [&_p:last-child]:mb-0">
        <Markdown>{issue.description}</Markdown>
      </div>

      {issue.suggested_action && (
        <div className="bg-background/60 rounded border border-dashed px-2 py-1.5">
          <p className="mb-1 flex items-center gap-1 font-mono text-[9.5px] tracking-wide text-muted-foreground uppercase">
            <LightbulbIcon className="size-3" />
            Suggested action
          </p>
          <div className="text-xs leading-relaxed [&_p]:mb-1 [&_p:last-child]:mb-0">
            <Markdown>{issue.suggested_action}</Markdown>
          </div>
        </div>
      )}

      {issue.long_description && (
        <>
          <button
            onClick={() => setShowDetails(!showDetails)}
            aria-expanded={showDetails}
            className="flex cursor-pointer items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
          >
            {showDetails ? <ChevronUpIcon className="size-3" /> : <ChevronDownIcon className="size-3" />}
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
          {showDetails && (
            <div className="text-foreground/80 text-xs leading-relaxed [&_p]:mb-1 [&_p:last-child]:mb-0">
              <Markdown>{issue.long_description}</Markdown>
            </div>
          )}
        </>
      )}

      {crossLink === undefined ? <AssessmentReportLink issue={issue} /> : crossLink}

      {issue.id && (!readOnly || canRate) && (
        <div className="flex items-center gap-1.5 pt-0.5">
          {!readOnly && (
            <Button
              size="sm"
              variant={resolved ? 'outline' : 'default'}
              className="h-6 px-2 text-[11px]"
              disabled={busy}
              onClick={() => (resolved ? unresolveIssue(issue.id) : resolveIssue(issue.id))}
            >
              {resolved ? <UndoIcon className="size-3" /> : <CheckIcon className="size-3" />}
              {resolved ? 'Mark unresolved' : 'Mark resolved'}
            </Button>
          )}
          {canRate && (
            <span className="ml-auto">
              <IssueFeedbackButtons issueId={issue.id} />
            </span>
          )}
        </div>
      )}
    </div>
  );
}
