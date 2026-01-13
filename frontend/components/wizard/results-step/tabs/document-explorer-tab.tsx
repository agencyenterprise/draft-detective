'use client';

import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { SkeletonList } from '@/components/ui/skeleton-list';
import { useChunkHashNavigation } from '@/lib/chunk-ids';
import { DocRenderMode } from '@/lib/constants';
import { DocumentIssue, SeverityEnum, WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import {
  getWorkflowErrors,
  getWorkflowRunByType,
  isAnyWorkflowProcessing,
  isWorkflowProcessing,
} from '@/lib/workflow-state';
import { AlertTriangleIcon, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChunkSidebarContent } from '../components/chunk-sidebar-content';
import { DoclingViewer } from '../components/docling-viewer';
import { DocumentIssuesList } from '../components/document-issues-list';
import { DocumentReconstructor } from '../components/document-reconstructor';
import { filterIssuesBySeverity, SeverityFilter } from '../components/severity-filter';

interface DocumentExplorerTabProps {
  projectId: string;
  allWorkflowDetails: WorkflowRunDetail[];
  issues: DocumentIssue[];
  viewMode: DocRenderMode;
  readOnly?: boolean;
  onNavigateToAnalyses: () => void;
}

export function DocumentExplorerTab({
  allWorkflowDetails,
  issues,
  viewMode,
  readOnly = false,
  onNavigateToAnalyses,
}: DocumentExplorerTabProps) {
  const documentProcessing = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.DocumentProcessing);
  const isDocumentProcessing = isWorkflowProcessing(documentProcessing);
  const isAnyProcessing = isAnyWorkflowProcessing(allWorkflowDetails);

  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityEnum[]>([]);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const chunks = useMemo(() => documentProcessing?.state?.chunks ?? [], [documentProcessing?.state?.chunks]);
  const validChunkIndices = useMemo(() => chunks.map((c) => c.chunk_index), [chunks]);
  const handleHashSelect = useCallback((idx: number) => setSelectedChunkIndex(idx), []);
  useChunkHashNavigation(validChunkIndices, handleHashSelect);

  useEffect(() => {
    if (sidebarRef.current && selectedChunkIndex !== null) {
      sidebarRef.current.scrollTop = 0;
    }
  }, [selectedChunkIndex]);

  const handleChunkSelect = useCallback((chunkIndex: number | null) => {
    setSelectedChunkIndex((curr) => (curr === chunkIndex ? null : chunkIndex));
  }, []);

  const pages = documentProcessing?.state?.file?.docling_pages ?? [];
  const chunkToItems = documentProcessing?.state?.chunk_to_items?.mapping ?? {};
  const pageImagesBaseUrl = `/api/images/${documentProcessing?.run.id}`;

  const workflowErrors = getWorkflowErrors(allWorkflowDetails);
  const hasChunks = chunks.length > 0;

  // Check if docling view is available
  const isDoclingAvailable = Boolean(pages && pages.length > 0 && Object.keys(chunkToItems).length > 0);

  const selectedChunk = chunks.find((chunk) => chunk.chunk_index === selectedChunkIndex);
  const filteredIssues = filterIssuesBySeverity(issues, severityFilter);

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
                Analyses tab
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

  const handleSelectIssue = (issue: DocumentIssue) => {
    if (issue.chunk_index !== undefined && issue.chunk_index !== null) {
      setSelectedChunkIndex(issue.chunk_index);
    } else {
      setSelectedChunkIndex(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
        <div className="col-span-7 leading-relaxed text-sm overflow-hidden flex flex-col">
          {/* Document Viewer */}
          <div className="flex-1 overflow-hidden">
            {workflowErrors.length > 0 && (
              <div className="mb-2 bg-red-200/40 py-3 px-4 rounded-lg text-sm">
                <div className="flex items-center gap-2">
                  <AlertTriangleIcon className="w-4 h-4" />
                  <span className="font-medium">Unexpected processing errors occurred.</span>
                  <span>Please check the</span>
                  <button
                    onClick={onNavigateToAnalyses}
                    className="text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
                  >
                    Analyses tab
                  </button>
                  <span>for details.</span>
                </div>
              </div>
            )}

            {(() => {
              const shouldRenderDocling = viewMode === 'docling' && isDoclingAvailable;

              if (shouldRenderDocling) {
                return (
                  <DoclingViewer
                    pages={pages}
                    chunkToItems={chunkToItems}
                    pageImagesBaseUrl={pageImagesBaseUrl}
                    selectedChunkIndex={selectedChunkIndex}
                    onChunkSelect={handleChunkSelect}
                  />
                );
              }

              return (
                <DocumentReconstructor
                  chunks={chunks}
                  issues={issues}
                  selectedChunkIndex={selectedChunkIndex}
                  onChunkSelect={handleChunkSelect}
                />
              );
            })()}
          </div>
        </div>
        <div ref={sidebarRef} className="col-span-5 bg-muted/50 p-4 rounded-lg text-sm overflow-y-auto">
          <div className="space-y-4 pb-8">
            {!selectedChunk && (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    {issues.length > 0 &&
                      (filteredIssues.length === issues.length
                        ? `${issues.length} issues`
                        : `${filteredIssues.length} of ${issues.length}`)}
                    {issues.length === 0 && isAnyProcessing && 'Finding issues...'}
                  </span>
                  {issues.length > 0 && <SeverityFilter value={severityFilter} onChange={setSeverityFilter} />}
                  <AiGeneratedLabel />
                </div>
                {issues.length === 0 && !isAnyProcessing && (
                  <div className="text-sm text-muted-foreground space-y-2">
                    <p>No issues found for this document.</p>
                    <p>You can still view detailled analysis for each chunk by selecting a chunk from the document.</p>
                  </div>
                )}
                <DocumentIssuesList issues={filteredIssues} onSelect={handleSelectIssue} />
                {isAnyProcessing && <SkeletonList count={3} />}
              </div>
            )}

            {selectedChunk && selectedChunkIndex !== null && (
              <ChunkSidebarContent
                chunkIndex={selectedChunkIndex}
                onClearChunkSelection={() => setSelectedChunkIndex(null)}
                allWorkflowDetails={allWorkflowDetails}
                issues={issues}
                readOnly={readOnly}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
