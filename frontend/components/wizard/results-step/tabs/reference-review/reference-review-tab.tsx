import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getReferenceExtractionWarningStatus, getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useState } from 'react';
import { useFetchAllFromWebMutation } from './mutations';
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

  const references = useReferenceReviewReferences(projectDetail);
  const fetchAllFromWebMutation = useFetchAllFromWebMutation(projectId);
  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);

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

  const referenceWarning = getReferenceExtractionWarningStatus(workflowDetails);

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
