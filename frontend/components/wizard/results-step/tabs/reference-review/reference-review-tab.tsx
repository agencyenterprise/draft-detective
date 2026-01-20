import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useState } from 'react';
import { useFetchAllFromWebMutation } from './mutations';
import { useReferenceReviewReferences } from './queries';
import { ReferenceReviewList } from './reference-review-list';

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

  return (
    <>
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
    </>
  );
}
