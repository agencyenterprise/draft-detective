'use client';

interface SeverityDonutChartProps {
  high: number;
  medium: number;
  low: number;
}

const SEVERITY_COLORS = {
  high: { fill: '#dc2626', label: 'High' },
  medium: { fill: '#d97706', label: 'Medium' },
  low: { fill: '#2563eb', label: 'Low' },
} as const;

/**
 * A small round donut chart showing the split of high/medium/low severity issues
 * with a legend beside it.
 */
export function SeverityDonutChart({ high, medium, low }: SeverityDonutChartProps) {
  const total = high + medium + low;
  if (total === 0) return null;

  const size = 64;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Calculate arc segments (high → medium → low)
  const segments = [
    { count: high, color: SEVERITY_COLORS.high.fill },
    { count: medium, color: SEVERITY_COLORS.medium.fill },
    { count: low, color: SEVERITY_COLORS.low.fill },
  ].filter((s) => s.count > 0);

  let accumulatedOffset = 0;

  return (
    <div className="flex items-center gap-3">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0 -rotate-90">
        {segments.map((segment, i) => {
          const segmentLength = (segment.count / total) * circumference;
          const offset = accumulatedOffset;
          accumulatedOffset += segmentLength;

          return (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${segmentLength} ${circumference - segmentLength}`}
              strokeDashoffset={-offset}
              strokeLinecap="round"
              className="transition-all duration-300"
            />
          );
        })}
      </svg>

      <div className="flex flex-col gap-1 text-xs">
        {high > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-red-600 shrink-0" />
            <span className="text-muted-foreground">
              High <span className="font-semibold text-foreground">{high}</span>
            </span>
          </div>
        )}
        {medium > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-amber-600 shrink-0" />
            <span className="text-muted-foreground">
              Medium <span className="font-semibold text-foreground">{medium}</span>
            </span>
          </div>
        )}
        {low > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-blue-600 shrink-0" />
            <span className="text-muted-foreground">
              Low <span className="font-semibold text-foreground">{low}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
