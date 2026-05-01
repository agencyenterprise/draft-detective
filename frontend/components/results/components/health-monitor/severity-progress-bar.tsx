'use client';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface SeverityProgressBarProps {
  high: number;
  medium: number;
  low: number;
}

/**
 * A horizontal stacked progress bar showing issue counts by severity.
 * Each segment is colored by severity and shows the count on hover.
 */
export function SeverityProgressBar({ high, medium, low }: SeverityProgressBarProps) {
  const total = high + medium + low;
  if (total === 0) return null;

  const segments = [
    { count: high, color: 'bg-red-600', label: 'High' },
    { count: medium, color: 'bg-amber-600', label: 'Medium' },
    { count: low, color: 'bg-blue-600', label: 'Low' },
  ].filter((s) => s.count > 0);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {total} issue{total !== 1 ? 's' : ''}
        </span>
        <div className="flex items-center gap-2">
          {segments.map((s) => (
            <span key={s.label} className="flex items-center gap-1">
              <span className={`size-2 rounded-full ${s.color}`} />
              {s.count} {s.label.toLowerCase()}
            </span>
          ))}
        </div>
      </div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {segments.map((segment) => (
          <Tooltip key={segment.label}>
            <TooltipTrigger asChild>
              <div
                className={`${segment.color} transition-all duration-300`}
                style={{ width: `${(segment.count / total) * 100}%` }}
              />
            </TooltipTrigger>
            <TooltipContent>
              {segment.count} {segment.label} severity
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
