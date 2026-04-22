import { useFeedback } from './use-feedback';

/**
 * Type-safe wrapper for claim-level feedback
 *
 * Uses the generic useFeedback hook with claim-specific entity path
 */
export function useClaimFeedback(workflowRunId: string, chunkIndex: number, claimIndex: number) {
  return useFeedback(workflowRunId, {
    chunk_index: chunkIndex,
    claim_index: claimIndex,
  });
}
