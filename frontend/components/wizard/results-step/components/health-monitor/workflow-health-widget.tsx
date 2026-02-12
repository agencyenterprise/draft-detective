'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { healthStatusConfig, WorkflowHealthData } from '@/lib/health-status';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import { HealthStatusIndicator } from './health-status-indicator';
import { SeverityProgressBar } from './severity-progress-bar';

interface WorkflowHealthWidgetProps {
  healthData: WorkflowHealthData;
  onReviewIssues?: () => void;
}

/**
 * Individual workflow health widget displaying status and key metrics.
 * White card with a bold left border colored by health status.
 */
export function WorkflowHealthWidget({ healthData, onReviewIssues }: WorkflowHealthWidgetProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const config = healthStatusConfig[healthData.status];

  const hasIssues = healthData.issueCount > 0;

  return (
    <Card className={cn('transition-all hover:shadow-md bg-white border-0 border-l-4', config.borderClass)}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base font-semibold">{getWorkflowTypeName(healthData.type)}</CardTitle>
          <HealthStatusIndicator status={healthData.status} size="sm" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Issue severity progress bar */}
        {hasIssues && (
          <SeverityProgressBar
            high={healthData.highSeverityCount}
            medium={healthData.mediumSeverityCount}
            low={healthData.lowSeverityCount}
          />
        )}

        {/* Action button */}
        {hasIssues && onReviewIssues && (
          <Button
            variant="ghost"
            size="sm"
            className={cn('w-full justify-between', config.colorClass)}
            onClick={onReviewIssues}
          >
            Review issues
            <ArrowRight className="h-4 w-4" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
