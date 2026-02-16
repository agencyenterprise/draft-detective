'use client';

import { Button } from '@/components/ui/button';
import { SkeletonList } from '@/components/ui/skeleton-list';
import { Issue, ProjectDetailed } from '@/lib/generated-api';
import { useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { X } from 'lucide-react';
import { Ref, useImperativeHandle, useRef } from 'react';
import { DocumentExplorerSidebarFilter } from './document-explorer-sidebar-filter';
import { DocumentIssuesList } from './document-issues-list';
import { SingleChunkContent } from './single-chunk-content';

export interface DocumentExplorerSidebarHandle {
  scrollToTop: () => void;
  scrollToIssue: (issue: Issue) => void;
}

interface DocumentExplorerSidebarProps {
  ref?: Ref<DocumentExplorerSidebarHandle>;
  visibleIssues: Issue[];
  filteredIssues: Issue[];
  resolvedCount: number;
  isAnyProcessing: boolean;
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onSelectIssue: (issue: Issue) => void;
}

export function DocumentExplorerSidebar({
  ref,
  visibleIssues,
  filteredIssues,
  resolvedCount,
  isAnyProcessing,
  projectDetail,
  readOnly,
  onSelectIssue,
}: DocumentExplorerSidebarProps) {
  const {
    selectedChunkIndices,
    clearChunkSelection,
    severityFilter,
    setSeverityFilter,
    workflowTypeFilter,
    setWorkflowTypeFilter,
    showResolved,
    setShowResolved,
    clearFilters,
  } = useDocumentExplorerStore();

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

  const visibleIssuesCount = visibleIssues.length;
  const filteredIssuesCount = filteredIssues.length;
  const hasActiveFilters = severityFilter.length > 0 || workflowTypeFilter.length > 0 || !showResolved;

  return (
    <div className="col-span-5 bg-muted/50 rounded-lg rounded-l-none text-sm flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap px-4 pt-4 pb-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground">
          {visibleIssuesCount > 0 &&
            (filteredIssuesCount === visibleIssuesCount
              ? `${visibleIssuesCount} issues`
              : `${filteredIssuesCount} of ${visibleIssuesCount} issues`)}
          {visibleIssuesCount === 0 && isAnyProcessing && 'Finding issues...'}
        </span>
        <div className="flex items-center flex-wrap gap-1">
          {selectedChunkIndices.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-6 px-2 gap-1 shadow-xs bg-white"
              onClick={clearChunkSelection}
            >
              {selectedChunkIndices.length === 1
                ? `Chunk #${selectedChunkIndices[0]}`
                : `${selectedChunkIndices.length} chunks selected`}
              <X />
            </Button>
          )}
          {visibleIssuesCount > 0 && (
            <DocumentExplorerSidebarFilter
              issues={visibleIssues}
              severityFilter={severityFilter}
              onSeverityFilterChange={setSeverityFilter}
              workflowTypeFilter={workflowTypeFilter}
              onWorkflowTypeFilterChange={setWorkflowTypeFilter}
              resolvedCount={resolvedCount}
              showResolved={showResolved}
              onShowResolvedChange={setShowResolved}
            />
          )}
        </div>
      </div>

      <div ref={scrollContainerRef} className="space-y-2 overflow-y-auto flex-1 px-4 pt-0 pb-4">
        {visibleIssuesCount === 0 && !isAnyProcessing && (
          <div className="text-sm text-muted-foreground py-4 space-y-2">
            <p>No issues found for this document.</p>
            <p>You can still view detailed analysis for each chunk by selecting a chunk from the document.</p>
          </div>
        )}

        {isAnyProcessing && <SkeletonList count={3} />}

        {visibleIssuesCount > 0 &&
          filteredIssuesCount === 0 &&
          !isAnyProcessing &&
          hasActiveFilters &&
          selectedChunkIndices.length === 0 && (
            <div className="text-sm text-muted-foreground space-y-1 py-8 text-center">
              <p>No issues match the current filters.</p>
              <Button variant="link" size="sm" className="text-xs" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          )}

        <DocumentIssuesList
          issues={filteredIssues}
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
