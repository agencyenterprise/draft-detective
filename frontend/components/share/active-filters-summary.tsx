'use client';

import { SeverityBadge } from '@/components/results/components/severity-badge';
import { Badge } from '@/components/ui/badge';
import { SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import {
  editsPhrase,
  exportOutcomeSentence,
  exportScopeSentence,
  passingChecksIncluded,
  type ExportCounts,
} from '@/lib/export-scope';

export interface ActiveFilters {
  severity: SeverityEnum[];
  workflowType: WorkflowRunType[];
  showPassing: boolean;
}

/**
 * Whether the filters leave findings out, as opposed to letting more in.
 *
 * The passing toggle only ever widens the export, and `exportScopeSentence`
 * already says which way it is set, so a passing-only scope is described in
 * words rather than by a lone badge under "Matching the current filters".
 */
export function narrowsTheExport(filters: ActiveFilters): boolean {
  const partialSeverity = filters.severity.length > 0 && filters.severity.length < 3;
  return partialSeverity || filters.workflowType.length > 0;
}

/**
 * What the export will contain, in one line of badges.
 *
 * The document explorer's filters scope the export, so the dialog states the
 * scope beside the options instead of asking for a second confirmation. With no
 * filter it says so in words rather than showing an empty row. The counts name
 * what was selected; the sentence under them says what becomes of it, which is
 * what the `includeEdits` checkbox changes.
 */
export function ExportScope({
  filters,
  counts,
  countsFailed = false,
  includeEdits,
}: {
  filters: ActiveFilters;
  /** Null until the issues behind them have loaded: an unknown count is not zero. */
  counts: ExportCounts | null;
  /** The issues could not be loaded, so there is nothing to count. */
  countsFailed?: boolean;
  includeEdits: boolean;
}) {
  const filtered = narrowsTheExport(filters);
  const countsStatus = exportCountsStatus(counts, countsFailed);

  return (
    <div className="space-y-1.5">
      {counts && countsStatus === 'known' ? (
        <p className="text-sm">
          <span className="font-medium tabular-nums">{plural(counts.issues, 'issue')}</span>
          <span className="text-muted-foreground"> · </span>
          <span className="font-medium tabular-nums">{editsPhrase(counts.edits)}</span>
        </p>
      ) : countsStatus === 'failed' ? (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          Couldn&apos;t count the issues. The export still includes every one that matches.
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">Counting issues...</p>
      )}
      <p className="text-sm text-muted-foreground">{exportOutcomeSentence(includeEdits)}</p>
      {filtered ? (
        <FilterBadges filters={filters} />
      ) : (
        <p className="text-sm text-muted-foreground">{exportScopeSentence(filters)}</p>
      )}
    </div>
  );
}

/**
 * Whether the counts can be stated yet. Until the issues load the count is
 * unknown, which is not zero; once loading failed it stays unknown.
 */
export function exportCountsStatus(
  counts: ExportCounts | null,
  countsFailed: boolean,
): 'known' | 'failed' | 'counting' {
  if (counts) return 'known';
  return countsFailed ? 'failed' : 'counting';
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

function FilterBadges({ filters }: { filters: ActiveFilters }) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const partialSeverity = filters.severity.length > 0 && filters.severity.length < 3;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-sm text-muted-foreground">Matching the current filters:</span>
      {partialSeverity && filters.severity.map((severity) => <SeverityBadge key={severity} severity={severity} />)}
      {filters.workflowType.map((type) => (
        <Badge key={type} variant="secondary" className="font-normal">
          {getWorkflowTypeName(type)}
        </Badge>
      ))}
      {passingChecksIncluded(filters) && (
        <Badge variant="outline" className="font-normal">
          Passing checks included
        </Badge>
      )}
    </div>
  );
}
