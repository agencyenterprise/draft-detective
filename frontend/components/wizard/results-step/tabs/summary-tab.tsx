'use client';

import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { SummaryCards } from '../components/summary-cards';
import { useResultsCalculations } from '../hooks/use-results-calculations';

interface SummaryTabProps {
  projectDetail: ProjectDetailed;
}

export function SummaryTab({ projectDetail }: SummaryTabProps) {
  const workflowDetails = projectDetail.workflow_runs ?? [];
  const chunkSplitting = getWorkflowRunByType(workflowDetails, WorkflowRunType.ChunkSplitting);
  const referenceExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction);
  const claimExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimExtraction);
  const citationDetection = getWorkflowRunByType(workflowDetails, WorkflowRunType.CitationDetection);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);

  const isProcessing = isWorkflowProcessing(chunkSplitting);

  const {
    totalClaims,
    totalCitations,
    totalUnsubstantiated,
    totalChunks,
    chunksWithClaims,
    chunksWithCitations,
    supportedReferences,
  } = useResultsCalculations(
    chunkSplitting?.state,
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
