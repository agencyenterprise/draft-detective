import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';

const severityConfigMap: Record<
  SeverityEnum,
  {
    title: string;
    description: string;
    className: string;
  }
> = {
  [SeverityEnum.None]: {
    // fgColorClassName: 'text-green-600',
    title: 'No issues',
    description: 'No issues found',
    className: 'bg-green-700 text-white',
  },
  [SeverityEnum.Low]: {
    title: 'Low',
    description: 'Low severity issue found',
    className: 'bg-blue-600 text-white',
  },
  [SeverityEnum.Medium]: {
    title: 'Medium',
    description: 'Medium severity issue found',
    className: 'bg-yellow-600 text-white',
  },
  [SeverityEnum.High]: {
    title: 'High',
    description: 'High severity issue found',
    className: 'bg-red-600 text-white',
  },
};

export interface SeverityBadgeProps {
  severity: SeverityEnum;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const { title, description, className } = severityConfigMap[severity];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn('inline-flex items-center gap-1 px-2 py-0.75 rounded-md text-xs font-medium', className)}>
          {title}
        </span>
      </TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  );
}
