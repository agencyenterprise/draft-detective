import { Issue, SeverityEnum } from './generated-api';

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
