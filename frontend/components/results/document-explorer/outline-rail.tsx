'use client';

import { HelpLink } from '@/components/help/help-link';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Issue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { SEVERITY } from '@/lib/severity-style';
import { DocumentExplorerFilter, hasActiveFilters } from '@/lib/stores/document-explorer-store';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { CircleHelp } from 'lucide-react';
import { useMemo } from 'react';
import { AssessmentFilter } from './assessment-filter';
import { OutlineEntry, issuesInSection } from './outline';

/** The severities this rail filters by, worst first. Their colours and labels
 *  come from the shared palette so the rail cannot drift from the margin. */
const SEVERITY_ROWS = [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low] as const;

interface OutlineRailProps {
  outline: OutlineEntry[];
  /**
   * Issues after the passing/resolved toggles, before severity and type. Drives
   * the filter counts, so they keep showing what turning a filter on would add.
   */
  visibleIssues: Issue[];
  /**
   * Issues after every filter — the same set the document highlights. Drives the
   * section dots, so the outline always agrees with what is marked in the text.
   */
  markedIssues: Issue[];
  filter: DocumentExplorerFilter;
  onFilterChange: (partial: Partial<DocumentExplorerFilter>) => void;
  onClearFilters: () => void;
  resolvedCount: number;
  passingCount: number;
  activeLine: number | null;
  onJump: (entry: OutlineEntry) => void;
}

export function OutlineRail({
  outline,
  visibleIssues,
  markedIssues,
  filter,
  onFilterChange,
  onClearFilters,
  resolvedCount,
  passingCount,
  activeLine,
  onJump,
}: OutlineRailProps) {
  const workflowCounts = useMemo(() => {
    const counts = new Map<WorkflowRunType, number>();
    for (const issue of visibleIssues) {
      counts.set(issue.workflow_type, (counts.get(issue.workflow_type) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [visibleIssues]);

  const toggleSeverity = (value: SeverityEnum) => {
    const next = filter.severity.includes(value)
      ? filter.severity.filter((s) => s !== value)
      : [...filter.severity, value];
    onFilterChange({ severity: next });
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <section className="max-h-[55%] shrink-0 overflow-y-auto px-3 py-4">
        <div className="flex items-center justify-between px-2">
          <h3 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Filter issues</h3>
          {hasActiveFilters(filter) && (
            <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={onClearFilters}>
              Clear
            </Button>
          )}
        </div>

        <div className="mt-2 space-y-px">
          {SEVERITY_ROWS.map((severity) => {
            const count = visibleIssues.filter((i) => i.severity === severity).length;
            const on = filter.severity.includes(severity);
            return (
              <button
                key={severity}
                onClick={() => toggleSeverity(severity)}
                aria-pressed={on}
                className={cn(
                  'flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                  on ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                )}
              >
                <span className={cn('block size-2 rounded-[2px]', SEVERITY[severity].dot)} />
                <span className="flex-1 text-left">{SEVERITY[severity].label}</span>
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 space-y-2.5 px-2">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Switch
              checked={filter.showPassing}
              onCheckedChange={(showPassing) => onFilterChange({ showPassing })}
              className="scale-90"
            />
            <span className="flex-1">Passing checks</span>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{passingCount}</span>
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Switch
              checked={filter.showResolved}
              onCheckedChange={(showResolved) => onFilterChange({ showResolved })}
              className="scale-90"
            />
            <span className="flex-1">Resolved</span>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{resolvedCount}</span>
          </label>
        </div>

        {(workflowCounts.length > 0 || filter.workflowType.length > 0) && (
          <div className="mt-3">
            <AssessmentFilter
              counts={workflowCounts}
              value={filter.workflowType}
              onChange={(workflowType) => onFilterChange({ workflowType })}
            />
          </div>
        )}
      </section>

      <div className="border-t" />

      <section className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <h3 className="px-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Document outline</h3>
        {outline.length === 0 ? (
          <p className="px-2 pt-2 text-xs text-muted-foreground">This document has no headings.</p>
        ) : (
          <ol className="mt-2 space-y-px">
            {outline.map((entry) => {
              const marks = issuesInSection(markedIssues, entry);
              const isActive = activeLine !== null && activeLine >= entry.line && activeLine <= entry.endLine;
              return (
                <li key={entry.id}>
                  <button
                    onClick={() => onJump(entry)}
                    className={cn(
                      'flex w-full cursor-pointer items-center gap-2 rounded-md py-1.5 pr-2 text-left text-sm transition-colors',
                      isActive ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                    )}
                    style={{ paddingLeft: `${0.5 + (entry.level - 1) * 0.75}rem` }}
                  >
                    <span className="w-6 shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                      {entry.line}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{entry.text}</span>
                    <span className="flex shrink-0 items-center gap-[3px]">
                      {marks.slice(0, 4).map((m) => (
                        <span key={m.id} className={cn('block size-1.5 rounded-full', SEVERITY[m.severity].dot)} />
                      ))}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* A row rather than a paragraph: this rail already carries filters and a
          whole outline, and prose at the foot of it costs more than it explains. */}
      <div className="shrink-0 border-t p-3">
        <HelpLink
          topic="issues"
          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm no-underline transition-colors hover:bg-accent/60 hover:text-foreground"
        >
          <CircleHelp className="size-3.5 shrink-0" aria-hidden />
          Help
        </HelpLink>
      </div>
    </div>
  );
}
