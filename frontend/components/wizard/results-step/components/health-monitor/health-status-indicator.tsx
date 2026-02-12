'use client';

import { HealthStatus, healthStatusConfig } from '@/lib/health-status';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react';

interface HealthStatusIndicatorProps {
  status: HealthStatus;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

const sizeClasses = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
};

const iconMap: Record<HealthStatus, React.ElementType> = {
  healthy: CheckCircle2,
  issues: AlertTriangle,
  processing: Loader2,
  error: XCircle,
};

export function HealthStatusIndicator({ status, size = 'md', showLabel = true }: HealthStatusIndicatorProps) {
  const config = healthStatusConfig[status];
  const Icon = iconMap[status];

  return (
    <span className={cn('inline-flex items-center gap-1.5', config.colorClass)}>
      <Icon className={cn(sizeClasses[size], status === 'processing' && 'animate-spin')} />
      {showLabel && <span className="text-sm font-medium">{config.label}</span>}
    </span>
  );
}
