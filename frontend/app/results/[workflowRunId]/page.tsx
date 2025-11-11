'use client';

import { Button } from '@/components/ui/button';
import { EditableTitle } from '@/components/ui/editable-title';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ResultsVisualization } from '@/components/wizard/results-step/results-visualization';
import { TabType } from '@/components/wizard/results-step/constants';
import { workflowsApi } from '@/lib/api';
import { ChunkReevaluationResponse, WorkflowRunDetailed, WorkflowRunStatus } from '@/lib/generated-api';
import { DocRenderMode, isDoclingRender } from '@/lib/constants';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { FileText, Layout } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const params = useParams();
  const workflowRunId = params.workflowRunId as string;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');

  const defaultViewMode: DocRenderMode = isDoclingRender() ? 'docling' : 'markdown';
  const [viewMode, setViewMode] = useState<DocRenderMode>(defaultViewMode);

  const {
    data: workflowRun,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['workflowRun', workflowRunId],
    refetchInterval: ({ state }) => (state.data?.run.status === WorkflowRunStatus.Running ? 3000 : false),
    queryFn: () => workflowsApi.getWorkflowRunApiWorkflowRunWorkflowRunIdGet({ workflowRunId }),
  });

  const isProcessing = workflowRun?.run.status === WorkflowRunStatus.Running;

  const isDoclingAvailable = !!(workflowRun?.state?.file?.doclingDocument && workflowRun?.state?.chunkToItems?.mapping);

  const handleChunkReevaluation = (response: ChunkReevaluationResponse) => {
    queryClient.setQueryData(['workflowRun', workflowRunId], (curr: WorkflowRunDetailed) => {
      return {
        ...curr,
        state: { ...curr.state, ...response.state },
      };
    });
  };

  const updateTitleMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      return await workflowsApi.updateWorkflowRunEndpointApiWorkflowRunWorkflowRunIdPatch({
        workflowRunId,
        updateWorkflowRunRequest: { title: newTitle },
      });
    },
    onSuccess: (updatedRun) => {
      queryClient.setQueryData(['workflowRun', workflowRunId], (curr: WorkflowRunDetailed | undefined) => {
        if (!curr) return curr;
        return {
          ...curr,
          run: updatedRun,
        };
      });
      toast.success('Title updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update title: ${error instanceof Error ? error.message : 'Unknown error'}`);
    },
  });

  const handleTitleSave = async (newTitle: string) => {
    await updateTitleMutation.mutateAsync(newTitle);
  };

  useEffect(() => {
    let toastId: string | number | undefined;
    if (isProcessing) {
      toastId = toast.loading('Analysis in progress', {
        description: 'Results will update automatically as sections complete',
      });
    }

    return () => {
      if (toastId) {
        toast.dismiss(toastId);
      }
    };
  }, [isProcessing]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
        <div className="container mx-auto px-4 py-12 max-w-6xl">
          <div className="flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading workflow run...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
        <div className="container mx-auto px-4 py-12 max-w-6xl">
          <div className="flex items-center justify-center">
            <div className="text-center">
              <p className="text-destructive mb-4">{error.message}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!workflowRun) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <div className="container mx-auto px-4 py-12 max-w-6xl">
        <div className="flex items-center justify-between mb-6 gap-4">
          <hgroup className="w-full">
            <EditableTitle
              title={workflowRun.run.title}
              titleClassName="text-2xl font-bold"
              onSave={handleTitleSave}
              isLoading={updateTitleMutation.isPending}
            />
            <h2 className="text-muted-foreground text-sm">
              Workflow Run Results · Created on {format(workflowRun.run.createdAt || new Date(), 'MMM d, yyyy')}
            </h2>
          </hgroup>
          <div className="flex items-center gap-2">
            {/* View Mode Toggle - only show on document-explorer tab */}
            {activeTab === 'document-explorer' && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="inline-flex rounded-md bg-muted/40 p-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setViewMode('markdown')}
                      className={`h-7 w-7 rounded-sm transition-all ${
                        viewMode === 'markdown'
                          ? 'bg-background shadow-xs text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-transparent'
                      }`}
                    >
                      <FileText className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setViewMode('docling')}
                      disabled={!isDoclingAvailable}
                      className={`h-7 w-7 rounded-sm transition-all ${
                        viewMode === 'docling'
                          ? 'bg-background shadow-xs text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-transparent'
                      }`}
                    >
                      <Layout className="size-3.5" />
                    </Button>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="font-semibold mb-1">Document View</p>
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium">Markdown:</span> Simple text-based view of document content
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium">Docling:</span> Visual layout with original document formatting
                    {!isDoclingAvailable && ' (unavailable for this document)'}
                  </p>
                </TooltipContent>
              </Tooltip>
            )}
            <Link href="/">
              <Button variant="outline">Back to Home</Button>
            </Link>
          </div>
        </div>

        <ResultsVisualization
          results={workflowRun.state || undefined}
          onChunkReevaluation={handleChunkReevaluation}
          isProcessing={isProcessing}
          viewMode={viewMode}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
      </div>
    </div>
  );
}
