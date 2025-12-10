import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';

export function useResultsCalculations(detailedResults: ClaimSubstantiatorStateSummary | undefined) {
  if (!detailedResults) {
    return {
      totalClaims: 0,
      totalCitations: 0,
      totalUnsubstantiated: 0,
      totalChunks: 0,
      chunksWithClaims: 0,
      chunksWithCitations: 0,
      supportedReferences: 0,
    };
  }

  const totalClaims = detailedResults.chunks?.reduce((sum, chunk) => sum + (chunk.claims_count || 0), 0) || 0;

  const totalCitations = detailedResults.chunks?.reduce((sum, chunk) => sum + (chunk.citations_count || 0), 0) || 0;

  const totalUnsubstantiated = 0;

  const chunksWithClaims = detailedResults.chunks?.filter((chunk) => chunk.has_claims).length || 0;

  const chunksWithCitations = detailedResults.chunks?.filter((chunk) => chunk.has_citations).length || 0;

  const supportedReferences =
    detailedResults.references?.filter((ref) => ref.has_associated_supporting_document).length || 0;

  const totalChunks = detailedResults.chunks?.length || 0;

  return {
    totalClaims,
    totalCitations,
    totalUnsubstantiated,
    totalChunks,
    chunksWithClaims,
    chunksWithCitations,
    supportedReferences,
  };
}
