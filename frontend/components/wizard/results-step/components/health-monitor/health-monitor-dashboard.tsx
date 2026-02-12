'use client';

import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowHealth } from '@/lib/hooks/use-workflow-health';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import { OverallHealthCard } from './overall-health-card';
import { WorkflowHealthWidget } from './workflow-health-widget';

interface HealthMonitorDashboardProps {
  projectDetail: ProjectDetailed;
  onNavigateToAnalyses?: (workflowType?: WorkflowRunType) => void;
  onNavigateToDocumentExplorer?: (workflowType?: WorkflowRunType) => void;
}

export function HealthMonitorDashboard({
  projectDetail,
  onNavigateToAnalyses,
  onNavigateToDocumentExplorer,
}: HealthMonitorDashboardProps) {
  const workflowRuns = projectDetail.workflow_runs ?? [];
  const issues = projectDetail.issues ?? [];

  const { healthData, overallHealth, totalIssues, highSeverityTotal, mediumSeverityTotal, isLoading } =
    useWorkflowHealth(workflowRuns, issues);

  const { data: workflowTypes } = useWorkflowTypes();

  // Sort health data by workflow order for consistent display
  const sortedHealthData = useMemo(() => {
    if (!workflowTypes) return healthData;

    const orderMap = new Map(workflowTypes.map((wt) => [wt.type, wt.order]));
    return [...healthData].sort((a, b) => {
      const orderA = orderMap.get(a.type) ?? 99;
      const orderB = orderMap.get(b.type) ?? 99;
      return orderA - orderB;
    });
  }, [healthData, workflowTypes]);

  const handleReviewIssues = (workflowType: WorkflowRunType) => {
    // Navigate to document explorer with workflow type filter
    if (onNavigateToDocumentExplorer) {
      onNavigateToDocumentExplorer(workflowType);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (sortedHealthData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">No analyses have been run yet.</p>
        <p className="text-sm text-muted-foreground mt-1">Start an analysis to see the project health dashboard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overall Health Summary */}
      <OverallHealthCard
        overallHealth={overallHealth}
        totalWorkflows={sortedHealthData.length}
        totalIssues={totalIssues}
        highSeverityTotal={highSeverityTotal}
        mediumSeverityTotal={mediumSeverityTotal}
      />

      {/* Workflow Widgets Grid */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Analysis Health by Workflow</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedHealthData.map((data) => (
            <WorkflowHealthWidget
              key={data.type}
              healthData={data}
              onReviewIssues={() => handleReviewIssues(data.type)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
