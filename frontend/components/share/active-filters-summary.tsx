'use client';

import { SeverityBadge } from '@/components/results/components/severity-badge';
import { Badge } from '@/components/ui/badge';
import { SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { editsPhrase, exportOutcomeSentence, type ExportCounts } from '@/lib/export-scope';

export interface ActiveFilters {
  severity: SeverityEnum[];
  workflowType: WorkflowRunType[];
  showPassing: boolean;
}

/** Whether an export scoped by these filters would differ from a full one. */
export function hasActiveFilters(filters: ActiveFilters): boolean {
  const partialSeverity = filters.severity.length > 0 && filters.severity.length < 3;
  return partialSeverity || filters.workflowType.length > 0 || filters.showPassing;
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
  includeEdits,
}: {
  filters: ActiveFilters;
  counts: ExportCounts;
  includeEdits: boolean;
}) {
  const filtered = hasActiveFilters(filters);

  return (
    <div className="space-y-1.5">
      <p className="text-sm">
        <span className="font-medium tabular-nums">{plural(counts.issues, 'issue')}</span>
        <span className="text-muted-foreground"> · </span>
        <span className="font-medium tabular-nums">{editsPhrase(counts.edits)}</span>
      </p>
      <p className="text-sm text-muted-foreground">{exportOutcomeSentence(includeEdits)}</p>
      {filtered ? (
        <FilterBadges filters={filters} />
      ) : (
        <p className="text-sm text-muted-foreground">Every unresolved issue, from every assessment.</p>
      )}
    </div>
  );
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
      {partialSeverity &&
        filters.severity.map((severity) => <SeverityBadge key={severity} severity={severity} hideIcon />)}
      {filters.workflowType.map((type) => (
        <Badge key={type} variant="secondary" className="font-normal">
          {getWorkflowTypeName(type)}
        </Badge>
      ))}
      {filters.showPassing && (
        <Badge variant="outline" className="font-normal">
          Passing checks included
        </Badge>
      )}
    </div>
  );
}
