'use client';

import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Issue, ProjectDetailed } from '@/lib/generated-api';
import { getIssueCount, hasActiveFilters, useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { Loader2, X } from 'lucide-react';
import { Ref, useImperativeHandle, useRef, useState } from 'react';
import { DocumentExplorerSidebarFilter } from './document-explorer-sidebar-filter';
import { DocumentIssuesList, DocumentIssuesListHandle } from './document-issues-list';

export interface DocumentExplorerSidebarHandle {
  scrollToTop: () => void;
  scrollToIssue: (issue: Issue) => void;
}

interface DocumentExplorerSidebarProps {
  ref?: Ref<DocumentExplorerSidebarHandle>;
  visibleIssues: Issue[];
  filteredIssues: Issue[];
  resolvedCount: number;
  passingCount: number;
  isAnyProcessing: boolean;
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onSelectIssue: (issue: Issue) => void;
  onClearSelection: () => void;
}

export function DocumentExplorerSidebar({
  ref,
  visibleIssues,
  filteredIssues,
  resolvedCount,
  passingCount,
  isAnyProcessing,
  readOnly,
  onSelectIssue,
  onClearSelection,
}: DocumentExplorerSidebarProps) {
  const { selectedLineRange, filter, setFilter, clearFilters } = useDocumentExplorerStore();

  const [scrollContainer, setScrollContainer] = useState<HTMLDivElement | null>(null);
  const issuesListRef = useRef<DocumentIssuesListHandle>(null);

  useImperativeHandle(ref, () => ({
    scrollToTop: () => {
      scrollContainer?.scrollTo({ top: 0, behavior: 'instant' });
    },
    scrollToIssue: (issue: Issue) => {
      requestAnimationFrame(() => {
        issuesListRef.current?.scrollToIssue(issue);
      });
    },
  }));

  const visibleIssueCount = getIssueCount(visibleIssues);
  const filteredIssueCount = getIssueCount(filteredIssues);

  const selectionLabel = selectedLineRange
    ? selectedLineRange[0] === selectedLineRange[1]
      ? `Line ${selectedLineRange[0]}`
      : `Lines ${selectedLineRange[0]}–${selectedLineRange[1]}`
    : null;

  return (
    <div className="col-span-5 bg-muted/50 rounded-lg rounded-l-none text-sm flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap px-4 pt-4 pb-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground inline-flex items-center gap-1.5">
          {isAnyProcessing && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="inline-flex size-3.5 items-center justify-center"
                  aria-label="Some results are still loading"
                >
                  <Loader2 className="size-3.5 animate-spin" />
                </span>
              </TooltipTrigger>
              <TooltipContent>Some results are still loading, see Assessments tab for more details</TooltipContent>
            </Tooltip>
          )}
          {visibleIssueCount > 0 &&
            (filteredIssueCount === visibleIssueCount
              ? `${visibleIssueCount} issues`
              : `${filteredIssueCount} of ${visibleIssueCount} issues`)}
          {visibleIssueCount === 0 && isAnyProcessing && 'Finding issues...'}
        </span>
        <div className="flex items-center flex-wrap gap-1">
          {selectionLabel && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-6 px-2 gap-1 shadow-xs bg-card"
              onClick={onClearSelection}
            >
              {selectionLabel}
              <X />
            </Button>
          )}
          {visibleIssues.length > 0 && (
            <DocumentExplorerSidebarFilter
              issues={visibleIssues}
              filter={filter}
              onFilterChange={setFilter}
              resolvedCount={resolvedCount}
              passingCount={passingCount}
            />
          )}
        </div>
      </div>

      <div ref={setScrollContainer} className="space-y-2 overflow-y-auto flex-1 px-4 pt-0 pb-4">
        {visibleIssues.length === 0 && !isAnyProcessing && (
          <div className="text-sm text-muted-foreground py-4 space-y-2">
            <p>No issues found for this document.</p>
          </div>
        )}

        {visibleIssues.length > 0 &&
          filteredIssues.length === 0 &&
          !isAnyProcessing &&
          hasActiveFilters(filter) &&
          !selectedLineRange && (
            <div className="text-sm text-muted-foreground space-y-1 py-8 text-center">
              <p>No issues match the current filters.</p>
              <Button variant="link" size="sm" className="text-xs" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          )}

        <DocumentIssuesList
          ref={issuesListRef}
          issues={filteredIssues}
          scrollElement={scrollContainer}
          hideJumpButton={selectedLineRange !== null}
          onSelect={onSelectIssue}
          readOnly={readOnly}
        />
      </div>
    </div>
  );
}
