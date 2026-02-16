'use client';

import { Badge } from '@/components/ui/badge';
import { HealthStatus } from '@/lib/health-status';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react';

interface HealthStatusIndicatorProps {
  status: HealthStatus;
  size?: 'sm' | 'md';
}

const statusBadgeConfig: Record<
  HealthStatus,
  {
    icon: React.ElementType;
    label: string;
    className: string;
  }
> = {
  healthy: {
    icon: CheckCircle2,
    label: 'All clear',
    className: 'border-transparent bg-green-700 text-white',
  },
  issues: {
    icon: AlertTriangle,
    label: 'Review recommended',
    className: 'border-transparent bg-amber-600 text-white',
  },
  processing: {
    icon: Loader2,
    label: 'Analyzing…',
    className: 'border-transparent bg-blue-600 text-white',
  },
  error: {
    icon: XCircle,
    label: 'Analysis failed',
    className: 'border-transparent bg-red-600 text-white',
  },
};

const sizeClasses = {
  sm: { badge: 'text-[10px] px-1.5 py-0', icon: 'size-3' },
  md: { badge: 'text-xs px-2 py-0.5', icon: 'size-3.5' },
};

export function HealthStatusIndicator({ status, size = 'md' }: HealthStatusIndicatorProps) {
  const config = statusBadgeConfig[status];
  const Icon = config.icon;
  const sizes = sizeClasses[size];

  return (
    <Badge className={cn('gap-1', config.className, sizes.badge)}>
      <Icon className={cn(sizes.icon, status === 'processing' && 'animate-spin')} />
      {config.label}
    </Badge>
  );
}
