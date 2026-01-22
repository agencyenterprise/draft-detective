'use client';

import { WorkflowRunDetail, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { SummaryCards } from '../components/summary-cards';
import { useResultsCalculations } from '../hooks/use-results-calculations';

interface SummaryTabProps {
  allWorkflowDetails: WorkflowRunDetail[];
}

export function SummaryTab({ allWorkflowDetails }: SummaryTabProps) {
  const documentProcessing = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceExtraction = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction);
  const referenceFileMatching = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceFileMatching);
  const claimExtraction = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ClaimExtraction);
  const citationDetection = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.CitationDetection);

  const isProcessing = documentProcessing?.run.status !== WorkflowRunStatus.Completed;

  const {
    totalClaims,
    totalCitations,
    totalUnsubstantiated,
    totalChunks,
    chunksWithClaims,
    chunksWithCitations,
    supportedReferences,
  } = useResultsCalculations(
    documentProcessing?.state,
    referenceExtraction?.state,
    claimExtraction?.state,
    citationDetection?.state,
    referenceFileMatching?.state,
  );

  return (
    <div className="space-y-6">
      <SummaryCards
        totalClaims={totalClaims}
        totalCitations={totalCitations}
        totalUnsubstantiated={totalUnsubstantiated}
        isProcessing={isProcessing}
      />

      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Analysis Summary</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Total chunks:</span>
            <span className="ml-2 font-medium">{totalChunks}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Chunks with claims:</span>
            <span className="ml-2 font-medium">{chunksWithClaims}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Chunks with citations:</span>
            <span className="ml-2 font-medium">{chunksWithCitations}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Total references:</span>
            <span className="ml-2 font-medium">{referenceExtraction?.state?.extracted_references?.length || 0}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Supported references:</span>
            <span className="ml-2 font-medium">{supportedReferences}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
