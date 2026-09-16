'use client';

import { Callout } from '@/components/ui/callout';
import { ErrorsCard } from '@/components/results/components/errors-card';
import { GenericWorkflowResults } from '@/components/results/components/generic-workflow-results';
import { AboutThisGerResults } from '@/components/workflows/results/about-this-ger-results';
import { ReferenceDownloaderResults } from '@/components/workflows/results/reference-downloader-results';
import { ReferenceValidationV2Results } from '@/components/workflows/results/reference-validation-v2-results';
import { Reviewer2Results } from '@/components/workflows/results/reviewer-2-results';
import { SimpleDeepAgentResults } from '@/components/workflows/results/simple-deep-agent-results';
import {
  ProjectDetailed,
  SimpleDeepAgentState,
  WorkflowRunDetail,
  WorkflowRunType,
  WorkflowStateStatus,
} from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { getCurrentRunErrors, WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { FlaskConicalIcon } from 'lucide-react';
import { StaleWorkflowStateNotice } from '@/components/results/components/stale-workflow-state-notice';

function InternalWorkflowResults({ workflowName }: { workflowName: string }) {
  return (
    <Callout title="Internal Workflow" variant="info" icon={FlaskConicalIcon}>
      <p className="text-sm">
        <strong>{workflowName}</strong> runs automatically as a dependency of other assessments and is not meant to be
        triggered directly — its results feed into higher-level workflows that surface findings in their own result
        views.
      </p>
    </Callout>
  );
}

interface WorkflowResultsContentProps {
  projectDetail: ProjectDetailed;
  workflowRun: WorkflowRunDetail;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
  onNavigateToReferences: () => void;
}

function renderWorkflowResults(
  project: ProjectDetailed,
  workflowRun: WorkflowRunDetail,
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void,
  getWorkflowTypeName: (type: WorkflowRunType) => string,
) {
  const { type } = workflowRun.run;
  const { state } = workflowRun;

  if (!state) {
    // A completed run whose saved state no longer matches the assessment's
    // current model is a different situation from a run that never produced
    // one: the data exists and is recoverable, so say so and offer it.
    if (workflowRun.state_status === WorkflowStateStatus.SchemaMismatch) {
      return (
        <StaleWorkflowStateNotice workflowRunId={String(workflowRun.run.id)} workflowName={getWorkflowTypeName(type)} />
      );
    }
    return <div className="p-4 text-center text-muted-foreground">No results available for this workflow run</div>;
  }

  switch (type) {
    case WorkflowRunType.ReferenceDownloader:
      return <ReferenceDownloaderResults workflowDetail={workflowRun} />;
    case WorkflowRunType.AboutThisGer:
      return <AboutThisGerResults workflowDetail={workflowRun} />;
    case WorkflowRunType.ClaimReferenceValidationV2:
    case WorkflowRunType.AbbreviationScanV2:
      return (
        <GenericWorkflowResults
          project={project}
          workflowRun={workflowRun}
          workflowName={getWorkflowTypeName(type)}
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      );
    case WorkflowRunType.Reviewer2:
      return <Reviewer2Results workflowDetail={workflowRun} />;
    case WorkflowRunType.ReferenceValidationV2:
      return <ReferenceValidationV2Results workflowDetail={workflowRun} />;
    case WorkflowRunType.MethodologicalAlignment:
    case WorkflowRunType.ResultsExtraction:
    case WorkflowRunType.DocumentStructure:
    case WorkflowRunType.FiguresTablesCheck:
    case WorkflowRunType.InferenceValidationV2:
    case WorkflowRunType.RecommendationCheck:
    case WorkflowRunType.RevisionPlanningSummary:
    case WorkflowRunType.ReviewerResponseMemos:
    case WorkflowRunType.ReviewerCoverageReport:
    case WorkflowRunType.AdvocacyToneV2:
    case WorkflowRunType.LiteratureReviewV2:
    case WorkflowRunType.LiveReportsV2:
      return (
        <SimpleDeepAgentResults
          project={project}
          workflowDetail={workflowRun as WorkflowRunDetailTyped<SimpleDeepAgentState>}
          workflowName={getWorkflowTypeName(type)}
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      );
    default:
      // No case above: a skill-declared workflow, which has no code of its own.
      // Those run on the shared deep-agent state, so they get its results view
      // (report plus issues) without a per-type entry here.
      return (
        <SimpleDeepAgentResults
          project={project}
          workflowDetail={workflowRun as WorkflowRunDetailTyped<SimpleDeepAgentState>}
          workflowName={getWorkflowTypeName(type)}
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      );
  }
}

export function WorkflowResultsContent({
  projectDetail,
  workflowRun,
  onNavigateToDocumentExplorer,
}: WorkflowResultsContentProps) {
  const currentErrors = getCurrentRunErrors(workflowRun);
  const { getWorkflowTypeName, isWorkflowTypeVisible } = useWorkflowTypes();
  const workflowName = getWorkflowTypeName(workflowRun.run.type);

  if (!isWorkflowTypeVisible(workflowRun.run.type)) {
    return (
      <>
        {currentErrors.length > 0 && <ErrorsCard errors={currentErrors} />}
        <InternalWorkflowResults workflowName={workflowName} />
      </>
    );
  }

  return (
    <>
      {currentErrors.length > 0 && <ErrorsCard errors={currentErrors} />}
      {renderWorkflowResults(projectDetail, workflowRun, onNavigateToDocumentExplorer, getWorkflowTypeName)}
    </>
  );
}
