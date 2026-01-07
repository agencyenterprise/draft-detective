import {
  Reference,
  CitationSuggestionResultWithClaimIndex,
  ConfidenceInRecommendation,
  PublicationQuality,
} from './generated-api';

/**
 * Ranking scores for confidence levels in citation recommendations.
 * Higher scores indicate higher confidence.
 */
const confidenceRank: Record<ConfidenceInRecommendation, number> = {
  [ConfidenceInRecommendation.High]: 3,
  [ConfidenceInRecommendation.Medium]: 2,
  [ConfidenceInRecommendation.Low]: 1,
};

/**
 * Ranking scores for publication quality levels.
 * Higher scores indicate higher quality publications.
 */
const qualityRank: Record<PublicationQuality, number> = {
  [PublicationQuality.HighImpactPublication]: 4,
  [PublicationQuality.MediumImpactPublication]: 3,
  [PublicationQuality.LowImpactPublication]: 2,
  [PublicationQuality.NotAPublication]: 1,
};

/**
 * Calculates a score for a reference based on its confidence and publication quality.
 * Confidence is weighted more heavily than quality (10x multiplier).
 *
 * @param ref - The reference to score
 * @returns A numeric score where higher values indicate better references
 */
export function scoreReference(ref: Reference): number {
  const confidence = ref.confidence_in_recommendation;
  const quality = ref.publication_quality;

  const confidenceScore = confidence ? confidenceRank[confidence] || 0 : 0;
  const qualityScore = quality ? qualityRank[quality] || 0 : 0;

  // Weight confidence higher than quality
  return confidenceScore * 10 + qualityScore;
}

/**
 * Calculates a score for a citation suggestion based on its best (highest-scored) reference.
 *
 * @param suggestion - The citation suggestion to score
 * @returns The maximum reference score, or 0 if no references exist
 */
export function scoreSuggestion(suggestion: CitationSuggestionResultWithClaimIndex): number {
  const refs = suggestion?.relevant_references || [];
  if (refs.length === 0) return 0;
  return Math.max(...refs.map(scoreReference));
}
