'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { healthStatusConfig, WorkflowHealthData } from '@/lib/health-status';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import { ArrowRight, CircleAlert, TriangleAlert } from 'lucide-react';
import { HealthStatusIndicator } from './health-status-indicator';

interface WorkflowHealthWidgetProps {
  healthData: WorkflowHealthData;
  onReviewIssues?: () => void;
}

/**
 * Individual workflow health widget displaying status and key metrics.
 * This is the default widget - specialized widgets can be created for specific workflow types.
 */
export function WorkflowHealthWidget({ healthData, onReviewIssues }: WorkflowHealthWidgetProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const config = healthStatusConfig[healthData.status];

  const hasIssues = healthData.issueCount > 0;
  const hasHighSeverity = healthData.highSeverityCount > 0;
  const hasMediumSeverity = healthData.mediumSeverityCount > 0;

  return (
    <Card className={cn('transition-all hover:shadow-md', config.borderClass, config.bgClass)}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base font-semibold">{getWorkflowTypeName(healthData.type)}</CardTitle>
          <HealthStatusIndicator status={healthData.status} size="sm" showLabel={false} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Status and description */}
        <div className="flex items-center gap-2">
          <HealthStatusIndicator status={healthData.status} size="md" showLabel={true} />
        </div>

        {/* Issue counts - only show if there are issues */}
        {hasIssues && (
          <div className="flex flex-wrap gap-3 text-sm">
            {hasHighSeverity && (
              <span className="inline-flex items-center gap-1 text-red-600">
                <CircleAlert className="h-3.5 w-3.5" />
                <span className="font-medium">{healthData.highSeverityCount}</span>
                <span className="text-muted-foreground">high</span>
              </span>
            )}
            {hasMediumSeverity && (
              <span className="inline-flex items-center gap-1 text-amber-600">
                <TriangleAlert className="h-3.5 w-3.5" />
                <span className="font-medium">{healthData.mediumSeverityCount}</span>
                <span className="text-muted-foreground">medium</span>
              </span>
            )}
            {healthData.lowSeverityCount > 0 && (
              <span className="inline-flex items-center gap-1 text-blue-600">
                <span className="font-medium">{healthData.lowSeverityCount}</span>
                <span className="text-muted-foreground">low</span>
              </span>
            )}
          </div>
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
