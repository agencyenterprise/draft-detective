import { DocumentChunk, DocumentIssue, SeverityEnum } from './generated-api';

/**
 * Check if an issue is associated with a given chunk index.
 * Supports both legacy chunk_index and new chunk_indices array.
 */
function issueMatchesChunk(issue: DocumentIssue, chunkIndex: number): boolean {
  if (issue.chunk_indices && issue.chunk_indices.includes(chunkIndex)) {
    return true;
  }

  return issue.chunk_index === chunkIndex;
}

export function getMaxChunkSeverity(issues: DocumentIssue[], chunk: DocumentChunk) {
  const chunkIssues = issues.filter((issue) => issueMatchesChunk(issue, chunk.chunk_index));
  return getMaxSeverity(chunkIssues);
}

export function getClaimIssues(issues: DocumentIssue[], chunkIndex: number, claimIndex: number) {
  return issues
    .filter((issue) => issueMatchesChunk(issue, chunkIndex) && issue.claim_index === claimIndex)
    .sort(sortDocumentIssueBySeverity);
}

export function getChunkIssues(issues: DocumentIssue[], chunkIndex: number) {
  return issues
    .filter(
      (issue) =>
        issueMatchesChunk(issue, chunkIndex) && (issue.claim_index === null || issue.claim_index === undefined),
    )
    .sort(sortDocumentIssueBySeverity);
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
