'use client';

import { Card, CardContent } from '@/components/ui/card';
import { HealthStatus, healthStatusConfig } from '@/lib/health-status';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';
import { HealthStatusIndicator } from './health-status-indicator';
import { SeverityDonutChart } from './severity-donut-chart';

interface OverallHealthCardProps {
  overallHealth: HealthStatus;
  totalWorkflows: number;
  totalIssues: number;
  highSeverityTotal: number;
  mediumSeverityTotal: number;
  lowSeverityTotal: number;
}

export function OverallHealthCard({
  overallHealth,
  totalWorkflows,
  totalIssues,
  highSeverityTotal,
  mediumSeverityTotal,
  lowSeverityTotal,
}: OverallHealthCardProps) {
  const config = healthStatusConfig[overallHealth];

  return (
    <Card className="border bg-card">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-full bg-muted border border-border">
              <Activity className={cn('h-8 w-8', config.colorClass)} />
            </div>
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-2">
                Project Health
                <HealthStatusIndicator status={overallHealth} />
              </h2>
              <p className="text-sm text-muted-foreground">{config.description}</p>
            </div>
          </div>

          <div className="flex items-center gap-8">
            <div className="text-center">
              <div className="text-3xl font-bold">{totalWorkflows}</div>
              <div className="text-sm text-muted-foreground">Assessments</div>
            </div>
            <div className="text-center">
              <div className={cn('text-3xl font-bold', totalIssues > 0 ? 'text-amber-600' : 'text-emerald-600')}>
                {totalIssues}
              </div>
              <div className="text-sm text-muted-foreground">Total Issues</div>
            </div>
            {totalIssues > 0 && (
              <SeverityDonutChart high={highSeverityTotal} medium={mediumSeverityTotal} low={lowSeverityTotal} />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
