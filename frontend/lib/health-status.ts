import { DocumentIssue, SeverityEnum, WorkflowRunDetail, WorkflowRunStatus, WorkflowRunType } from './generated-api';
import { getDisplayStatus, DisplayStatus } from './workflow-state';

/**
 * Health status for a workflow widget
 */
export type HealthStatus = 'healthy' | 'issues' | 'processing' | 'error';

/**
 * Aggregated health data for a workflow type
 */
export interface WorkflowHealthData {
  type: WorkflowRunType;
  status: HealthStatus;
  displayStatus: DisplayStatus;
  issueCount: number;
  highSeverityCount: number;
  mediumSeverityCount: number;
  lowSeverityCount: number;
  workflowRun: WorkflowRunDetail;
}

/**
 * Determines if an issue should be considered as affecting health status.
 * Only Medium and High severity issues affect the health status.
 */
export function isHealthAffectingIssue(issue: DocumentIssue): boolean {
  return issue.severity === SeverityEnum.High || issue.severity === SeverityEnum.Medium;
}

/**
 * Counts issues by severity for a given workflow type
 */
export function countIssuesBySeverity(
  issues: DocumentIssue[],
  workflowType: WorkflowRunType,
): { high: number; medium: number; low: number; total: number } {
  const workflowIssues = issues.filter((issue) => issue.type === workflowType);

  return {
    high: workflowIssues.filter((i) => i.severity === SeverityEnum.High).length,
    medium: workflowIssues.filter((i) => i.severity === SeverityEnum.Medium).length,
    low: workflowIssues.filter((i) => i.severity === SeverityEnum.Low).length,
    total: workflowIssues.length,
  };
}

/**
 * Determines the health status for a workflow based on its run status and issues
 */
export function determineHealthStatus(workflowRun: WorkflowRunDetail, issues: DocumentIssue[]): HealthStatus {
  const displayStatus = getDisplayStatus(workflowRun);

  // Error state takes priority
  if (displayStatus === 'failed') {
    return 'error';
  }

  // Processing state (pending or running)
  if (workflowRun.run.status === WorkflowRunStatus.Pending || workflowRun.run.status === WorkflowRunStatus.Running) {
    return 'processing';
  }

  // Check for health-affecting issues (medium or high severity)
  const workflowIssues = issues.filter((issue) => issue.type === workflowRun.run.type);
  const hasHealthAffectingIssues = workflowIssues.some(isHealthAffectingIssue);

  return hasHealthAffectingIssues ? 'issues' : 'healthy';
}

/**
 * Aggregates health data for all workflow runs
 */
export function aggregateWorkflowHealth(
  workflowRuns: WorkflowRunDetail[],
  issues: DocumentIssue[],
): WorkflowHealthData[] {
  return workflowRuns.map((workflowRun) => {
    const { high, medium, low, total } = countIssuesBySeverity(issues, workflowRun.run.type);

    return {
      type: workflowRun.run.type,
      status: determineHealthStatus(workflowRun, issues),
      displayStatus: getDisplayStatus(workflowRun),
      issueCount: total,
      highSeverityCount: high,
      mediumSeverityCount: medium,
      lowSeverityCount: low,
      workflowRun,
    };
  });
}

/**
 * Calculates overall project health from individual workflow health data
 */
export function calculateOverallHealth(healthData: WorkflowHealthData[]): HealthStatus {
  if (healthData.length === 0) return 'healthy';

  // If any workflow has an error, overall is error
  if (healthData.some((h) => h.status === 'error')) return 'error';

  // If any workflow has issues, overall has issues
  if (healthData.some((h) => h.status === 'issues')) return 'issues';

  // If any workflow is processing, overall is processing
  if (healthData.some((h) => h.status === 'processing')) return 'processing';

  return 'healthy';
}

/**
 * Configuration for health status display
 */
export const healthStatusConfig: Record<
  HealthStatus,
  {
    label: string;
    description: string;
    colorClass: string;
    bgClass: string;
    borderClass: string;
  }
> = {
  healthy: {
    label: 'Healthy',
    description: 'No significant issues found',
    colorClass: 'text-green-600',
    bgClass: 'bg-green-50',
    borderClass: 'border-green-200',
  },
  issues: {
    label: 'Issues Found',
    description: 'Review recommended',
    colorClass: 'text-amber-600',
    bgClass: 'bg-amber-50',
    borderClass: 'border-amber-200',
  },
  processing: {
    label: 'Processing',
    description: 'Analysis in progress',
    colorClass: 'text-blue-600',
    bgClass: 'bg-blue-50',
    borderClass: 'border-blue-200',
  },
  error: {
    label: 'Error',
    description: 'Analysis failed',
    colorClass: 'text-red-600',
    bgClass: 'bg-red-50',
    borderClass: 'border-red-200',
  },
};
