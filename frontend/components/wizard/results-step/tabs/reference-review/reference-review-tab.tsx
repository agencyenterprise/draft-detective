import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { FileText, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { FileUploadDialog } from './file-upload-dialog';
import { useFetchAllFromWebMutation } from './mutations';
import { useReferenceReviewReferences } from './queries';
import { ReferenceReviewList } from './reference-review-list';
import { useScrollToReference } from './use-scroll-to-reference';

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
  const referenceExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction);
  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);
  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);
  const isExtractionProcessing = isWorkflowProcessing(referenceExtraction);

  const isFetchingAllFromWeb = fetchAllFromWebMutation.isPending || isWorkflowProcessing(referenceDownloader);
  const isProcessingFiles = isWorkflowProcessing(documentProcessing) || isWorkflowProcessing(referenceFileMatching);

  // For batch operations (Fetch All, Upload PDFs buttons): block during any processing
  const disableActions = isProcessingFiles || isWorkflowProcessing(referenceDownloader);

  // For individual cards: only block during ReferenceFileMatching (when file matching could conflict)
  // NOT during DocumentProcessing or ReferenceDownloader (individual fetches shouldn't block other cards)
  const disableIndividualCards = isWorkflowProcessing(referenceFileMatching);

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
          <p className="text-sm text-muted-foreground">This usually takes 2-10 minutes depending on document size.</p>
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
        projectId={projectId}
        onConfirm={handleConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <FileUploadDialog
        isOpen={isBatchUploadDialogOpen}
        title="Batch Upload Supporting Documents"
        description="Upload multiple supporting documents at once. After upload, the files will be processed and automatically matched to your extracted references."
        multiple={true}
        projectId={projectId}
        onCancel={() => setIsBatchUploadDialogOpen(false)}
        onComplete={() => setIsBatchUploadDialogOpen(false)}
      />

      <ReferenceReviewList
        references={references}
        projectId={projectId}
        readOnly={readOnly}
        onFetchAll={handleOpenDialog}
        isFetchingAllFromWeb={isFetchingAllFromWeb}
        isBatchUploading={isBatchUploadDialogOpen}
        isProcessingFiles={isProcessingFiles}
        disableActions={disableActions}
        disableIndividualCards={disableIndividualCards}
        enableInternalScroll={true}
        onBatchUpload={() => setIsBatchUploadDialogOpen(true)}
      />
    </div>
  );
}
