'use client';

/**
 * TODO: Consider consolidating the project endpoint and workflow history endpoint into a single
 * unified API endpoint with lazy state loading. The current approach fetches full state for all
 * workflows upfront, but the UI only displays one at a time. A unified endpoint with query params
 * like `include_state`, `workflow_type`, and `include_historical` could reduce payload size by ~90%
 * and eliminate redundant data fetching. See API analysis in PR discussion.
 */

import { Button } from '@/components/ui/button';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunHistory } from '@/components/workflows/workflow-run-history';
import { useShare } from '@/context/share-context';
import { ProjectDetailed, startMultipleWorkflowsApiWorkflowsStartMultiplePost } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { getDisplayStatus } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { InfoIcon, PlusIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { useWorkflowSelection } from './use-workflow-selection';
import { WorkflowListSidebar } from './workflow-list-sidebar';
import { WorkflowResultsContent } from './workflow-results-renderer';

interface AnalysesTabProps {
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onNavigateToDocumentExplorer: (chunkIndices?: number[]) => void;
  onNavigateToReferences: () => void;
}

export function AnalysesTab({
  projectDetail,
  readOnly,
  onNavigateToDocumentExplorer,
  onNavigateToReferences,
}: AnalysesTabProps) {
  const projectId = projectDetail.project.id;
  const workflowDetails = projectDetail.workflow_runs ?? [];
  const { shareToken } = useShare();

  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { getWorkflowTypeName, getWorkflowTypeDescription } = useWorkflowTypes();

  const { selectedWorkflowType, selectedWorkflowRun, historyData, handleSelectWorkflowType, handleSelectRun } =
    useWorkflowSelection({
      projectId,
      workflowDetails,
      shareToken,
    });

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

  const filteredWorkflowDetails = workflowDetails;

  const handleStartNewAnalysis = () => setIsConfigDialogOpen(true);

  const handleConfirmStartAnalysis = async (values: WorkflowConfigFormValues) => {
    setIsConfigDialogOpen(false);
    startMultipleWorkflows(values);
  };

  return (
    <div className="flex h-full gap-4">
      <WorkflowListSidebar
        workflowDetails={filteredWorkflowDetails}
        selectedWorkflowType={selectedWorkflowType}
        onSelectWorkflowType={handleSelectWorkflowType}
        onStartNewAnalysis={handleStartNewAnalysis}
        readOnly={readOnly}
      />

      <div className="flex-1 overflow-y-auto">
        {selectedWorkflowRun ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <h2 className="text-xl font-semibold">{getWorkflowTypeName(selectedWorkflowRun.run.type)}</h2>
                  {getWorkflowTypeDescription(selectedWorkflowRun.run.type) && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <InfoIcon className="w-4 h-4 text-muted-foreground cursor-help shrink-0" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        {getWorkflowTypeDescription(selectedWorkflowRun.run.type)}
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <WorkflowRunHistory
                    projectId={projectId}
                    workflowType={selectedWorkflowRun.run.type}
                    currentRunId={selectedWorkflowRun.run.id}
                    onSelectRun={handleSelectRun}
                    historyData={historyData}
                  />
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
              </div>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Status:</span>
                  <StatusIndicator status={getDisplayStatus(selectedWorkflowRun)} />
                </div>
                <div>
                  Last updated {formatDistanceToNow(selectedWorkflowRun.run.last_updated_at, { addSuffix: true })}
                </div>
              </div>
            </div>
            <div className="border-t pt-4 space-y-4">
              <WorkflowResultsContent
                projectDetail={projectDetail}
                workflowRun={selectedWorkflowRun}
                onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
                onNavigateToReferences={onNavigateToReferences}
              />
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
        projectId={projectId}
        onConfirm={handleConfirmStartAnalysis}
        onCancel={() => setIsConfigDialogOpen(false)}
      />
    </div>
  );
}
