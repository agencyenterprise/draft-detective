'use client';

import { WorkflowIssuesList } from '@/components/results/components/workflow-issues-list';
import { EmptyState } from '@/components/shared/empty-state';
import { NavigateToExplorerButton } from '@/components/shared/navigate-to-explorer-button';
import { AccessLevel, Issue, ProjectDetailed, WorkflowRunDetail } from '@/lib/generated-api';
import { isWorkflowCancelled, isWorkflowFailed, isWorkflowProcessing } from '@/lib/workflow-state';
import { Ban, HistoryIcon, Loader2, XCircle } from 'lucide-react';
import { useMemo } from 'react';

interface GenericWorkflowResultsProps {
  project: ProjectDetailed;
  workflowRun: WorkflowRunDetail;
  workflowName: string;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}

/**
 * Results for assessments with no bespoke visualisation: the issues the run
 * reported, or an all-clear when it found none.
 *
 * These used to show only a pointer to the Document Explorer, which made the
 * findings of a completed assessment invisible from the tab that lists it.
 */
export function GenericWorkflowResults({
  project,
  workflowRun,
  workflowName,
  onNavigateToDocumentExplorer,
}: GenericWorkflowResultsProps) {
  const runId = workflowRun.run.id;
  const runType = workflowRun.run.type;
  const allIssues = useMemo(() => project.issues ?? [], [project.issues]);
  const issues = useMemo<Issue[]>(
    () => allIssues.filter((issue) => issue.workflow_run_id === runId),
    [allIssues, runId],
  );

  // Only the newest run of a type keeps its issues; earlier ones are archived
  // and never reach the client. Without this an old run would claim an
  // all-clear it never earned.
  const isSuperseded =
    issues.length === 0 &&
    allIssues.some((issue) => issue.workflow_type === runType && issue.workflow_run_id !== runId);

  if (isWorkflowProcessing(workflowRun)) {
    return (
      <EmptyState
        icon={<Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />}
        message="Assessing Document…"
        description={`The ${workflowName} assessment is currently running. Results will appear here once complete.`}
      />
    );
  }

  if (isWorkflowCancelled(workflowRun)) {
    return (
      <EmptyState
        icon={<Ban className="h-8 w-8 text-muted-foreground mx-auto" />}
        message="Assessment Cancelled"
        description={`The ${workflowName} assessment was cancelled before it could complete.`}
      />
    );
  }

  if (isWorkflowFailed(workflowRun)) {
    return (
      <EmptyState
        icon={<XCircle className="h-8 w-8 text-red-600 mx-auto" />}
        message="Assessment Failed"
        description={
          workflowRun.run.failure_message ??
          `The ${workflowName} assessment failed before it could complete. Please retry it.`
        }
      />
    );
  }

  if (isSuperseded) {
    return (
      <EmptyState
        icon={<HistoryIcon className="h-8 w-8 text-muted-foreground mx-auto" />}
        message="Superseded Run"
        description={`A more recent ${workflowName} run has replaced these results. Select the latest run to see its findings.`}
      />
    );
  }

  return (
    <WorkflowIssuesList
      issues={issues}
      readOnly={project.access_level !== AccessLevel.Write}
      onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
      headerAction={
        <NavigateToExplorerButton
          onClick={() => onNavigateToDocumentExplorer()}
          label="See these findings inline in the Document Explorer"
          className="mt-0 -ml-2"
        />
      }
    />
  );
}
