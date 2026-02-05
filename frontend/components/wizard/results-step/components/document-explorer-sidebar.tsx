'use client';

import { Button } from '@/components/ui/button';
import { SkeletonList } from '@/components/ui/skeleton-list';
import { DocumentIssue, ProjectDetailed, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { getChunkIssuesByIndices } from '@/lib/severity';
import { X } from 'lucide-react';
import { Ref, useImperativeHandle, useMemo, useRef } from 'react';
import { DocumentIssuesList } from './document-issues-list';
import { SeverityFilter } from './severity-filter';
import { SingleChunkContent } from './single-chunk-content';
import { WorkflowTypeFilter } from './workflow-type-filter';

export interface DocumentExplorerSidebarHandle {
  scrollToTop: () => void;
  scrollToIssue: (issue: DocumentIssue) => void;
}

interface DocumentExplorerSidebarProps {
  ref?: Ref<DocumentExplorerSidebarHandle>;
  selectedChunkIndices: number[];
  issues: DocumentIssue[];
  filteredIssues: DocumentIssue[];
  isAnyProcessing: boolean;
  severityFilter: SeverityEnum[];
  onSeverityFilterChange: (value: SeverityEnum[]) => void;
  workflowTypeFilter: WorkflowRunType[];
  onWorkflowTypeFilterChange: (value: WorkflowRunType[]) => void;
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onSelectIssue: (issue: DocumentIssue) => void;
  onClearChunkSelection: () => void;
  onNavigateToReferences?: (referenceIndex: number) => void;
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
  projectDetail,
  readOnly,
  onSelectIssue,
  onClearChunkSelection,
  onNavigateToReferences,
}: DocumentExplorerSidebarProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    scrollToTop: () => {
      scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'instant' });
    },
    scrollToIssue: (issue: DocumentIssue) => {
      requestAnimationFrame(() => {
        const element = document.getElementById(`issue-${issue.id}`);
        element?.scrollIntoView({ behavior: 'instant' });
      });
    },
  }));

  const selectedFilteredIssues = useMemo(() => {
    if (selectedChunkIndices.length === 0) {
      return filteredIssues;
    }
    return getChunkIssuesByIndices(filteredIssues, selectedChunkIndices);
  }, [filteredIssues, selectedChunkIndices]);

  return (
    <div className="col-span-5 bg-muted/50 rounded-lg rounded-l-none text-sm flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap px-4 pt-4 pb-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground">
          {issues.length > 0 &&
            (selectedFilteredIssues.length === issues.length
              ? `${issues.length} issues`
              : `${selectedFilteredIssues.length} of ${issues.length} issues`)}
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
              <SeverityFilter value={severityFilter} onChange={onSeverityFilterChange} />
              <WorkflowTypeFilter issues={issues} value={workflowTypeFilter} onChange={onWorkflowTypeFilterChange} />
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

        <DocumentIssuesList
          issues={selectedFilteredIssues}
          hideJumpToChunk={selectedChunkIndices.length > 0}
          onSelect={onSelectIssue}
        />

        {selectedChunkIndices.map((chunkIndex) => (
          <SingleChunkContent
            key={chunkIndex}
            chunkIndex={chunkIndex}
            projectDetail={projectDetail}
            workflowRuns={projectDetail.workflow_runs ?? []}
            readOnly={readOnly}
            onNavigateToReferences={onNavigateToReferences}
            showChunkLabel={selectedChunkIndices.length > 1}
          />
        ))}
      </div>
    </div>
  );
}
