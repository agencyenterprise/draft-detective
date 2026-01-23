import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getReferenceExtractionWarningStatus, getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { FileText } from 'lucide-react';
import { useState } from 'react';
import { FileUploadDialog } from './file-upload-dialog';
import { useFetchAllFromWebMutation, useBatchUploadMutation } from './mutations';
import { useReferenceReviewReferences } from './queries';
import { ReferenceReviewList } from './reference-review-list';

interface ReferenceReviewTabProps {
  projectDetail: ProjectDetailed;
  readOnly: boolean;
}

export function ReferenceReviewTab({ projectDetail, readOnly }: ReferenceReviewTabProps) {
  const projectId = projectDetail.project.id;
  const workflowDetails = projectDetail.workflow_runs ?? [];
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const [isBatchUploadDialogOpen, setIsBatchUploadDialogOpen] = useState(false);

  const references = useReferenceReviewReferences(projectDetail);
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

  const disableActions =
    isWorkflowProcessing(documentProcessing) ||
    isWorkflowProcessing(referenceDownloader) ||
    isWorkflowProcessing(referenceFileMatching);

  const handleOpenDialog = () => {
    setIsConfigDialogOpen(true);
  };

  const handleConfirm = (values: WorkflowConfigFormValues) => {
    const unmatchedReferences = references
      .filter((ref) => ref.status === 'unmatched')
      .map((ref) => ({ index: ref.index, text: ref.text }));
    fetchAllFromWebMutation.mutate(
      { references: unmatchedReferences, openaiApiKey: values.openaiApiKey },
      { onSuccess: () => setIsConfigDialogOpen(false) },
    );
  };

  const handleBatchUploadConfirm = (files: File[], openaiApiKey: string) => {
    batchUploadMutation.mutate({ files, openaiApiKey }, { onSuccess: () => setIsBatchUploadDialogOpen(false) });
  };

  if (isExtractionProcessing) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-6">
        <div className="relative">
          <div className="w-24 h-24 rounded-full bg-blue-50 flex items-center justify-center">
            <FileText className="w-12 h-12 text-blue-500" />
          </div>
          <div className="absolute inset-0 w-24 h-24 rounded-full border-4 border-blue-200 border-t-blue-500 animate-spin" />
        </div>
        <div className="text-center space-y-2">
          <p className="font-medium text-lg">Extracting references...</p>
          <p className="text-sm text-muted-foreground">
            This should take approximately 10 minutes for a document with 100 reference list items.
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
        disableActions={disableActions}
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
