'use client';

import { useChunkHashNavigation } from '@/lib/chunk-ids';
import { Issue, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import {
  getFilteredIssues,
  getHighlightIssues,
  getPassingCount,
  getResolvedCount,
  getVisibleIssues,
  useDocumentExplorerStore,
} from '@/lib/stores/document-explorer-store';
import {
  getWorkflowErrors,
  getWorkflowRunByType,
  isAnyWorkflowProcessing,
  isWorkflowProcessing,
} from '@/lib/workflow-state';
import { AlertTriangleIcon, Loader2 } from 'lucide-react';
import { useCallback, useMemo, useRef } from 'react';
import { DocumentExplorerSidebar, DocumentExplorerSidebarHandle } from '../components/document-explorer-sidebar';
import { DocumentReconstructor } from '../components/document-reconstructor';

interface DocumentExplorerTabProps {
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onNavigateToAnalyses: () => void;
}

export function DocumentExplorerTab({
  projectDetail,
  readOnly = false,
  onNavigateToAnalyses,
}: DocumentExplorerTabProps) {
  const { selectedChunkIndices, selectChunkIndices, toggleChunk, clearChunkSelection, filter } =
    useDocumentExplorerStore();

  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const issues = useMemo(() => projectDetail.issues ?? [], [projectDetail.issues]);

  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const chunkSplitting = getWorkflowRunByType(workflowDetails, WorkflowRunType.ChunkSplitting);
  const isDocumentProcessing = isWorkflowProcessing(documentProcessing) || isWorkflowProcessing(chunkSplitting);
  const isAnyProcessing = isAnyWorkflowProcessing(workflowDetails);

  const sidebarRef = useRef<DocumentExplorerSidebarHandle>(null);

  const chunks = useMemo(() => chunkSplitting?.state?.chunks ?? [], [chunkSplitting?.state?.chunks]);
  const validChunkIndices = useMemo(() => chunks.map((c) => c.chunk_index), [chunks]);

  const handleHashSelect = useCallback((indices: number[]) => selectChunkIndices(indices), [selectChunkIndices]);
  useChunkHashNavigation(validChunkIndices, handleHashSelect);

  const handleChunkSelect = useCallback(
    (chunkIndex: number | null) => {
      sidebarRef.current?.scrollToTop();

      if (chunkIndex === null) {
        clearChunkSelection();
      } else {
        toggleChunk(chunkIndex);
      }
    },
    [clearChunkSelection, toggleChunk],
  );

  const workflowErrors = useMemo(() => getWorkflowErrors(workflowDetails), [workflowDetails]);
  const hasChunks = useMemo(() => chunks.length > 0, [chunks]);
  const visibleIssues = useMemo(() => getVisibleIssues(issues, filter), [issues, filter]);
  const resolvedCount = useMemo(() => getResolvedCount(issues, selectedChunkIndices), [issues, selectedChunkIndices]);
  const passingCount = useMemo(() => getPassingCount(issues), [issues]);
  const filteredIssues = useMemo(
    () => getFilteredIssues(visibleIssues, filter, selectedChunkIndices),
    [visibleIssues, filter, selectedChunkIndices],
  );
  const highlightIssues = useMemo(() => getHighlightIssues(visibleIssues, filter), [visibleIssues, filter]);

  const handleSelectIssue = useCallback(
    (issue: Issue) => {
      if ((issue.chunk_indices?.length ?? 0) > 0) {
        selectChunkIndices(issue.chunk_indices ?? []);
        sidebarRef.current?.scrollToIssue(issue);
      } else {
        clearChunkSelection();
      }
    },
    [selectChunkIndices, clearChunkSelection],
  );

  if (isDocumentProcessing && !hasChunks) {
    return (
      <div className="space-y-4">
        {workflowErrors.length > 0 && (
          <div className="bg-red-200/40 p-4 rounded-lg text-sm">
            <div className="flex items-center gap-2">
              <AlertTriangleIcon className="w-4 h-4" />
              <span className="font-medium">Unexpected processing errors occurred.</span>
              <span>Please check the</span>
              <button
                onClick={onNavigateToAnalyses}
                className="text-blue-600 hover:text-blue-800 underline font-medium"
              >
                Assessments tab
              </button>
              <span>for details.</span>
            </div>
          </div>
        )}
        <div className="flex items-center justify-center py-12">
          <div className="text-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
            <p className="text-sm text-muted-foreground">Processing document(s)...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {workflowErrors.length > 0 && (
        <div className="mb-4 bg-red-200/40 py-3 px-4 rounded-lg text-sm">
          <div className="flex items-center gap-2">
            <AlertTriangleIcon className="w-4 h-4" />
            <span className="font-medium">Unexpected processing errors occurred.</span>
            <span>Please check the</span>
            <button
              onClick={onNavigateToAnalyses}
              className="text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
            >
              Assessments tab
            </button>
            <span>for details.</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-12 flex-1 min-h-0">
        <div className="col-span-7 leading-relaxed text-sm overflow-hidden flex flex-col">
          <div className="flex-1 overflow-hidden">
            <DocumentReconstructor
              chunks={chunks}
              issues={highlightIssues}
              selectedChunkIndices={selectedChunkIndices}
              onChunkSelect={handleChunkSelect}
            />
          </div>
        </div>

        <DocumentExplorerSidebar
          ref={sidebarRef}
          visibleIssues={visibleIssues}
          filteredIssues={filteredIssues}
          resolvedCount={resolvedCount}
          passingCount={passingCount}
          isAnyProcessing={isAnyProcessing}
          projectDetail={projectDetail}
          readOnly={readOnly}
          onSelectIssue={handleSelectIssue}
        />
      </div>
    </div>
  );
}
