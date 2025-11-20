import { ClaimSubstantiatorStateOutput, DocumentChunkOutput, DocumentIssue, SeverityEnum } from './generated-api';

export function getMaxChunkSeverity(results: ClaimSubstantiatorStateOutput, chunk: DocumentChunkOutput) {
  const issues = results.rankedIssues?.filter((issue) => issue.chunkIndex === chunk.chunkIndex) || [];
  return getMaxSeverity(issues);
}

export function getClaimIssues(results: ClaimSubstantiatorStateOutput, chunkIndex: number, claimIndex: number) {
  return (
    results.rankedIssues?.filter((issue) => issue.chunkIndex === chunkIndex && issue.claimIndex === claimIndex) || []
  ).sort(sortDocumentIssueBySeverity);
}

export function getChunkIssues(results: ClaimSubstantiatorStateOutput, chunkIndex: number) {
  return (
    results.rankedIssues?.filter(
      (issue) => issue.chunkIndex === chunkIndex && (issue.claimIndex === null || issue.claimIndex === undefined),
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
