import {
  ChunkSplittingState,
  CitationDetectionState,
  ClaimExtractionState,
  ReferenceExtractionState,
  ReferenceFileMatchingState,
} from '@/lib/generated-api';

export function useResultsCalculations(
  chunkSplitting: ChunkSplittingState | undefined,
  referenceExtraction: ReferenceExtractionState | undefined,
  claimExtraction: ClaimExtractionState | undefined,
  citationDetection: CitationDetectionState | undefined,
  referenceFileMatching?: ReferenceFileMatchingState | undefined,
) {
  if (!chunkSplitting) {
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

  const chunks = chunkSplitting.chunks || [];
  const extractedRefs = referenceExtraction?.extracted_references || [];
  const fileMatches = referenceFileMatching?.matches || [];
  const claims = claimExtraction?.claims || [];
  const citations = citationDetection?.citations || [];

  const totalClaims = claims.reduce((sum, claimResponse) => sum + (claimResponse.claims?.length || 0), 0);
  const totalCitations = citations.length;
  const totalUnsubstantiated = 0; // TODO
  const chunksWithClaims = claims.filter(
    (claim) => claim.chunk_index !== null && claim.chunk_index !== undefined && (claim.claims?.length || 0) > 0,
  ).length;
  const chunksWithCitations = citations.filter(
    (citation) =>
      citation.chunk_index !== null && citation.chunk_index !== undefined && (citation.citations?.length || 0) > 0,
  ).length;

  // Count references that have file matches
  const matchedRefIds = new Set(fileMatches.map((m) => m.reference_id));
  const supportedReferences = extractedRefs.filter((ref) => ref.id && matchedRefIds.has(ref.id)).length;
  const totalChunks = chunks.length;

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
