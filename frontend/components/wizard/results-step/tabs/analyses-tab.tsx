'use client';

import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ErrorsCard } from '@/components/wizard/results-step/components/errors-card';
import { CitationSuggesterResults } from '@/components/workflows/results/citation-suggester-results';
import { LiteratureReviewResults } from '@/components/workflows/results/literature-review/literature-review-results';
import { LiveReportsResults } from '@/components/workflows/results/live-reports-results';
import { MethodologicalAlignmentResults } from '@/components/workflows/results/methodological-alignment-results';
import { ReferenceDownloaderResults } from '@/components/workflows/results/reference-downloader-results';
import { ResultsExtractorResults } from '@/components/workflows/results/results-extractor-results';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  ProjectDetailed,
  WorkflowRunDetail,
  WorkflowRunType,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
} from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import { getWorkflowTypeName } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { AlertTriangleIcon, ArrowRight, FileText, PlusIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

interface AnalysesTabProps {
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onNavigateToDocumentExplorer?: () => void;
  onNavigateToReferences?: () => void;
}

function renderWorkflowResults(
  project: ProjectDetailed,
  workflowRun: WorkflowRunDetail,
  onNavigateToDocumentExplorer?: () => void,
  onNavigateToReferences?: () => void,
) {
  const { type } = workflowRun.run;
  const { state } = workflowRun;

  if (!state) {
    return <div className="p-4 text-center text-muted-foreground">No results available for this workflow run</div>;
  }

  switch (type) {
    case WorkflowRunType.MethodologicalAlignment:
      return <MethodologicalAlignmentResults workflowDetail={workflowRun} />;
    case WorkflowRunType.LiveReports:
      return <LiveReportsResults project={project} workflowDetail={workflowRun} />;
    case WorkflowRunType.LiteratureReview:
      return <LiteratureReviewResults workflowDetail={workflowRun} />;
    case WorkflowRunType.CitationSuggester:
      return <CitationSuggesterResults project={project} />;
    case WorkflowRunType.ReferenceDownloader:
      return <ReferenceDownloaderResults workflowDetail={workflowRun} />;
    case WorkflowRunType.ResultsExtraction:
      return <ResultsExtractorResults workflowDetail={workflowRun} />;
    case WorkflowRunType.InferenceValidation:
    case WorkflowRunType.ClaimReferenceValidation:
      return (
        <Callout title="View Results in Document Explorer" variant="info" icon={FileText}>
          <div className="space-y-3">
            <p className="text-sm">
              Results for {getWorkflowTypeName(type)} are displayed in the <strong>Document Explorer</strong> tab.
              Please navigate to the Document Explorer tab to view detailed results organized by document chunks and
              claims.
            </p>
            {onNavigateToDocumentExplorer && (
              <Button onClick={onNavigateToDocumentExplorer} size="sm" variant="outline" className="mt-2">
                Go to Document Explorer
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
          </div>
        </Callout>
      );
    case WorkflowRunType.ReferenceValidation:
      return (
        <Callout title="View Results in References" variant="info" icon={FileText}>
          <div className="space-y-3">
            <p className="text-sm">
              Results for {getWorkflowTypeName(type)} are displayed in the <strong>References</strong> tab. Please
              navigate to the References tab to view detailed results organized by document chunks and claims.
            </p>
            {onNavigateToReferences && (
              <Button onClick={onNavigateToReferences} size="sm" variant="outline" className="mt-2">
                Go to References
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
          </div>
        </Callout>
      );
    default:
      return (
        <div className="p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">
            Results visualization for {getWorkflowTypeName(type)} is not yet implemented.
          </p>
        </div>
      );
  }
}

export function AnalysesTab({
  projectDetail,
  readOnly,
  onNavigateToDocumentExplorer,
  onNavigateToReferences,
}: AnalysesTabProps) {
  const projectId = projectDetail.project.id;
  const workflowDetails = projectDetail.workflow_runs ?? [];
  const [selectedWorkflowRunId, setSelectedWorkflowRunId] = useState<string | null>(null);
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  const { mutate: startMultipleWorkflows } = useMutation({
    mutationFn: async (values: WorkflowConfigFormValues) => {
      return await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: values.workflowTypes,
          openai_api_key: values.openaiApiKey,
        },
      });
    },
    onSuccess: () => {
      toast.success('Workflows started');
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to start workflows');
    },
  });

  const selectedWorkflowRun = workflowDetails.find((workflowDetail) => workflowDetail.run.id === selectedWorkflowRunId);
  const filteredWorkflowDetails = workflowDetails.filter((workflowDetail) =>
    isWorkflowTypeVisible(workflowDetail.run.type),
  );

  const handleStartNewAnalysis = () => {
    setIsConfigDialogOpen(true);
  };

  const handleConfirmStartAnalysis = async (values: WorkflowConfigFormValues) => {
    setIsConfigDialogOpen(false);
    startMultipleWorkflows(values);
  };

  return (
    <div className="flex h-full gap-4">
      {/* Left column - Workflow runs list */}
      <div className="w-1/4 overflow-y-auto border-r pr-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Analyses</h3>
            {!readOnly && (
              <Button size="xs" variant="outline" onClick={handleStartNewAnalysis}>
                <PlusIcon className="size-3" />
                New Analysis
              </Button>
            )}
          </div>
          {filteredWorkflowDetails.map((workflowDetail) => (
            <button
              key={workflowDetail.run.id}
              onClick={() => setSelectedWorkflowRunId(workflowDetail.run.id)}
              className={cn(
                'w-full text-left p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer shadow-xs',
                selectedWorkflowRun?.run.id === workflowDetail.run.id && 'bg-muted border-primary shadow',
              )}
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2 font-medium text-sm">
                  {getWorkflowTypeName(workflowDetail.run.type)}
                  {workflowDetail.state?.errors && workflowDetail.state.errors.length > 0 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <AlertTriangleIcon className="w-4 h-4 text-destructive cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent>
                        This workflow completed with {workflowDetail.state.errors.length} error
                        {workflowDetail.state.errors.length > 1 ? 's' : ''}. Please check them and try again.
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>
                <div className="flex items-center gap-2 justify-between">
                  <div className="text-xs text-muted-foreground">
                    {formatDistanceToNow(workflowDetail.run.last_updated_at, { addSuffix: true })}
                  </div>
                  <StatusIndicator status={workflowDetail.run.status} />
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right column - Selected workflow results */}
      <div className="flex-1 overflow-y-auto">
        {selectedWorkflowRun ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-xl font-semibold">{getWorkflowTypeName(selectedWorkflowRun.run.type)}</h2>
                {!readOnly && (
                  <StartWorkflowButton
                    type={selectedWorkflowRun.run.type}
                    projectId={projectId}
                    workflow={selectedWorkflowRun.run}
                    onConfirm={async (values: WorkflowConfigFormValues) => {
                      return await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
                        body: {
                          project_id: projectId,
                          workflow_types: [selectedWorkflowRun.run.type],
                          openai_api_key: values.openaiApiKey,
                        },
                      });
                    }}
                  />
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Status:</span>
                  <StatusIndicator status={selectedWorkflowRun.run.status} />
                </div>
                <div>
                  Last updated {formatDistanceToNow(selectedWorkflowRun.run.last_updated_at, { addSuffix: true })}
                </div>
              </div>
            </div>
            <div className="border-t pt-4 space-y-4">
              {selectedWorkflowRun.state?.errors && selectedWorkflowRun.state.errors.length > 0 && (
                <ErrorsCard errors={selectedWorkflowRun.state.errors} />
              )}
              {renderWorkflowResults(
                projectDetail,
                selectedWorkflowRun,
                onNavigateToDocumentExplorer,
                onNavigateToReferences,
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-32">
            <p className="text-muted-foreground flex items-center gap-2">
              {readOnly && <>Select an analysis to view its results</>}
              {!readOnly && (
                <>
                  Select an analysis to view its results or
                  <Button size="xs" variant="default" onClick={handleStartNewAnalysis}>
                    <PlusIcon className="size-3" />
                    Start a new analysis
                  </Button>
                </>
              )}
            </p>
          </div>
        )}
      </div>

      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        onConfirm={handleConfirmStartAnalysis}
        onCancel={() => setIsConfigDialogOpen(false)}
      />
    </div>
  );
}
