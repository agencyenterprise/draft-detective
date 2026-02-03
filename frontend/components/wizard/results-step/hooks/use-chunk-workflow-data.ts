import { useMemo } from 'react';
import type {
  ChunkSplittingState,
  ClaimExtractionState,
  ExtractedReference,
  ReferenceExtractionState,
  ReferenceValidationItem,
  ReferenceValidationState,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';

export interface ChunkWorkflowData {
  claimExtractionState: ClaimExtractionState | undefined;
  chunkSplittingState: ChunkSplittingState | undefined;
  referenceExtractionState: ReferenceExtractionState | undefined;
  referenceValidationState: ReferenceValidationState | undefined;
}

/**
 * Extract common workflow states needed for chunk analysis
 */
export function useChunkWorkflowData(workflowRuns: WorkflowRunDetail[]): ChunkWorkflowData {
  return useMemo(
    () => ({
      claimExtractionState: getWorkflowRunByType(workflowRuns, WorkflowRunType.ClaimExtraction)?.state,
      chunkSplittingState: getWorkflowRunByType(workflowRuns, WorkflowRunType.ChunkSplitting)?.state,
      referenceExtractionState: getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceExtraction)?.state,
      referenceValidationState: getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceValidation)?.state,
    }),
    [workflowRuns],
  );
}

export interface MatchedReference {
  index: number;
  reference: ExtractedReference;
  validation: ReferenceValidationItem | null;
}

/**
 * Find reference that contains this chunk using chunk_indices from ExtractedReference
 */
export function findReferenceForChunk(
  chunkIndex: number,
  referenceExtractionState: ReferenceExtractionState | undefined,
  referenceValidationState: ReferenceValidationState | undefined,
): MatchedReference | null {
  const extractedRefs = referenceExtractionState?.extracted_references ?? [];
  const validations = referenceValidationState?.reference_validations ?? [];

  // Find reference that includes this chunk in its chunk_indices
  const refIndex = extractedRefs.findIndex((ref) => ref.chunk_indices?.includes(chunkIndex));

  if (refIndex === -1) return null;

  const ref = extractedRefs[refIndex];
  const validation = validations.find((v) => v.reference_id === ref.id) ?? null;

  return { index: refIndex, reference: ref, validation };
}

/**
 * Get claims for a specific chunk
 */
export function getChunkClaims(chunkIndex: number, claimExtractionState: ClaimExtractionState | undefined) {
  const claims =
    claimExtractionState?.claims?.filter((c) => c.chunk_index === chunkIndex).flatMap((c) => c.claims) ?? [];

  return claims.map((claim, originalIndex) => ({ claim, originalIndex }));
}
