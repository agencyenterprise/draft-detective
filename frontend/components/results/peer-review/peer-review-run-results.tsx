'use client';

import { TabError, TabLoading } from '@/components/results/tab-status';
import { SimpleDeepAgentResults } from '@/components/workflows/results/simple-deep-agent-results';
import { AccessLevel, ProjectOverview, SimpleDeepAgentState, WorkflowRunSummary } from '@/lib/generated-api';
import { useProjectIssues, useWorkflowRunDetail } from '@/lib/hooks/use-project-data';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';

interface PeerReviewRunResultsProps {
  /** The overview of the revision the run belongs to, which is where its issues are. */
  overview: ProjectOverview;
  run: WorkflowRunSummary;
  workflowName: string;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}

/** One peer-review step's results, with the run's state fetched when the step is shown. */
export function PeerReviewRunResults({
  overview,
  run,
  workflowName,
  onNavigateToDocumentExplorer,
}: PeerReviewRunResultsProps) {
  const projectId = overview.project.id;
  const { data: detail, error: detailError } = useWorkflowRunDetail(projectId, run);
  const { data: issues, error: issuesError } = useProjectIssues(overview);

  const error = detailError ?? issuesError;
  if (error) return <TabError what="these results" error={error} />;
  if (!detail || !issues) return <TabLoading label="Loading results..." />;

  return (
    <SimpleDeepAgentResults
      issues={issues}
      canEditIssues={overview.access_level === AccessLevel.Write}
      workflowDetail={detail as WorkflowRunDetailTyped<SimpleDeepAgentState>}
      workflowName={workflowName}
      onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
    />
  );
}
