'use client';

import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Card, CardContent } from '@/components/ui/card';
import { useChunkHashNavigation } from '@/lib/chunk-ids';
import { DocRenderMode } from '@/lib/constants';
import { DocumentIssue, SeverityEnum, WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { Loader2 } from 'lucide-react';
import Image from 'next/image';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChunkSidebarContent } from '../components/chunk-sidebar-content';
import { DoclingViewer } from '../components/docling-viewer';
import { DocumentIssuesList } from '../components/document-issues-list';
import { DocumentReconstructor } from '../components/document-reconstructor';
import { ErrorsCard } from '../components/errors-card';
import { filterIssuesBySeverity, SeverityFilter } from '../components/severity-filter';
import { getWorkflowRunByType } from '@/lib/workflow-state';

interface DocumentExplorerTabProps {
  projectId: string;
  allWorkflowDetails: WorkflowRunDetail[];
  issues: DocumentIssue[];
  isProcessing?: boolean;
  viewMode: DocRenderMode;
  readOnly?: boolean;
}

export function DocumentExplorerTab({
  projectId,
  allWorkflowDetails,
  issues,
  isProcessing = false,
  viewMode,
  readOnly = false,
}: DocumentExplorerTabProps) {
  const claimSubstantiatorDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ClaimSubstantiation),
    [allWorkflowDetails],
  );

  const results = claimSubstantiatorDetail?.state;
  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityEnum[]>([]);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const validChunkIndices = useMemo(() => results?.chunks?.map((c) => c.chunk_index), [results?.chunks]);
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

  if (!results) {
    return null;
  }

  const pages = results.file?.docling_pages ?? [];
  const chunkToItems = results.chunk_to_items?.mapping ?? {};

  const pageImagesBaseUrl = `/api/images/${claimSubstantiatorDetail?.run.id}`;

  const errors = results.errors || [];
  const workflowErrors = errors.filter((error) => error.chunk_index === null || error.chunk_index === undefined);
  const hasChunks = (results.chunks?.length || 0) > 0;

  // Check if docling view is available
  const isDoclingAvailable = Boolean(pages && pages.length > 0 && Object.keys(chunkToItems).length > 0);

  const selectedChunk = results.chunks?.find((chunk) => chunk.chunk_index === selectedChunkIndex);
  const filteredIssues = filterIssuesBySeverity(issues, severityFilter);

  if (isProcessing && !hasChunks) {
    return (
      <div className="space-y-4">
        {workflowErrors.length > 0 && <ErrorsCard errors={workflowErrors} />}
        <div className="flex items-center justify-center py-12">
          <div className="text-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
            <p className="text-sm text-muted-foreground">Breaking document into chunks...</p>
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
      {workflowErrors.length > 0 && (
        <div className="mb-2">
          <ErrorsCard errors={workflowErrors} />
        </div>
      )}

      <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
        <div className="col-span-7 leading-relaxed text-sm overflow-hidden flex flex-col">
          {/* Document Viewer */}
          <div className="flex-1 overflow-hidden">
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
                  results={results}
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
            {isProcessing && (
              <Card>
                <CardContent className="flex flex-col justify-center space-y-2 py-8 text-center items-center">
                  <Image
                    src="/undraw_chat-with-ai_ir62.svg"
                    alt="Document Explorer"
                    width={200}
                    height={100}
                    className="mb-8"
                  />
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="h-6 w-6 animate-spin" />
                    <p className="font-medium text-xl">Analyzing document</p>
                  </div>
                  <p className="text-gray-600">
                    You can leave this page and come back later to view the results as the analysis runs in the
                    background.
                  </p>
                </CardContent>
              </Card>
            )}

            {!selectedChunk && (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    {issues.length > 0 &&
                      (filteredIssues.length === issues.length
                        ? `${issues.length} issues`
                        : `${filteredIssues.length} of ${issues.length}`)}
                  </span>
                  {issues.length > 0 && <SeverityFilter value={severityFilter} onChange={setSeverityFilter} />}
                  <AiGeneratedLabel />
                </div>
                {issues.length === 0 && !isProcessing && (
                  <div className="text-sm text-muted-foreground space-y-2">
                    <p>No issues found for this document.</p>
                    <p>You can still view detailled analysis for each chunk by selecting a chunk from the document.</p>
                  </div>
                )}
                <DocumentIssuesList issues={filteredIssues} onSelect={handleSelectIssue} />
              </div>
            )}

            {selectedChunk && selectedChunkIndex !== null && (
              <ChunkSidebarContent
                chunkIndex={selectedChunkIndex}
                projectId={projectId}
                isWorkflowRunning={isProcessing}
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
