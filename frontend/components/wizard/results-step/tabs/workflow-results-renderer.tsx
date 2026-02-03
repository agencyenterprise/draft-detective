'use client';

import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { ErrorsCard } from '@/components/wizard/results-step/components/errors-card';
import { AboutAuthorsResults } from '@/components/workflows/results/about-authors-results';
import { AboutThisResults } from '@/components/workflows/results/about-this-results';
import { AdvocacyToneResults } from '@/components/workflows/results/advocacy-tone-results';
import { CitationSuggesterResults } from '@/components/workflows/results/citation-suggester-results';
import { InferenceValidationV2Results } from '@/components/workflows/results/inference-validation-v2-results';
import { LiteratureReviewResults } from '@/components/workflows/results/literature-review/literature-review-results';
import { LiveReportsResults } from '@/components/workflows/results/live-reports-results';
import { MethodologicalAlignmentResults } from '@/components/workflows/results/methodological-alignment-results';
import { ReferenceDownloaderResults } from '@/components/workflows/results/reference-downloader-results';
import { ResultsExtractorResults } from '@/components/workflows/results/results-extractor-results';
import { ProjectDetailed, WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getCurrentRunErrors, getWorkflowTypeName } from '@/lib/workflow-state';
import { ArrowRight, FileText } from 'lucide-react';

interface WorkflowResultsContentProps {
  projectDetail: ProjectDetailed;
  workflowRun: WorkflowRunDetail;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
  onNavigateToReferences?: () => void;
}

function renderWorkflowResults(
  project: ProjectDetailed,
  workflowRun: WorkflowRunDetail,
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void,
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
    case WorkflowRunType.AdvocacyTone:
      return <AdvocacyToneResults project={project} onNavigateToDocumentExplorer={onNavigateToDocumentExplorer} />;
    case WorkflowRunType.AboutAuthors:
      return <AboutAuthorsResults project={project} onNavigateToDocumentExplorer={onNavigateToDocumentExplorer} />;
    case WorkflowRunType.AboutThis:
      return <AboutThisResults project={project} />;
    case WorkflowRunType.InferenceValidationV2:
      return <InferenceValidationV2Results workflowDetail={workflowRun} />;
    case WorkflowRunType.InferenceValidation:
    case WorkflowRunType.ClaimReferenceValidation:
    case WorkflowRunType.AbbreviationScan:
      return (
        <Callout title="View Results in Document Explorer" variant="info" icon={FileText}>
          <div className="space-y-3">
            <p className="text-sm">
              Results for {getWorkflowTypeName(type)} are displayed in the <strong>Document Explorer</strong> tab.
              Please navigate to the Document Explorer tab to view detailed results organized by document chunks and
              claims.
            </p>
            {onNavigateToDocumentExplorer && (
              <Button onClick={() => onNavigateToDocumentExplorer([])} size="sm" variant="outline" className="mt-2">
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

export function WorkflowResultsContent({
  projectDetail,
  workflowRun,
  onNavigateToDocumentExplorer,
  onNavigateToReferences,
}: WorkflowResultsContentProps) {
  const currentErrors = getCurrentRunErrors(workflowRun);

  return (
    <>
      {currentErrors.length > 0 && <ErrorsCard errors={currentErrors} />}
      {renderWorkflowResults(projectDetail, workflowRun, onNavigateToDocumentExplorer, onNavigateToReferences)}
    </>
  );
}
