'use client';

import { useState } from 'react';
import { AlertCircle, AlertTriangle, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Callout } from '@/components/ui/callout';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useWizard } from './wizard-context';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { ReferenceReviewTab } from '@/components/results/tabs/reference-review/reference-review-tab';
import { useReferenceReviewReferences } from '@/components/results/tabs/reference-review/queries';
import { ProjectDetailed, WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useApproveAndNavigate } from './use-approve-workflow';

type StepStatus = 'loading' | 'ready' | 'no-references';

function getStepStatus(project: ProjectDetailed | undefined, isLoading: boolean): StepStatus {
  if (isLoading || !project) return 'loading';

  const workflowRuns = project.workflow_runs ?? [];
  const referenceExtraction = getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceExtraction);

  if (!referenceExtraction || isWorkflowProcessing(referenceExtraction)) {
    return 'loading';
  }

  const extractedReferences = referenceExtraction.state?.extracted_references ?? [];
  return extractedReferences.length === 0 ? 'no-references' : 'ready';
}

function LoadingCard() {
  return (
    <Card className="max-w-xl mx-auto">
      <CardContent className="py-12">
        <div className="flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-12 h-12 animate-spin text-primary" />
          <div className="text-center space-y-2">
            <h2 className="text-xl font-semibold">Finding references...</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              This usually takes 2-10 minutes depending on document size.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function StepReferences() {
  const wizard = useWizard();
  const { project, isLoading } = useProjectDetails(wizard.projectId);
  const stepStatus = getStepStatus(project, isLoading);

  if (stepStatus === 'loading') {
    return <LoadingCard />;
  }

  if (stepStatus === 'no-references') {
    return <NoReferencesView project={project!} />;
  }

  return <ReferencesReady project={project!} />;
}

function NoReferencesView({ project }: { project: ProjectDetailed }) {
  const projectId = project.project.id;
  const workflowRuns: WorkflowRunDetail[] = project.workflow_runs ?? [];
  const humanApprovalRun = workflowRuns.find((run) => run.run.type === WorkflowRunType.HumanApproval);

  const approveMutation = useApproveAndNavigate(projectId, humanApprovalRun?.run.id);
  const isDisabled = approveMutation.isPending || approveMutation.isSuccess;

  const buttonText =
    (approveMutation.isSuccess && 'Redirecting...') ||
    (approveMutation.isPending && 'Starting analysis...') ||
    'Run Analysis';

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">No references found</h1>
        <p className="text-muted-foreground">
          We couldn&apos;t find any citations in your document — that&apos;s okay! You can still continue.
        </p>
      </div>

      <Callout variant="warning" icon={AlertCircle} title="Why might this happen?">
        <ul className="list-disc ml-6 mt-2 space-y-1">
          <li>Your document doesn&apos;t have a references or bibliography section</li>
          <li>The citations are formatted in an unusual way</li>
        </ul>
      </Callout>

      <Button onClick={() => approveMutation.mutate()} disabled={isDisabled} size="lg" className="w-full">
        {isDisabled && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
        {buttonText}
      </Button>
    </div>
  );
}

function ReferencesReady({ project }: { project: ProjectDetailed }) {
  const projectId = project.project.id;
  const workflowDetails: WorkflowRunDetail[] = project.workflow_runs ?? [];
  const humanApprovalRun = workflowDetails.find((run) => run.run.type === WorkflowRunType.HumanApproval);

  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);
  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);

  const isDocumentProcessing = isWorkflowProcessing(documentProcessing);
  const isReferenceMatching = isWorkflowProcessing(referenceFileMatching);
  const isReferenceDownloading = isWorkflowProcessing(referenceDownloader);
  const isProcessing = isDocumentProcessing || isReferenceMatching || isReferenceDownloading;

  const approveMutation = useApproveAndNavigate(projectId, humanApprovalRun?.run.id);
  const isDisabled = approveMutation.isPending || approveMutation.isSuccess || isProcessing;

  // Get references to check for unmatched count
  const references = useReferenceReviewReferences(project);
  const unmatchedCount = references.filter((ref) => ref.status === 'unmatched').length;
  const [showWarningDialog, setShowWarningDialog] = useState(false);

  const buttonText =
    (approveMutation.isSuccess && 'Redirecting...') ||
    (approveMutation.isPending && 'Starting analysis...') ||
    (isDocumentProcessing && 'Indexing files...') ||
    (isReferenceMatching && 'Matching references...') ||
    (isReferenceDownloading && 'Fetching references...') ||
    'Run Analysis';

  const handleRunAnalysis = () => {
    if (unmatchedCount > 0 && !isProcessing) {
      setShowWarningDialog(true);
    } else {
      approveMutation.mutate();
    }
  };

  const handleConfirmRunAnalysis = () => {
    setShowWarningDialog(false);
    approveMutation.mutate();
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Add your source documents</h1>
        <p className="text-muted-foreground">
          We found references in your document. To validate claims against their sources, upload the full-text PDFs of
          the cited papers — or let us fetch them from the web.
        </p>
        <p className="text-sm text-muted-foreground">
          <strong>Note:</strong> Claims citing references without matched documents will be skipped during validation.
        </p>
      </div>

      <ReferenceReviewTab projectId={projectId} />

      <Button onClick={handleRunAnalysis} disabled={isDisabled} size="lg" className="w-full">
        {isDisabled && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
        {buttonText}
      </Button>

      <AlertDialog open={showWarningDialog} onOpenChange={setShowWarningDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              </div>
              <AlertDialogTitle>Some references are missing source documents</AlertDialogTitle>
            </div>
            <AlertDialogDescription className="space-y-3">
              <p>
                <strong>
                  {unmatchedCount} reference{unmatchedCount === 1 ? '' : 's'}
                </strong>{' '}
                {unmatchedCount === 1 ? "doesn't" : "don't"} have source PDFs yet.
              </p>
              <p>
                Without source documents, we won&apos;t be able to fully verify claims that cite these references. You
                can still run the analysis, but results may be incomplete.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-row gap-2 sm:justify-end">
            <AlertDialogAction onClick={handleConfirmRunAnalysis} className="bg-red-600 hover:bg-red-700 text-white">
              Continue anyway
            </AlertDialogAction>
            <AlertDialogCancel className="mt-0 bg-primary text-primary-foreground hover:bg-primary/90">
              Go back and add sources
            </AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
