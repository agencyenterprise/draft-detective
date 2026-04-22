import { DocumentChunk, Issue, SeverityEnum } from './generated-api';

/**
 * Check if an issue is associated with a given chunk index.
 */
function issueMatchesChunk(issue: Issue, chunkIndex: number): boolean {
  return issue.chunk_indices?.includes(chunkIndex) ?? false;
}

export function getMaxChunkSeverity(issues: Issue[], chunk: DocumentChunk): SeverityEnum | undefined {
  const chunkIssues = issues.filter((issue) => issueMatchesChunk(issue, chunk.chunk_index));
  return getMaxSeverity(chunkIssues);
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
