'use client';

import { SeverityFilter } from '@/components/results/components/severity-filter';
import { IssueDocumentLink } from '@/components/results/document-explorer/issue-note';
import { GroupHeader, IssueRow } from '@/components/results/document-explorer/issue-row';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Issue, SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { CheckCircle2, ChevronDownIcon } from 'lucide-react';
import { ReactNode, useState } from 'react';

/** Worst first, as the explorer's queue orders them. */
const SEVERITY_ORDER: SeverityEnum[] = [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low];

interface WorkflowIssuesListProps {
  issues: Issue[];
  /** Whether the issues can be resolved here; rating is governed by the feedback context. */
  readOnly: boolean;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
  /** Rendered at the left of the header row, opposite the count and filter. */
  headerAction?: ReactNode;
}

/**
 * The issues one assessment reported, or an all-clear when it found nothing.
 *
 * The rows are the explorer's: grouped by severity, two lines closed, opening
 * in place. Passing checks (severity `none`) are collapsed behind a disclosure,
 * so an assessment that verified 717 abbreviations and flagged 3 reads as three
 * issues — and does not mount 717 rows to say so.
 */
export function WorkflowIssuesList({
  issues,
  readOnly,
  onNavigateToDocumentExplorer,
  headerAction,
}: WorkflowIssuesListProps) {
  const [showInformational, setShowInformational] = useState(false);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  // Empty means no filter, matching the document explorer's severity toggles.
  const [severityFilter, setSeverityFilter] = useState<SeverityEnum[]>([]);

  const realIssues = issues.filter((i) => i.severity !== SeverityEnum.None);
  const informational = issues.filter((i) => i.severity === SeverityEnum.None);
  const visibleIssues =
    severityFilter.length === 0 ? realIssues : realIssues.filter((i) => severityFilter.includes(i.severity));
  const isFiltered = visibleIssues.length !== realIssues.length;

  const toggleIssue = (issue: Issue) => setActiveIssueId((current) => (current === issue.id ? null : issue.id));

  const renderRow = (issue: Issue) => (
    <IssueRow
      key={issue.id}
      issue={issue}
      active={activeIssueId === issue.id}
      readOnly={readOnly}
      onSelect={toggleIssue}
      crossLink={<IssueDocumentLink issue={issue} onNavigate={onNavigateToDocumentExplorer} />}
    />
  );

  return (
    <div className="space-y-2">
      {realIssues.length === 0 ? (
        <>
          {/* Kept outside the header row below: an all-clear has no count or
              filter to show, but the action must not vanish with them. */}
          {headerAction}
          <div className="flex items-center gap-3 rounded-md border border-green-200 bg-green-50/30 px-4 py-5 dark:border-green-900 dark:bg-green-950/30">
            <CheckCircle2 className="size-5 shrink-0 text-green-600" />
            <div>
              <p className="text-sm font-medium">All checks passed</p>
              <p className="text-xs text-muted-foreground">No issues were found in the document.</p>
            </div>
          </div>
        </>
      ) : (
        <section className="space-y-2">
          <div className="flex items-center gap-2">
            {headerAction}
            <h3 className="ml-auto mr-1 text-sm font-medium text-muted-foreground">
              {isFiltered
                ? `${visibleIssues.length} of ${realIssues.length} issues`
                : `${realIssues.length} issue${realIssues.length !== 1 ? 's' : ''}`}
            </h3>
            <SeverityFilter value={severityFilter} onChange={setSeverityFilter} />
          </div>
          {visibleIssues.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No issues match the selected severities.</p>
          ) : (
            <RowFrame>
              {SEVERITY_ORDER.map((severity) => {
                const group = visibleIssues.filter((issue) => issue.severity === severity);
                if (group.length === 0) return null;
                return (
                  <div key={severity}>
                    <GroupHeader severity={severity} count={group.length} />
                    {group.map(renderRow)}
                  </div>
                );
              })}
            </RowFrame>
          )}
        </section>
      )}

      {informational.length > 0 && (
        <Collapsible open={showInformational} onOpenChange={setShowInformational} className="mt-4 space-y-2">
          <CollapsibleTrigger className="flex cursor-pointer items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">
            <ChevronDownIcon className={cn('size-3.5 transition-transform', !showInformational && '-rotate-90')} />
            {informational.length} informational item{informational.length !== 1 ? 's' : ''}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <RowFrame>
              <div>{informational.map(renderRow)}</div>
            </RowFrame>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

/**
 * The rows carry their own bottom rule, sized for a column that runs to the
 * pane's edges. Here they sit in a padded page, so a frame closes them in, and
 * the last row's rule is dropped so it does not double up with the frame's.
 * Children are groups — a div of rows, with or without a header — so the last
 * row is always the last child of the last child.
 */
function RowFrame({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border [&>div:last-child>div:last-child]:border-b-0">{children}</div>
  );
}
