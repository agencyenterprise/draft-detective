'use client';

import { AwaitingApprovalNotice } from '@/components/results/assessments/awaiting-approval-notice';
import { useWorkflowSelection } from '@/components/results/assessments/use-workflow-selection';
import { WorkflowDuration } from '@/components/results/assessments/workflow-duration';
import { WorkflowResultsContent } from '@/components/results/assessments/workflow-results-renderer';
import { Button } from '@/components/ui/button';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunCost } from '@/components/workflows/workflow-run-cost';
import { useShare } from '@/context/share-context';
import { getErrorMessage } from '@/lib/api-error';
import { ProjectDetailed, startMultipleWorkflowsApiWorkflowsStartMultiplePost } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { isPeerReviewWorkflowType } from '@/lib/peer-review';
import { getDisplayStatus, isWorkflowAwaitingApproval } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { ArrowRight, PlayIcon } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { WorkflowRunHistory } from '@/components/workflows/workflow-run-history';
import { Rail, RailToggle, useRailState } from '../panes';
import { AssessmentRail } from './assessment-rail';

interface AssessmentsTabProps {
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
  onNavigateToReferences: () => void;
  onNavigateToPeerReview?: () => void;
}

/**
 * The assessments tab. The rail lists what has run, the pane
 * shows the selected run's results, and the right-hand pane holds that
 * assessment's history — which the old tab buried in a popover, though it is
 * the only place to see whether findings are falling as the draft is revised.
 */
export function AssessmentsTab({
  projectDetail,
  readOnly,
  onNavigateToDocumentExplorer,
  onNavigateToReferences,
  onNavigateToPeerReview,
}: AssessmentsTabProps) {
  const projectId = projectDetail.project.id;
  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const { shareToken } = useShare();
  const queryClient = useQueryClient();
  const { getWorkflowTypeName, getWorkflowTypeDescription, isWorkflowTypeVisible } = useWorkflowTypes();

  const rail = useRailState();
  const [configOpen, setConfigOpen] = useState(false);

  // Opening on the first assessment beats opening on a prompt to click one.
  const visibleWorkflows = useMemo(
    () => workflowDetails.filter((detail) => isWorkflowTypeVisible(detail.run.type)),
    [workflowDetails, isWorkflowTypeVisible],
  );
  const visibleCount = visibleWorkflows.length;
  const firstVisibleType = visibleWorkflows[0]?.run.type ?? null;

  const { selectedWorkflowType, selectedWorkflowRun, historyData, handleSelectWorkflowType, handleSelectRun } =
    useWorkflowSelection({ projectId, workflowDetails, shareToken, defaultWorkflowType: firstVisibleType });

  const { mutate: startWorkflows } = useMutation({
    mutationFn: (values: WorkflowConfigFormValues) =>
      startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: { project_id: projectId, workflow_types: values.workflowTypes },
      }),
    onSuccess: () => {
      toast.success('Assessments started');
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
    onError: (error) => toast.error(getErrorMessage(error, 'Failed to start assessments')),
  });

  const description = selectedWorkflowRun ? getWorkflowTypeDescription(selectedWorkflowRun.run.type) : null;
  // A run waiting on the user has nothing to re-run and nothing to show; the
  // pane explains what it is waiting for and carries the approve action.
  const awaitingApproval = isWorkflowAwaitingApproval(selectedWorkflowRun ?? undefined);

  return (
    <div className="flex h-full min-h-0">
      <WorkflowConfigDialog
        isOpen={configOpen}
        projectId={projectId}
        onConfirm={(values) => {
          setConfigOpen(false);
          startWorkflows(values);
        }}
        onCancel={() => setConfigOpen(false)}
      />

      <Rail state={rail} label="Assessments">
        <AssessmentRail
          workflowDetails={workflowDetails}
          issues={projectDetail.issues ?? []}
          selectedWorkflowType={selectedWorkflowType}
          onSelectWorkflowType={(type) => {
            handleSelectWorkflowType(type);
            rail.close();
          }}
          onStartNewAssessment={() => setConfigOpen(true)}
          readOnly={readOnly}
        />
      </Rail>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center gap-2 border-b px-2">
          <RailToggle state={rail} label="Assessments" />

          {/* The count, not the selected name: the pane's own heading says which
              assessment this is, one line below. */}
          <span className="min-w-0 truncate text-xs text-muted-foreground">
            {visibleCount} {visibleCount === 1 ? 'assessment' : 'assessments'}
          </span>

          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            {selectedWorkflowRun && (
              <WorkflowRunHistory
                projectId={projectId}
                workflowType={selectedWorkflowRun.run.type}
                currentRunId={selectedWorkflowRun.run.id}
                onSelectRun={handleSelectRun}
                historyData={historyData}
                size="xs"
                tooltip="Every time this assessment has run. Pick one to read its results."
              />
            )}

            {!readOnly &&
              selectedWorkflowRun &&
              !awaitingApproval &&
              // Peer-review assessments are sequenced from their own tab;
              // re-running one here could produce a guard report, not a result.
              (isPeerReviewWorkflowType(selectedWorkflowRun.run.type) ? (
                onNavigateToPeerReview && (
                  <Button size="xs" variant="outline" onClick={onNavigateToPeerReview}>
                    Manage in Peer Review
                    <ArrowRight className="size-3" />
                  </Button>
                )
              ) : (
                <StartWorkflowButton
                  type={selectedWorkflowRun.run.type}
                  projectId={projectId}
                  workflow={selectedWorkflowRun.run}
                  size="xs"
                  startLabel={
                    selectedWorkflowRun.run.started_at ? (
                      <>
                        {/* The name only where it fits: an assessment called
                            "Claim Reference Validation" is wider than a phone. */}
                        Re-run
                        <span className="hidden sm:inline"> {getWorkflowTypeName(selectedWorkflowRun.run.type)}</span>
                      </>
                    ) : undefined
                  }
                  tooltip="Running an assessment again replaces what the document explorer shows for it."
                  onConfirm={() =>
                    startMultipleWorkflowsApiWorkflowsStartMultiplePost({
                      body: { project_id: projectId, workflow_types: [selectedWorkflowRun.run.type] },
                    })
                  }
                />
              ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {selectedWorkflowRun ? (
            <div className="mx-auto max-w-5xl px-6 py-5">
              <header className="border-b pb-4">
                <h1 className="text-base font-semibold tracking-tight">
                  {getWorkflowTypeName(selectedWorkflowRun.run.type)}
                </h1>
                {description && <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{description}</p>}
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <StatusIndicator status={getDisplayStatus(selectedWorkflowRun)} />
                  <span>
                    Last updated {formatDistanceToNow(selectedWorkflowRun.run.last_updated_at, { addSuffix: true })}
                  </span>
                  <WorkflowDuration run={selectedWorkflowRun.run} />
                  {selectedWorkflowRun.cost && (
                    <WorkflowRunCost key={selectedWorkflowRun.run.id} cost={selectedWorkflowRun.cost} />
                  )}
                </div>
              </header>

              {/* The result components are shared with the add-in and the admin pages,
                  which run a larger type scale than this chrome. Scaling the
                  subtree beats forking them or changing sizes those depend on. */}
              <div className="text-scale-compact space-y-4 pt-4">
                {awaitingApproval ? (
                  <AwaitingApprovalNotice
                    projectDetail={projectDetail}
                    workflowRun={selectedWorkflowRun}
                    readOnly={readOnly}
                    onNavigateToReferences={onNavigateToReferences}
                  />
                ) : (
                  <WorkflowResultsContent
                    projectDetail={projectDetail}
                    workflowRun={selectedWorkflowRun}
                    onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
                    onNavigateToReferences={onNavigateToReferences}
                  />
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-8">
              <div className="max-w-sm space-y-2 text-center">
                <p className="text-sm font-medium">No assessments yet</p>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Assessments read the document and report what they find as issues in the explorer.
                </p>
                {!readOnly && (
                  <Button size="sm" className="mt-1" onClick={() => setConfigOpen(true)}>
                    <PlayIcon className="size-3.5" />
                    Run an assessment
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
