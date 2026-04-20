import { Issue, SeverityEnum, WorkflowRunDetail, WorkflowRunStatus, WorkflowRunType } from './generated-api';
import { getDisplayStatus } from './workflow-state';

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
export function isHealthAffectingIssue(issue: Issue): boolean {
  return issue.severity === SeverityEnum.High || issue.severity === SeverityEnum.Medium;
}

/**
 * Counts issues by severity from a pre-filtered list
 */
function countBySeverity(issues: Issue[]): { high: number; medium: number; low: number; total: number } {
  const high = issues.filter((i) => i.severity === SeverityEnum.High).length;
  const medium = issues.filter((i) => i.severity === SeverityEnum.Medium).length;
  const low = issues.filter((i) => i.severity === SeverityEnum.Low).length;
  return {
    high,
    medium,
    low,
    total: high + medium + low,
  };
}

/**
 * Determines the health status for a workflow based on its run status and issues.
 * Accepts pre-filtered issues to avoid redundant filtering in aggregateWorkflowHealth.
 */
function determineHealthStatusFromIssues(workflowRun: WorkflowRunDetail, workflowIssues: Issue[]): HealthStatus {
  const displayStatus = getDisplayStatus(workflowRun);

  if (displayStatus === 'failed') return 'error';

  if (workflowRun.run.status === WorkflowRunStatus.Pending || workflowRun.run.status === WorkflowRunStatus.Running) {
    return 'processing';
  }

  return workflowIssues.some(isHealthAffectingIssue) ? 'issues' : 'healthy';
}

/**
 * Aggregates health data for all workflow runs
 */
export function aggregateWorkflowHealth(workflowRuns: WorkflowRunDetail[], issues: Issue[]): WorkflowHealthData[] {
  return workflowRuns.map((workflowRun) => {
    const workflowIssues = issues.filter((issue) => issue.workflow_type === workflowRun.run.type);
    const { high, medium, low, total } = countBySeverity(workflowIssues);

    return {
      type: workflowRun.run.type,
      status: determineHealthStatusFromIssues(workflowRun, workflowIssues),
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
    description: string;
    colorClass: string;
    borderClass: string;
  }
> = {
  healthy: {
    description: 'No significant issues found',
    colorClass: 'text-green-600',
    borderClass: 'border-green-200',
  },
  issues: {
    description: 'Review recommended',
    colorClass: 'text-amber-600',
    borderClass: 'border-amber-200',
  },
  processing: {
    description: 'Analysis in progress',
    colorClass: 'text-blue-600',
    borderClass: 'border-blue-200',
  },
  error: {
    description: 'Analysis failed',
    colorClass: 'text-red-600',
    borderClass: 'border-red-200',
  },
};
