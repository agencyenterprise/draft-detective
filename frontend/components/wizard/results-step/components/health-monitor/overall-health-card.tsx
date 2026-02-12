'use client';

import { Card, CardContent } from '@/components/ui/card';
import { HealthStatus, healthStatusConfig } from '@/lib/health-status';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';
import { HealthStatusIndicator } from './health-status-indicator';

interface OverallHealthCardProps {
  overallHealth: HealthStatus;
  totalWorkflows: number;
  totalIssues: number;
  highSeverityTotal: number;
  mediumSeverityTotal: number;
}

export function OverallHealthCard({
  overallHealth,
  totalWorkflows,
  totalIssues,
  highSeverityTotal,
  mediumSeverityTotal,
}: OverallHealthCardProps) {
  const config = healthStatusConfig[overallHealth];

  return (
    <Card className={cn('border-2', config.borderClass, config.bgClass)}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={cn('p-3 rounded-full', config.bgClass, 'border', config.borderClass)}>
              <Activity className={cn('h-8 w-8', config.colorClass)} />
            </div>
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-2">
                Project Health
                <HealthStatusIndicator status={overallHealth} size="lg" showLabel={false} />
              </h2>
              <p className={cn('text-sm', config.colorClass)}>{config.description}</p>
            </div>
          </div>

          <div className="flex gap-8 text-center">
            <div>
              <div className="text-3xl font-bold">{totalWorkflows}</div>
              <div className="text-sm text-muted-foreground">Analyses</div>
            </div>
            <div>
              <div className={cn('text-3xl font-bold', totalIssues > 0 ? 'text-amber-600' : 'text-emerald-600')}>
                {totalIssues}
              </div>
              <div className="text-sm text-muted-foreground">Total Issues</div>
            </div>
            {highSeverityTotal > 0 && (
              <div>
                <div className="text-3xl font-bold text-red-600">{highSeverityTotal}</div>
                <div className="text-sm text-muted-foreground">High Severity</div>
              </div>
            )}
            {mediumSeverityTotal > 0 && (
              <div>
                <div className="text-3xl font-bold text-amber-600">{mediumSeverityTotal}</div>
                <div className="text-sm text-muted-foreground">Medium Severity</div>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
