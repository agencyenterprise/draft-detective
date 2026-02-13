import { useMemo } from 'react';
import { Issue, WorkflowRun, WorkflowRunDetail } from '../generated-api';
import { aggregateWorkflowHealth, calculateOverallHealth, HealthStatus, WorkflowHealthData } from '../health-status';
import { useWorkflowTypes } from './use-workflow-types';

interface UseWorkflowHealthResult {
  healthData: WorkflowHealthData[];
  overallHealth: HealthStatus;
  totalIssues: number;
  highSeverityTotal: number;
  mediumSeverityTotal: number;
  lowSeverityTotal: number;
  isLoading: boolean;
}

/**
 * Hook to aggregate workflow health data for display in the health monitor dashboard.
 * Filters to only include user-visible workflows that have been started.
 */
export function useWorkflowHealth(workflowRuns: WorkflowRunDetail[], issues: Issue[]): UseWorkflowHealthResult {
  const { isWorkflowTypeVisible, isLoading } = useWorkflowTypes();

  const healthData = useMemo(() => {
    // Filter to only user-visible workflows
    const visibleWorkflows = workflowRuns.filter((run) => isWorkflowTypeVisible(run.run.type));

    // Aggregate health data
    return aggregateWorkflowHealth(visibleWorkflows, issues);
  }, [workflowRuns, issues, isWorkflowTypeVisible]);

  const overallHealth = useMemo(() => calculateOverallHealth(healthData), [healthData]);

  const totals = useMemo(() => {
    return healthData.reduce(
      (acc, data) => ({
        totalIssues: acc.totalIssues + data.issueCount,
        highSeverityTotal: acc.highSeverityTotal + data.highSeverityCount,
        mediumSeverityTotal: acc.mediumSeverityTotal + data.mediumSeverityCount,
        lowSeverityTotal: acc.lowSeverityTotal + data.lowSeverityCount,
      }),
      { totalIssues: 0, highSeverityTotal: 0, mediumSeverityTotal: 0, lowSeverityTotal: 0 },
    );
  }, [healthData]);

  return {
    healthData,
    overallHealth,
    ...totals,
    isLoading,
  };
}
