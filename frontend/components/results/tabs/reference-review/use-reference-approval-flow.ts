'use client';

import { useApproveWorkflow } from '@/components/analysis-wizard/use-approve-workflow';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing, needsHumanApproval } from '@/lib/workflow-state';
import { useState } from 'react';
import { useReferenceReviewReferences } from './queries';

/**
 * Shared approve / unmatched-warning logic for the References tab and the project header callout.
 */
export function useReferenceApprovalFlow(projectDetail: ProjectDetailed | undefined, projectId: string) {
  const workflowDetails = projectDetail?.workflow_runs ?? [];
  const [showUnmatchedWarning, setShowUnmatchedWarning] = useState(false);

  const references = useReferenceReviewReferences(projectDetail);

  const referenceExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction);
  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);
  const isExtractionProcessing = isWorkflowProcessing(referenceExtraction);

  const isProcessingFiles = isWorkflowProcessing(documentProcessing) || isWorkflowProcessing(referenceFileMatching);

  const hasPendingApproval = needsHumanApproval(workflowDetails);
  const humanApprovalRun = workflowDetails.find((run) => run.run.type === WorkflowRunType.HumanApproval);
  const approveMutation = useApproveWorkflow(projectId, humanApprovalRun?.run.id);

  const unmatchedCount = references.filter((ref) => ref.status === 'unmatched').length;
  const isApproveDisabled =
    approveMutation.isPending || approveMutation.isSuccess || isProcessingFiles || isExtractionProcessing;

  /** Spinner only while the approve request is in flight — not while docs/refs are still processing. */
  const showApproveButtonSpinner = approveMutation.isPending;

  const approveButtonText =
    (approveMutation.isSuccess && 'Starting analysis...') ||
    (approveMutation.isPending && 'Starting analysis...') ||
    (isProcessingFiles && 'Processing files...') ||
    (isExtractionProcessing && 'Extracting references...') ||
    'Approve and Start Analysis';

  const handleApprove = () => {
    if (unmatchedCount > 0 && !isProcessingFiles) {
      setShowUnmatchedWarning(true);
    } else {
      approveMutation.mutate();
    }
  };

  const handleConfirmApprove = () => {
    setShowUnmatchedWarning(false);
    approveMutation.mutate();
  };

  return {
    hasPendingApproval,
    showUnmatchedWarning,
    setShowUnmatchedWarning,
    handleApprove,
    handleConfirmApprove,
    isApproveDisabled,
    showApproveButtonSpinner,
    approveButtonText,
    unmatchedCount,
    isProcessingFiles,
    isExtractionProcessing,
  };
}
