'use client';

import { HealthMonitorDashboard } from '../components/health-monitor';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';

interface SummaryTabProps {
  projectDetail: ProjectDetailed;
  onNavigateToAnalyses?: (workflowType?: WorkflowRunType) => void;
  onNavigateToDocumentExplorer?: (workflowType?: WorkflowRunType) => void;
}

export function SummaryTab({ projectDetail, onNavigateToAnalyses, onNavigateToDocumentExplorer }: SummaryTabProps) {
  return (
    <HealthMonitorDashboard
      projectDetail={projectDetail}
      onNavigateToAnalyses={onNavigateToAnalyses}
      onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
    />
  );
}
