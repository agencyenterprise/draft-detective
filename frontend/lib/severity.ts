import { DocumentChunk, Issue, SeverityEnum } from './generated-api';

/**
 * Check if an issue is associated with a given chunk index.
 * Supports both legacy chunk_index and new chunk_indices array.
 */
function issueMatchesChunk(issue: Issue, chunkIndex: number): boolean {
  if (issue.chunk_indices && issue.chunk_indices.includes(chunkIndex)) {
    return true;
  }

  return issue.chunk_index === chunkIndex;
}

export function getMaxChunkSeverity(issues: Issue[], chunk: DocumentChunk): SeverityEnum | undefined {
  const chunkIssues = issues.filter((issue) => issueMatchesChunk(issue, chunk.chunk_index));
  return getMaxSeverity(chunkIssues);
}

/**
 * Returns the issues that are associated with any of the given chunk indices.
 * @param issues - The issues to filter
 * @param chunkIndices - The chunk indices to filter by
 */
export function getChunkIssuesByIndices(issues: Issue[], chunkIndices: number[]): Issue[] {
  return issues
    .filter((issue) => chunkIndices.some((chunkIndex) => issueMatchesChunk(issue, chunkIndex)))
    .sort(sortIssueBySeverity);
}

export function sortIssueBySeverity(a: Issue, b: Issue) {
  return severitySortIndex[b.severity] - severitySortIndex[a.severity];
}

export function getMaxSeverity(issues: Issue[]): SeverityEnum | undefined {
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
  if (severities.includes(SeverityEnum.None)) {
    return SeverityEnum.None;
  }
  return undefined;
}

const severitySortIndex: Record<SeverityEnum, number> = {
  [SeverityEnum.None]: 0,
  [SeverityEnum.Low]: 1,
  [SeverityEnum.Medium]: 2,
  [SeverityEnum.High]: 3,
};
