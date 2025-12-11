import { ClaimSubstantiatorStateSummary, DocumentChunkOutput, DocumentIssue, SeverityEnum } from './generated-api';

export function getMaxChunkSeverity(results: ClaimSubstantiatorStateSummary, chunk: DocumentChunkOutput) {
  const issues = results.ranked_issues?.filter((issue) => issue.chunk_index === chunk.chunk_index) || [];
  return getMaxSeverity(issues);
}

export function getClaimIssues(results: ClaimSubstantiatorStateSummary, chunkIndex: number, claimIndex: number) {
  return (
    results.ranked_issues?.filter((issue) => issue.chunk_index === chunkIndex && issue.claim_index === claimIndex) || []
  ).sort(sortDocumentIssueBySeverity);
}

export function getChunkIssues(results: ClaimSubstantiatorStateSummary, chunkIndex: number) {
  return (
    results.ranked_issues?.filter(
      (issue) => issue.chunk_index === chunkIndex && (issue.claim_index === null || issue.claim_index === undefined),
    ) || []
  ).sort(sortDocumentIssueBySeverity);
}

export function sortDocumentIssueBySeverity(a: DocumentIssue, b: DocumentIssue) {
  return severitySortIndex[b.severity] - severitySortIndex[a.severity];
}

export function sortBySeverity(a: SeverityEnum, b: SeverityEnum) {
  return severitySortIndex[b] - severitySortIndex[a];
}

export function getMaxSeverity(issues: DocumentIssue[]) {
  const severities = issues.map((issue) => issue.severity);
  if (severities.includes(SeverityEnum.High)) {
    return SeverityEnum.High;
  }
  if (severities.includes(SeverityEnum.Medium)) {
    return SeverityEnum.Medium;
  }
  if (severities.includes(SeverityEnum.Low)) {
    return SeverityEnum.Low;
  }
  return SeverityEnum.None;
}

const severitySortIndex: Record<SeverityEnum, number> = {
  [SeverityEnum.None]: 0,
  [SeverityEnum.Low]: 1,
  [SeverityEnum.Medium]: 2,
  [SeverityEnum.High]: 3,
};
