'use client';

import { Button } from '@/components/ui/button';
import { SkeletonList } from '@/components/ui/skeleton-list';
import { Issue, ProjectDetailed } from '@/lib/generated-api';
import { getIssueCount, hasActiveFilters, useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
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
  passingCount: number;
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
  passingCount,
  isAnyProcessing,
  projectDetail,
  readOnly,
  onSelectIssue,
}: DocumentExplorerSidebarProps) {
  const { selectedChunkIndices, clearChunkSelection, filter, setFilter, clearFilters } = useDocumentExplorerStore();

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

  const visibleIssueCount = getIssueCount(visibleIssues);
  const filteredIssueCount = getIssueCount(filteredIssues);

  return (
    <div className="col-span-5 bg-muted/50 rounded-lg rounded-l-none text-sm flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap px-4 pt-4 pb-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground">
          {visibleIssueCount > 0 &&
            (filteredIssueCount === visibleIssueCount
              ? `${visibleIssueCount} issues`
              : `${filteredIssueCount} of ${visibleIssueCount} issues`)}
          {visibleIssueCount === 0 && isAnyProcessing && 'Finding issues...'}
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

      <div ref={scrollContainerRef} className="space-y-2 overflow-y-auto flex-1 px-4 pt-0 pb-4">
        {visibleIssues.length === 0 && !isAnyProcessing && (
          <div className="text-sm text-muted-foreground py-4 space-y-2">
            <p>No issues found for this document.</p>
            <p>You can still view detailed assessment for each chunk by selecting a chunk from the document.</p>
          </div>
        )}

        {isAnyProcessing && <SkeletonList count={3} />}

        {visibleIssues.length > 0 &&
          filteredIssues.length === 0 &&
          !isAnyProcessing &&
          hasActiveFilters(filter) &&
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
