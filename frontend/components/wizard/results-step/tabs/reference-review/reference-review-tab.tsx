import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getReferenceExtractionWarningStatus, getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useState } from 'react';
import { useFetchAllFromWebMutation } from './mutations';
import { useReferenceReviewReferences } from './queries';
import { ReferenceReviewList } from './reference-review-list';
import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';

interface ReferenceReviewTabProps {
  projectId: string;
  allWorkflowDetails: WorkflowRunDetail[];
  readOnly: boolean;
}

export function ReferenceReviewTab({ projectId, allWorkflowDetails, readOnly }: ReferenceReviewTabProps) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);

  const references = useReferenceReviewReferences(projectId);
  const fetchAllFromWebMutation = useFetchAllFromWebMutation(projectId);
  const referenceDownloader = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceDownloader);

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

  const referenceWarning = getReferenceExtractionWarningStatus(allWorkflowDetails);

  return (
    <div className="space-y-4">
      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        type={WorkflowRunType.ReferenceDownloader}
        onConfirm={handleConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <ReferenceReviewList
        references={references}
        projectId={projectId}
        readOnly={readOnly}
        onFetchAll={handleOpenDialog}
        isFetchingAllFromWeb={fetchAllFromWebMutation.isPending || isWorkflowProcessing(referenceDownloader)}
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
