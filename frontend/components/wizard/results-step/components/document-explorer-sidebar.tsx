'use client';

import { Button } from '@/components/ui/button';
import { SkeletonList } from '@/components/ui/skeleton-list';
import { Issue, ProjectDetailed, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { getChunkIssuesByIndices } from '@/lib/severity';
import { EyeIcon, EyeOffIcon, X } from 'lucide-react';
import { Ref, useImperativeHandle, useMemo, useRef } from 'react';
import { DocumentExplorerSidebarFilter } from './document-explorer-sidebar-filter';
import { DocumentIssuesList } from './document-issues-list';
import { SingleChunkContent } from './single-chunk-content';

export interface DocumentExplorerSidebarHandle {
  scrollToTop: () => void;
  scrollToIssue: (issue: Issue) => void;
}

interface DocumentExplorerSidebarProps {
  ref?: Ref<DocumentExplorerSidebarHandle>;
  selectedChunkIndices: number[];
  issues: Issue[];
  filteredIssues: Issue[];
  isAnyProcessing: boolean;
  severityFilter: SeverityEnum[];
  onSeverityFilterChange: (value: SeverityEnum[]) => void;
  workflowTypeFilter: WorkflowRunType[];
  onWorkflowTypeFilterChange: (value: WorkflowRunType[]) => void;
  showResolved: boolean;
  onShowResolvedChange: (value: boolean) => void;
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onSelectIssue: (issue: Issue) => void;
  onClearChunkSelection: () => void;
}

export function DocumentExplorerSidebar({
  ref,
  selectedChunkIndices,
  issues,
  filteredIssues,
  isAnyProcessing,
  severityFilter,
  onSeverityFilterChange,
  workflowTypeFilter,
  onWorkflowTypeFilterChange,
  showResolved,
  onShowResolvedChange,
  projectDetail,
  readOnly,
  onSelectIssue,
  onClearChunkSelection,
}: DocumentExplorerSidebarProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    scrollToTop: () => {
      scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'instant' });
    },
    scrollToIssue: (issue: Issue) => {
      requestAnimationFrame(() => {
        const element = document.getElementById(`issue-${issue.id}`);
        element?.scrollIntoView({ behavior: 'instant' });
      });
    },
  }));

  const selectedFilteredIssues = useMemo(() => {
    let result = filteredIssues;

    if (selectedChunkIndices.length > 0) {
      result = getChunkIssuesByIndices(result, selectedChunkIndices);
    }

    return result;
  }, [filteredIssues, selectedChunkIndices]);

  const sortedIssues = useMemo(() => {
    let result = [...selectedFilteredIssues];

    if (!showResolved) {
      result = result.filter((issue) => !issue.resolved_by);
    }

    return result.sort((a, b) => {
      const aResolved = !!a.resolved_by;
      const bResolved = !!b.resolved_by;
      if (aResolved !== bResolved) return aResolved ? 1 : -1;
      return 0;
    });
  }, [selectedFilteredIssues, showResolved]);

  const resolvedCount = useMemo(
    () => selectedFilteredIssues.filter((issue) => issue.resolved_by).length,
    [selectedFilteredIssues],
  );

  const totalCount = showResolved ? issues.length : issues.filter((issue) => !issue.resolved_by).length;
  const displayCount = showResolved ? selectedFilteredIssues.length : selectedFilteredIssues.length - resolvedCount;
  const hasActiveFilters = severityFilter.length > 0 || workflowTypeFilter.length > 0 || !showResolved;

  const handleClearFilters = () => {
    onSeverityFilterChange([]);
    onWorkflowTypeFilterChange([]);
    onShowResolvedChange(true);
  };

  return (
    <div className="col-span-5 bg-muted/50 rounded-lg rounded-l-none text-sm flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap px-4 pt-4 pb-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground">
          {issues.length > 0 &&
            (displayCount === totalCount ? `${totalCount} issues` : `${displayCount} of ${totalCount} issues`)}
          {issues.length === 0 && isAnyProcessing && 'Finding issues...'}
        </span>
        <div className="flex items-center flex-wrap gap-1">
          {selectedChunkIndices.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-6 px-2 gap-1 shadow-xs bg-white"
              onClick={onClearChunkSelection}
            >
              {selectedChunkIndices.length === 1
                ? `Chunk #${selectedChunkIndices[0]}`
                : `${selectedChunkIndices.length} chunks selected`}
              <X />
            </Button>
          )}
          {issues.length > 0 && (
            <>
              {resolvedCount > 0 && (
                <Button
                  variant={showResolved ? 'secondary' : 'outline'}
                  size="sm"
                  className="text-xs h-6 px-2 gap-1 shadow-xs"
                  onClick={() => onShowResolvedChange(!showResolved)}
                  title={showResolved ? 'Hide resolved issues' : 'Show resolved issues'}
                >
                  {showResolved ? <EyeIcon className="size-3" /> : <EyeOffIcon className="size-3" />}
                  {resolvedCount} resolved
                </Button>
              )}
              <DocumentExplorerSidebarFilter
                issues={issues}
                severityFilter={severityFilter}
                onSeverityFilterChange={onSeverityFilterChange}
                workflowTypeFilter={workflowTypeFilter}
                onWorkflowTypeFilterChange={onWorkflowTypeFilterChange}
              />
            </>
          )}
        </div>
      </div>

      <div ref={scrollContainerRef} className="space-y-2 overflow-y-auto flex-1 px-4 pt-0 pb-4">
        {issues.length === 0 && !isAnyProcessing && (
          <div className="text-sm text-muted-foreground space-y-2">
            <p>No issues found for this document.</p>
            <p>You can still view detailed analysis for each chunk by selecting a chunk from the document.</p>
          </div>
        )}

        {isAnyProcessing && <SkeletonList count={3} />}

        {issues.length > 0 &&
          sortedIssues.length === 0 &&
          !isAnyProcessing &&
          hasActiveFilters &&
          selectedChunkIndices.length === 0 && (
            <div className="text-sm text-muted-foreground space-y-1 py-8 text-center">
              <p>No issues match the current filters.</p>
              <Button variant="link" size="sm" className="text-xs" onClick={handleClearFilters}>
                Clear filters
              </Button>
            </div>
          )}

        <DocumentIssuesList
          issues={sortedIssues}
          hideJumpToChunk={selectedChunkIndices.length > 0}
          onSelect={onSelectIssue}
          readOnly={readOnly}
        />

        {selectedChunkIndices.map((chunkIndex) => (
          <SingleChunkContent
            key={chunkIndex}
            chunkIndex={chunkIndex}
            projectDetail={projectDetail}
            workflowRuns={projectDetail.workflow_runs ?? []}
            readOnly={readOnly}
            showChunkLabel={selectedChunkIndices.length > 1}
          />
        ))}
      </div>
    </div>
  );
}
