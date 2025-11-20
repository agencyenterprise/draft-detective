'use client';

import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Card, CardContent } from '@/components/ui/card';
import { DocRenderMode } from '@/lib/constants';
import { ClaimSubstantiatorStateSummary, DocumentIssue } from '@/lib/generated-api';
import { Loader2 } from 'lucide-react';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ChunkSidebarContent } from '../components/chunk-sidebar-content';
import { DoclingViewer } from '../components/docling-viewer';
import { DocumentIssuesList } from '../components/document-issues-list';
import { DocumentReconstructor } from '../components/document-reconstructor';
import { ErrorsCard } from '../components/errors-card';

interface DocumentExplorerTabProps {
  results: ClaimSubstantiatorStateSummary;
  isProcessing?: boolean;
  viewMode: DocRenderMode;
}

export function DocumentExplorerTab({ results, isProcessing = false, viewMode }: DocumentExplorerTabProps) {
  const pages = results.file?.doclingPages ?? [];
  const chunkToItems = results.chunkToItems?.mapping ?? {};

  const pageImagesBaseUrl = `/api/images/${results.workflowRunId}`;

  const errors = results.errors || [];
  const issues = results.rankedIssues || [];
  const workflowErrors = errors.filter((error) => error.chunkIndex === null || error.chunkIndex === undefined);
  const hasChunks = (results.chunks?.length || 0) > 0;

  // Check if docling view is available
  const isDoclingAvailable = Boolean(pages && pages.length > 0 && Object.keys(chunkToItems).length > 0);

  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(null);
  const selectedChunk = results.chunks?.find((chunk) => chunk.chunkIndex === selectedChunkIndex);
  const sidebarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sidebarRef.current && selectedChunkIndex !== null) {
      sidebarRef.current.scrollTop = 0;
    }
  }, [selectedChunkIndex]);

  const handleChunkSelect = useCallback((chunkIndex: number | null) => {
    setSelectedChunkIndex((curr) => (curr === chunkIndex ? null : chunkIndex));
  }, []);

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
    if (issue.chunkIndex !== undefined && issue.chunkIndex !== null) {
      setSelectedChunkIndex(issue.chunkIndex);
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
                <div className="flex justify-end">
                  <AiGeneratedLabel />
                </div>
                <DocumentIssuesList issues={issues} onSelect={handleSelectIssue} />
              </div>
            )}

            {selectedChunk && selectedChunkIndex !== null && results.workflowRunId && (
              <ChunkSidebarContent
                results={results}
                chunkIndex={selectedChunkIndex}
                workflowRunId={results.workflowRunId}
                isWorkflowRunning={isProcessing}
                onSelectIssue={handleSelectIssue}
                onClearChunkSelection={() => setSelectedChunkIndex(null)}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
