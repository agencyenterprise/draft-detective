import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';
import { Progress } from '@/components/ui/progress';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  WorkflowRunType,
  getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet,
} from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { getReferenceExtractionWarningStatus, getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useQuery } from '@tanstack/react-query';
import { FileText, Loader2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { FileUploadDialog } from './file-upload-dialog';
import { useFetchAllFromWebMutation, useBatchUploadMutation } from './mutations';
import { useReferenceReviewReferences } from './queries';
import { ReferenceReviewList } from './reference-review-list';

function useScrollToReference() {
  useEffect(() => {
    const scrollToHash = () => {
      const hash = window.location.hash;
      if (hash.startsWith('#reference-')) {
        const element = document.getElementById(hash.slice(1));
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          element.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
          setTimeout(() => {
            element.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
          }, 2000);
        }
      }
    };

    // Scroll on mount and hash changes
    scrollToHash();
    window.addEventListener('hashchange', scrollToHash);
    return () => window.removeEventListener('hashchange', scrollToHash);
  }, []);
}

interface ReferenceReviewTabProps {
  projectId: string;
  readOnly?: boolean;
}

export function ReferenceReviewTab({ projectId, readOnly = false }: ReferenceReviewTabProps) {
  const { project: projectDetail, isLoading } = useProjectDetails(projectId);
  const workflowDetails = projectDetail?.workflow_runs ?? [];
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const [isBatchUploadDialogOpen, setIsBatchUploadDialogOpen] = useState(false);

  useScrollToReference();

  const references = useReferenceReviewReferences(projectDetail ?? undefined);
  const fetchAllFromWebMutation = useFetchAllFromWebMutation(projectId);
  const batchUploadMutation = useBatchUploadMutation(projectId);
  const referenceExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction);
  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);
  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);
  const referenceWarning = getReferenceExtractionWarningStatus(workflowDetails);
  const isExtractionProcessing = isWorkflowProcessing(referenceExtraction);

  const isBatchUploading = batchUploadMutation.isPending;
  const isFetchingAllFromWeb = fetchAllFromWebMutation.isPending || isWorkflowProcessing(referenceDownloader);
  const isProcessingFiles = isWorkflowProcessing(documentProcessing) || isWorkflowProcessing(referenceFileMatching);

  // For batch operations (Fetch All, Upload PDFs buttons): block during any processing
  const disableActions = isProcessingFiles || isWorkflowProcessing(referenceDownloader);

  // For individual cards: only block during ReferenceFileMatching (when file matching could conflict)
  // NOT during DocumentProcessing or ReferenceDownloader (individual fetches shouldn't block other cards)
  const disableIndividualCards = isWorkflowProcessing(referenceFileMatching);

  const { data: progressData } = useQuery({
    queryKey: ['project-workflow-progress', projectId],
    queryFn: () =>
      getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet({
        path: { project_id: projectId },
      }),
    enabled: isExtractionProcessing,
    refetchInterval: 3000,
  });

  const extractionProgress = progressData?.find((p) => p.workflow_run_id === referenceExtraction?.run.id);
  const progressPercent =
    extractionProgress?.total_steps && extractionProgress.total_steps > 0
      ? Math.round((extractionProgress.current_step / extractionProgress.total_steps) * 100)
      : 0;

  const handleOpenDialog = () => {
    setIsConfigDialogOpen(true);
  };

  const handleConfirm = (values: WorkflowConfigFormValues) => {
    const unmatchedReferences = references
      .filter((ref) => ref.status === 'unmatched')
      .map((ref) => ({ reference_id: ref.id, text: ref.text }));
    fetchAllFromWebMutation.mutate(
      { references: unmatchedReferences, openaiApiKey: values.openaiApiKey },
      { onSuccess: () => setIsConfigDialogOpen(false) },
    );
  };

  const handleBatchUploadConfirm = (files: File[], openaiApiKey: string) => {
    batchUploadMutation.mutate({ files, openaiApiKey }, { onSuccess: () => setIsBatchUploadDialogOpen(false) });
  };

  if (isLoading || !projectDetail) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isExtractionProcessing) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-6">
        <div className="relative">
          <div className="w-24 h-24 rounded-full bg-blue-50 flex items-center justify-center">
            <FileText className="w-12 h-12 text-blue-500" />
          </div>
          <div className="absolute inset-0 w-24 h-24 rounded-full border-4 border-blue-200 border-t-blue-500 animate-spin" />
        </div>
        <div className="text-center space-y-3 max-w-md">
          <p className="font-medium text-lg">Finding references in your document...</p>

          {extractionProgress && extractionProgress.total_steps > 0 ? (
            <div className="space-y-2 w-full max-w-xs mx-auto">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  Reference {extractionProgress.current_step} of {extractionProgress.total_steps}
                </span>
                <span className="font-medium text-primary">{progressPercent}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">This usually takes 2-10 minutes depending on document size.</p>
          )}

          <p className="text-xs text-muted-foreground">
            You can leave this page — we&apos;ll keep working in the background.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        type={WorkflowRunType.ReferenceDownloader}
        onConfirm={handleConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <FileUploadDialog
        isOpen={isBatchUploadDialogOpen}
        isUploading={batchUploadMutation.isPending}
        title="Batch Upload Supporting Documents"
        description="Upload multiple supporting documents at once. After upload, the files will be processed and automatically matched to your extracted references."
        multiple={true}
        onConfirm={handleBatchUploadConfirm}
        onCancel={() => setIsBatchUploadDialogOpen(false)}
      />

      <ReferenceReviewList
        references={references}
        projectId={projectId}
        readOnly={readOnly}
        onFetchAll={handleOpenDialog}
        isFetchingAllFromWeb={isFetchingAllFromWeb}
        isBatchUploading={isBatchUploading}
        isProcessingFiles={isProcessingFiles}
        disableActions={disableActions}
        disableIndividualCards={disableIndividualCards}
        onBatchUpload={() => setIsBatchUploadDialogOpen(true)}
      />

      {referenceWarning?.showWarning && (
        <NoReferencesCallout
          sectionsDetected={referenceWarning.sectionsDetected}
          hasErrors={referenceWarning.hasErrors}
        />
      )}
    </div>
  );
}
