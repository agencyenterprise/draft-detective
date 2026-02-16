import type { ClaimExtractionState, WorkflowRunDetail } from '@/lib/generated-api';
import { getClaimExtractionDetail } from '@/lib/workflow-state';
import { useMemo } from 'react';

/**
 * Extract common workflow states needed for chunk analysis
 */
export function useChunkWorkflowData(workflowRuns: WorkflowRunDetail[]) {
  return useMemo(
    () => ({
      claimExtractionState: getClaimExtractionDetail(workflowRuns)?.state,
    }),
    [workflowRuns],
  );
}

/**
 * Get claims for a specific chunk
 */
export function getChunkClaims(chunkIndex: number, claimExtractionState: ClaimExtractionState | undefined) {
  const claims =
    claimExtractionState?.claims?.filter((c) => c.chunk_index === chunkIndex).flatMap((c) => c.claims) ?? [];

  return claims.map((claim, originalIndex) => ({ claim, originalIndex }));
}
