import {
  CitationDetectionState,
  ClaimExtractionState,
  DocumentProcessingState,
  ReferenceExtractionState,
} from '@/lib/generated-api';

export function useResultsCalculations(
  documentProcessing: DocumentProcessingState | undefined,
  referenceExtraction: ReferenceExtractionState | undefined,
  claimExtraction: ClaimExtractionState | undefined,
  citationDetection: CitationDetectionState | undefined,
) {
  if (!documentProcessing) {
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

  const chunks = documentProcessing.chunks || [];
  const references = referenceExtraction?.references || [];
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
  const supportedReferences = references.filter((ref) => ref.has_associated_supporting_document).length;
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
